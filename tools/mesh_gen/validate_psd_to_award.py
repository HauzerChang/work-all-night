#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 生成 mesh → 對照 Award 真實生產 mesh。

這是 S3+S4 串接的最後一哩:先前分別驗過「PSD 切圖無損」(S4)與「生成 mesh 對 main_draw
窗簾/陰影收斂」(S3)。本工具把兩者接起來,並用**真實生產標的(Award 的機器人 mesh)**當真值:

  robot_parts.psd 的可動件(光暈/身體/左手,在 Award 皆為 mesh)
    → psd_slice 切出上正立件 PNG(S4)
    → generate_mesh(_v2) 從件 alpha 生成 mesh(S3)
    → ① 生成 mesh 覆蓋率 vs ② Award 藝術家 mesh 覆蓋率(同一輪廓、同一正規化框)
    → 生成 ≥ 藝術家基準 - margin 即「達到藝術家等級覆蓋」。

## 座標對齊(關鍵)
Award mesh 的 `uvs` 是 **atlas region 框**的 0-1 座標,而該 region 在 atlas 中可能被
**旋轉(rotate:true)+ 縮小(~0.70)打包**(見 knowledge/s4-psd-to-spine-real.md)。
PSD 切件則是**上正立、邏輯原尺寸**。故不能直接把 artist uvs 疊到件像素上。

作法:把兩者都柵格化到同一個 N×N 正規化方框再比 IoU(方框化對 mesh 與 alpha 皆等效,
IoU 不受長寬比擠壓影響)。藝術家 uvs 直接 (u·N, v·N) 填三角;件 alpha 則對 8 種
(4 旋轉 × 水平翻)朝向各算一次 IoU 取最大 —— **朝向由『哪個對得最好』自證**
(外部真值互校,與 atlas_crop 方向 bug 同一套方法論)。

生成 mesh 因由該件 alpha 直接產出,無朝向歧義,同樣柵格化到 N×N 與正立件輪廓比。

## Award 三個 mesh 件(真值)
  光暈 706×683(atlas rotate) · 身體 379×425(atlas rotate) · 左手 257×215(atlas 不轉)
  三者在 Award **無 deform timeline**(靠骨骼/權重變形),故本閘主打**靜態覆蓋率對照**;
  變形穩健度用「轉移真實位移場」另做 robustness 附加檢查(非 pass 門檻)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
import deform_eval as de


N_RASTER = 256


