#!/usr/bin/env python3
"""端到端「PSD 件 → S3 生成 mesh → 對照 Award 真實 artist mesh」靜態驗收。

背景(knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 5 個圖層對應 Award spine
的 5 個 slot,其中 光暈/身體/左手 是 **mesh**(藝術家手做,ground truth)。本工具把
S3 `generate_mesh_v2` 產的 mesh 與**真實生產 artist mesh** 對同一張件 alpha 做 IoU 對照:

  1. `psd_slice` 切 robot_parts.psd → 各件 PNG(緊湊 bbox)。
  2. 取 Award artist mesh(用 `vertices`+`width/height` 的**邏輯座標**還原,
     天然 upright,**不碰 atlas 旋轉/縮放**,故無方向歧義)。
  3. 把件 alpha resize 到 artist (W,H) 當共同遮罩;生成 mesh 也在這張上跑。
  4. AC:`gen_iou >= artist_iou - margin`(生成 mesh 覆蓋率不輸藝術家)且生成 mesh 格式合法。

⚠️ 範圍誠實聲明:這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點
   deform)→ 本驗收為**靜態 IoU**,不含 deform 閘。deform 穩健性已在 main_draw 4 mesh
   的真實位移場轉移驗證過(見 s3-four-mesh-generalization.md)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, mesh_pixel_coords
from generate_mesh_v2 import generate as gen_v2
from atlas_crop import parse_atlas

# PSD 圖層名 ⇄ Award mesh slot(皆中文,slot = 機器人拆件/<圖層名>)
MESH_PARTS = ["光暈", "身體", "左手"]


def load_award_attachment(sk, layer):
    slot = f"機器人拆件/{layer}"
    skins = sk["skins"]; skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    return att[slot][slot], slot  # attachment 名 == slot 名


def uv_to_local(uvs, W, H):
    """Award JSON mesh uvs → 直立 region 局部像素。

    ⚠️ 關鍵(2026-08-14 實測校正):Spine JSON 的 mesh `uvs` 是 **region 局部正規化 [0,1]**
    (runtime SkeletonJson 載入時才乘進 atlas region 的 UV rect),**不是** atlas page 正規化;
    v 原點在上;因為是直立邏輯 region 座標,**與 atlas rotate 打包方向無關**。
    故 local = (u*W, v*H) 即可,無須處理旋轉。這些件皆 **weighted mesh**(vertices 為權重格式,
    不能當座標),setup 形狀只能從 uvs 還原。內建自檢:還原 mask 對真實 region alpha
    IoU 應 ≥0.80(4 形式 u*W,v*H 對 3 件實測 0.968–0.979,其餘翻轉 <0.77)。
    """
    uv = np.array(uvs, dtype=np.float64).reshape(-1, 2)
    return np.column_stack([uv[:, 0] * W, uv[:, 1] * H])


def render_from_pts(pts, tris, W, H):
    tris = np.array(tris, dtype=np.int32).reshape(-1, 3)
    canvas = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(canvas, np.round(pts[t]).astype(np.int32), 1)
    return canvas


def render_mesh_mask(mesh, W, H):
    pts, _, _ = mesh_pixel_coords({**mesh, "width": W, "height": H})
    return render_from_pts(pts, mesh["triangles"], W, H)


def iou(a, b):
    inter = int(np.logical_and(a, b).sum()); union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def psd_part_alpha(psd_parts_dir, layer):
    """從 psd_slice 輸出目錄找對應件 PNG,回傳 RGBA。"""
    man = json.load(open(os.path.join(psd_parts_dir, "manifest.json")))
    for e in man["parts"]:
        if e["name"] == layer:
            return Image.open(os.path.join(psd_parts_dir, e["file"])).convert("RGBA"), e
    raise SystemExit(f"PSD 件找不到圖層: {layer}")


def compare_one(sk, regions, atlas_path, assets_dir, psd_parts_dir, layer,
                tmp_dir, fig_dir=None, margin=0.02, eps=None):
    att, slot = load_award_attachment(sk, layer)
    region = regions[slot]
    page_path = os.path.join(assets_dir, region["page"])

    # ── 真值遮罩:真實 atlas region alpha(藝術家 mesh 就建在這張上)——**共同評分基準**。
    #    ⚠️ 公平性關鍵(2026-08-14):生成 mesh 必須也建在「同一張 region alpha」上。若改在
    #    PSD 切件(0.70 縮放前)上生成再對 region 評分,件↔region 羽化差(alpha-IoU 0.92–0.99)
    #    會注入 ~5% 假性 gap。PSD→件 連結另以 psd↔region IoU 佐證(見下),非評分基準。
    from atlas_crop import extract
    sub = extract(atlas_path, page_path, slot)
    alpha = (sub[:, :, 3] > 8).astype(np.uint8) if sub.ndim == 3 else (sub > 8).astype(np.uint8)
    H, W = alpha.shape
    region_png = os.path.join(tmp_dir, f"_region_{layer}.png")
    cv2.imwrite(region_png, sub)

    # ── artist mesh(weighted):setup 形狀從 uvs → region 局部 還原(u*W, v*H)
    art_pts = uv_to_local(att["uvs"], W, H)
    art_mask = render_from_pts(art_pts, att["triangles"], W, H)
    art_iou = iou(art_mask, alpha)  # 兼作 UV→local 映射正確性自檢(應偏高)

    # ── 生成 mesh:S3 跑真實 region alpha(公平共同遮罩)
    if eps is None:
        gen = gen_v2(region_png, mode="auto")
    else:  # 明確 epsilon(大面積平滑件需較細邊界取樣)→ 走 v1
        from generate_mesh import generate as gv1
        gen, _ = gv1(region_png, epsilon_frac=eps)
        gen["_mode"] = f"delaunay-v1(eps={eps})"
    gen_mask = render_mesh_mask(gen, W, H)
    gen_iou = iou(gen_mask, alpha)
    fmt = evaluate(gen, alpha)["criteria"]["AC4_format"]["pass"]

    # ── PSD→件 連結佐證:PSD 切件 resize 到 region 尺寸,alpha-IoU(確認同素材)
    im, entry = psd_part_alpha(psd_parts_dir, layer)
    psd_alpha = (np.array(im.resize((W, H), Image.BILINEAR).split()[-1]) > 8).astype(np.uint8)
    psd_link_iou = iou(psd_alpha, alpha)

    if fig_dir:
        os.makedirs(fig_dir, exist_ok=True)
        rgb = np.zeros((H, W, 3), np.uint8)
        rgb[..., 1] = alpha * 90                 # 綠 = 真實 region alpha
        rgb[..., 2] = art_mask * 160             # 藍 = artist mesh
        rgb[..., 0] = gen_mask * 160             # 紅 = 生成 mesh
        cv2.imwrite(os.path.join(fig_dir, f"cmp_{layer}.png"), rgb)

    return {
        "layer": layer, "slot": slot, "region_rotate": region.get("rotate", "false"),
        "atlas_region_size": [W, H], "psd_part_size": entry["size"],
        "psd_link_iou": round(psd_link_iou, 4),  # PSD 件 ↔ atlas region 同素材佐證
        "artist": {"vertices": len(att["uvs"]) // 2, "triangles": len(att["triangles"]) // 3,
                   "hull": att["hull"], "weighted": len(att["vertices"]) != len(att["uvs"]),
                   "iou": round(art_iou, 4)},
        "generated": {"vertices": len(gen["uvs"]) // 2, "triangles": len(gen["triangles"]) // 3,
                      "hull": gen["hull"], "mode": gen.get("_mode"), "iou": round(gen_iou, 4),
                      "format_ok": bool(fmt)},
        "iou_delta": round(gen_iou - art_iou, 4),
        "mapping_selfcheck_pass": bool(art_iou >= 0.80),  # UV→local 映射可信門檻
        "pass": bool(gen_iou >= art_iou - margin and fmt and art_iou >= 0.80),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--assets", default="assets")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--fig", default=None)
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--eps", type=float, default=None,
                    help="明確 epsilon_frac(走 v1);省略則用 generate_mesh_v2 auto 預設")
    a = ap.parse_args()

    # 切 PSD 件(若尚未切)
    if not os.path.exists(os.path.join(a.parts_dir, "manifest.json")):
        from psd_slice import slice_psd
        slice_psd(a.psd, a.parts_dir)

    sk = json.load(open(a.award))
    regions = parse_atlas(a.atlas)
    reps = [compare_one(sk, regions, a.atlas, a.assets, a.parts_dir, layer,
                        a.tmp, a.fig, a.margin, a.eps) for layer in MESH_PARTS]
    overall = all(r["pass"] for r in reps)
    out = {"overall_pass": overall, "n_parts": len(reps), "parts": reps}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