def award_mesh(skeleton_path, slot, name):
    sk = json.load(open(skeleton_path))
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    a = att[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return uvs, tris, len(uvs)


def raster_uv(uvs, tris, n=N_RASTER):
    """把 mesh 三角形填進 n×n 正規化框(uv 直接當座標)。"""
    canvas = np.zeros((n, n), np.uint8)
    p = np.column_stack([np.clip(uvs[:, 0], 0, 1) * (n - 1),
                         np.clip(uvs[:, 1], 0, 1) * (n - 1)])
    for t in tris:
        cv2.fillConvexPoly(canvas, np.round(p[t]).astype(np.int32), 1)
    return canvas


def iou(a, b):
    a = a > 0; b = b > 0
    u = int((a | b).sum())
    return float((a & b).sum() / u) if u else 0.0


def best_orientation_iou(artist_raster, piece_mask, n=N_RASTER):
    """件 alpha 對 8 朝向各柵格化到 n×n,回傳與 artist_raster 的最大 IoU 與朝向名。"""
    best, best_name = -1.0, None
    for k in range(4):
        base = np.rot90(piece_mask, k)
        for flip, tag in ((base, f"rot{k*90}"), (np.fliplr(base), f"rot{k*90}+flipH")):
            r = cv2.resize(flip.astype(np.uint8), (n, n), interpolation=cv2.INTER_NEAREST)
            v = iou(artist_raster, r)
            if v > best:
                best, best_name = v, tag
    return best, best_name


def piece_mask_from_png(im):
    """PIL RGBA -> 上正立 alpha mask (H,W)。"""
    arr = np.array(im)
    if arr.ndim == 3 and arr.shape[2] == 4:
        return (arr[:, :, 3] > 8).astype(np.uint8)
    g = arr if arr.ndim == 2 else cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    return (g > 8).astype(np.uint8)


def robustness_stress(mesh, curtain_skeleton="assets/main_draw.json",
                      curtain_slot="image/curtain_left", curtain_name="image/curtain_left"):
    """附加(非門檻):把 main_draw 窗簾的『真實位移場』轉移到生成 mesh,查 0 自交/0 翻面。
    這些 Award mesh 本身無 deform timeline,此檢查僅測拓樸對『真實等級大變形』的耐受度。"""
    try:
        sk = json.load(open(curtain_skeleton))
        uvs_src, field, frame = de.real_deform_field(sk, curtain_slot, curtain_name)
        dres = de.transfer_deform_check(mesh, uvs_src, field)
        return {"source_frame": frame, "area_ratio": dres["area_ratio"],
                "self_intersections": dres["self_intersections"],
                "triangle_flips": dres["triangle_flips"], "clean": dres["clean"]}
    except Exception as e:  # robustness 是加分項,失敗不影響 pass
        return {"error": str(e)}


def validate_piece(piece_im, skeleton, slot, name, gen_fn, iou_margin=0.03, budget=100):
    from evaluate_mesh import evaluate as eval_mesh
    mask = piece_mask_from_png(piece_im)
    H, W = mask.shape

    # 生成 mesh(需要檔案路徑 → 落到暫存 PNG)
    tmp = os.path.join("/tmp", f"_piece_{slot.replace('/', '_')}.png")
    piece_im.save(tmp)
    mesh = gen_fn(tmp)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    # 生成 mesh 覆蓋率(件正立框 → N×N)+ 格式閘
    gm = eval_mesh(mesh, mask, vertex_budget=budget, iou_thresh=0.0)
    gen_raster = raster_uv(np.array(mesh["uvs"]).reshape(-1, 2), np.array(mesh["triangles"]).reshape(-1, 3))
    piece_raster = cv2.resize(mask, (N_RASTER, N_RASTER), interpolation=cv2.INTER_NEAREST)
    gen_iou = iou(gen_raster, piece_raster)

    # 藝術家 mesh 覆蓋率(朝向自證)
    a_uvs, a_tris, a_nv = award_mesh(skeleton, slot, name)
    artist_raster = raster_uv(a_uvs, a_tris)
    artist_iou, orient = best_orientation_iou(artist_raster, mask)

    rob = robustness_stress(mesh)

    passed = gen_iou >= artist_iou - iou_margin
    fmt_ok = gm["criteria"]["AC4_format"]["pass"] and gm["criteria"]["AC2c_orphans"]["pass"]
    return {
        "slot": slot,
        "gen_mesh": {"vertices": nv, "hull": mesh["hull"],
                     "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode"),
                     "format_ok": bool(fmt_ok)},
        "artist_mesh": {"vertices": a_nv, "triangles": len(a_tris), "best_orient": orient},
        "coverage": {"gen_iou": round(gen_iou, 4), "artist_iou": round(artist_iou, 4),
                     "margin": iou_margin, "pass": bool(passed)},
        "deform_robustness_stress": rob,
        "overall_pass": bool(passed and fmt_ok),
    }


# Award 三個 mesh 件:PSD 圖層名 → (slot, attachment name)
MESH_PIECES = {
    "光暈": ("機器人拆件/光暈", "機器人拆件/光暈"),
    "身體": ("機器人拆件/身體", "機器人拆件/身體"),
    "左手": ("機器人拆件/左手", "機器人拆件/左手"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--layer", default=None, help="只驗單一圖層(光暈/身體/左手);預設全跑")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()

    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")

    _, _, parts = slice_psd(a.psd)
    by_name = {e["name"]: im for e, im in parts}

    targets = [a.layer] if a.layer else list(MESH_PIECES.keys())
    reports, all_pass = [], True
    for layer in targets:
        if layer not in MESH_PIECES:
            print(f"跳過(非 mesh 件或未知):{layer}"); continue
        if layer not in by_name:
            print(f"PSD 缺圖層:{layer}"); all_pass = False; continue
        slot, name = MESH_PIECES[layer]
        rep = validate_piece(by_name[layer], a.skeleton, slot, name, gen, a.margin)
        rep["layer"] = layer
        reports.append(rep)
        all_pass = all_pass and rep["overall_pass"]

    out = {"gen": a.gen, "overall_pass": all_pass, "pieces": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
