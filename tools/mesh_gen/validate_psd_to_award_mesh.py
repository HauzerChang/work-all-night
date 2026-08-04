#!/usr/bin/env python3
"""端到端驗證:PSD件 → S3 generate_mesh_v2 → 對照 Award 真實 mesh(靜態)。

背景(見 knowledge/s4-psd-to-spine-real.md):Award 機器人拆件的 3 件 mesh
(光暈/身體/左手)在生產 spine 是 **weighted mesh**,且**無 deform timeline**
(靠骨骼權重變形,非逐頂點 deform)。因此:
  - 這是 S3 對「加權、非 strip(低長寬比)真實生產 mesh」的**推廣測試**
    (先前 4 mesh 全是 unweighted 窗簾/影子)。
  - 動畫不做逐頂點 deform → 不套用 transfer_deform_check(不捏造 deform 閘,誠實)。
    靜態剛體/仿射 bone deform 不會使拓樸自交,故有意義的閘是:
    ① 覆蓋率 IoU vs 藝術家 mesh ② 頂點預算 vs 藝術家 ③ setup 拓樸有效性。

藝術家 mesh 參考幀:Spine JSON 的 mesh `uvs` 是 **region-local 0..1**(經驗證:對 Award
3 件用 `uv*[Wc,Hc]` 直接填三角形,self-IoU 0.97~0.98 → 與 atlas_crop 上正裁切件完全同幀)。
故直接把藝術家三角形填到裁切件尺寸的畫布,不需 atlas 頁面座標推導。以 self-IoU(≥0.85)自我校驗。

輸入來源:
  - Award mesh 遮罩:atlas 裁切件 alpha(atlas_crop.extract,已校正 CW+多頁)。
  - PSD 端到端 sanity:psd_slice 切件 alpha(原始解析度,~1/0.70 尺度)。
用法:python3 tools/mesh_gen/validate_psd_to_award_mesh.py
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import parse_atlas, crop_region
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_static
import deform_eval as de

# Award 3 mesh 件:slot 名 == attachment 名;PSD robot_parts 對應圖層名
MESH_PIECES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]
PSD_LAYER = {"機器人拆件/光暈": "光暈", "機器人拆件/身體": "身體", "機器人拆件/左手": "左手"}


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return uvs, tris, a["hull"]


ORIENTS = {"u,v": (1, 1, False), "u,1-v": (1, -1, False),
           "1-u,v": (-1, 1, False), "1-u,1-v": (-1, -1, False)}


def rasterize_artist(uvs, tris, Wc, Hc, orient):
    """region-local uv → 裁切件像素填三角形(orient=翻轉組合,自校驗用)。"""
    su, sv, _ = ORIENTS[orient]
    uu = uvs[:, 0] if su == 1 else 1.0 - uvs[:, 0]
    vv = uvs[:, 1] if sv == 1 else 1.0 - uvs[:, 1]
    pts = np.column_stack([uu * Wc, vv * Hc])
    canvas = np.zeros((Hc, Wc), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(canvas, np.round(pts[t]).astype(np.int32), 1)
    return (canvas > 0).astype(np.uint8)


def iou(a, b):
    a = a > 0; b = b > 0
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def static_topology(mesh):
    """setup pose 拓樸有效性(自交/退化);setup_signs=None → 不算 flip。"""
    from evaluate_mesh import mesh_pixel_coords
    pts, _, _ = mesh_pixel_coords(mesh)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    r = de.check(pts, tris, None)
    return r


def validate_piece(sk, atlas_path, slot, psd_alpha, tmp_dir):
    regions = parse_atlas(atlas_path)
    region = regions[slot]
    page = region["page"]
    page_png = os.path.join(os.path.dirname(atlas_path), page)

    # ① Award 貼圖裁切件 alpha(真實貼圖幀)
    sheet = cv2.imread(page_png, cv2.IMREAD_UNCHANGED)
    crop = crop_region(sheet, region)
    alpha = (crop[:, :, 3] > 8).astype(np.uint8) if crop.ndim == 3 and crop.shape[2] == 4 \
        else (cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)
    Hc, Wc = alpha.shape
    crop_png = os.path.join(tmp_dir, "_award_crop.png")
    cv2.imwrite(crop_png, crop)

    # ② 藝術家 mesh(region-local uv)→ crop 幀遮罩(試 4 種翻轉,取高 self-IoU)
    uvs, tris, hull = artist_mesh(sk, slot, slot)
    cands = {o: rasterize_artist(uvs, tris, Wc, Hc, o) for o in ORIENTS}
    orient = max(cands, key=lambda o: iou(cands[o], alpha))
    artist_mask = cands[orient]
    artist_self_iou = iou(artist_mask, alpha)
    artist_nv = len(uvs)

    # 藝術家 uv 空間拓樸(sanity:真實 mesh 應乾淨)
    au = np.column_stack([uvs[:, 0], uvs[:, 1]])
    art_topo = de.check(au, tris, None)

    # ③ S3 generate_mesh_v2 對 Award 裁切件;覆蓋率不足時,自我迭代加密邊界取樣
    #    (RULES 自我驗證迴圈,≤5 輪;strip 模式 epsilon 無效即回退預設一輪)
    margin = 0.02
    budget_factor = 1.3
    budget = int(np.ceil(budget_factor * len(uvs)))
    EPS_SCHEDULE = [None, 0.005, 0.003, 0.002, 0.0015]  # None=生成器預設(0.008)
    refine = []
    gmesh = None
    for eps in EPS_SCHEDULE:
        m = gen_v2(crop_png, mode="auto", epsilon_frac=eps)
        nv = len(m["uvs"]) // 2
        io = eval_static(m, alpha, vertex_budget=256)["criteria"]["AC1_iou"]["value"]
        refine.append({"epsilon": eps, "nv": nv, "iou": io})
        gmesh = m
        if io >= artist_self_iou - margin and nv <= budget:
            break
        if m.get("_mode") == "strip":  # strip 不吃 epsilon,不必再試
            break
    gen_nv = len(gmesh["uvs"]) // 2
    iou_gen_crop = refine[-1]["iou"]
    gtopo = static_topology(gmesh)

    # ④ 端到端 PSD sanity:對 PSD 切件跑同一生成器
    psd_iou = None
    psd_nv = None
    psd_mode = None
    if psd_alpha is not None:
        psd_png = os.path.join(tmp_dir, "_psd_piece.png")
        cv2.imwrite(psd_png, psd_alpha)
        pmesh = gen_v2(psd_png, mode="auto")
        psd_nv = len(pmesh["uvs"]) // 2
        psd_mode = pmesh.get("_mode")
        pmask = (psd_alpha[:, :, 3] > 8).astype(np.uint8)
        psd_iou = eval_static(pmesh, pmask, vertex_budget=256)["criteria"]["AC1_iou"]["value"]

    ac_cover = iou_gen_crop >= artist_self_iou - margin
    ac_budget = gen_nv <= budget
    ac_valid = gtopo["self_intersections"] == 0 and gtopo["degenerate"] == 0
    ac_selfcheck = artist_self_iou >= 0.85

    return {
        "slot": slot,
        "crop_size": [Wc, Hc],
        "orient_used": orient,
        "artist": {"nv": artist_nv, "hull": hull, "tris": len(tris),
                   "self_iou_in_crop": round(artist_self_iou, 4),
                   "uv_topology": {k: art_topo[k] for k in
                                   ("self_intersections", "degenerate")}},
        "generated": {"nv": gen_nv, "hull": gmesh["hull"],
                      "tris": len(gmesh["triangles"]) // 3, "mode": gmesh.get("_mode"),
                      "epsilon_frac": refine[-1]["epsilon"], "iou_vs_alpha": iou_gen_crop,
                      "refine_rounds": len(refine), "refine_trace": refine,
                      "topology": {k: gtopo[k] for k in
                                   ("self_intersections", "degenerate")}},
        "psd_end_to_end": {"nv": psd_nv, "mode": psd_mode, "iou_vs_alpha": psd_iou},
        "AC_coverage": {"pass": bool(ac_cover), "gen": iou_gen_crop,
                        "artist_baseline": round(artist_self_iou, 4), "margin": margin},
        "AC_vertex_budget": {"pass": bool(ac_budget), "gen_nv": gen_nv,
                             "artist_nv": artist_nv, "factor": budget_factor},
        "AC_static_validity": {"pass": bool(ac_valid), **gtopo},
        "AC_selfcheck_artist_maps": {"pass": bool(ac_selfcheck),
                                     "self_iou": round(artist_self_iou, 4)},
        "overall_pass": bool(ac_cover and ac_budget and ac_valid and ac_selfcheck),
    }


def negative_control(sk, atlas_path, tmp_dir):
    """把生成 mesh 的一個 hull 頂點拉到對側 → 應觸發 self-intersection(閘鑑別力)。"""
    regions = parse_atlas(atlas_path)
    slot = MESH_PIECES[0]
    region = regions[slot]
    sheet = cv2.imread(os.path.join(os.path.dirname(atlas_path), region["page"]),
                       cv2.IMREAD_UNCHANGED)
    crop = crop_region(sheet, region)
    p = os.path.join(tmp_dir, "_neg.png"); cv2.imwrite(p, crop)
    m = gen_v2(p, mode="auto")
    v = m["vertices"][:]
    # 交換第 0 與 hull//2 個頂點的座標 → 邊必然穿插
    h = m["hull"]; j = h // 2
    v[0], v[1], v[2 * j], v[2 * j + 1] = v[2 * j], v[2 * j + 1], v[0], v[1]
    m2 = dict(m); m2["vertices"] = v
    r = static_topology(m2)
    return {"self_intersections": r["self_intersections"],
            "caught": r["self_intersections"] > 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award-json", default="assets/Award.json")
    ap.add_argument("--award-atlas", default="assets/Award.atlas")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    os.makedirs(a.tmp, exist_ok=True)
    sk = json.load(open(a.award_json))

    # PSD 切件 alpha(對應圖層名)
    psd_alphas = {}
    try:
        from psd_slice import slice_psd
        _, _, parts = slice_psd(a.psd)
        by_name = {e["name"]: im for e, im in parts}
        for slot in MESH_PIECES:
            im = by_name.get(PSD_LAYER[slot])
            psd_alphas[slot] = np.array(im.convert("RGBA"))[:, :, [2, 1, 0, 3]] if im else None
    except Exception as e:
        print(f"[warn] PSD 切件不可用: {e}", file=sys.stderr)
        for slot in MESH_PIECES:
            psd_alphas[slot] = None

    reports = []
    for slot in MESH_PIECES:
        reports.append(validate_piece(sk, a.award_atlas, slot,
                                      psd_alphas.get(slot), a.tmp))
    neg = negative_control(sk, a.award_atlas, a.tmp)

    summary = {
        "pieces": reports,
        "negative_control": neg,
        "overall_pass": all(r["overall_pass"] for r in reports) and neg["caught"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["overall_pass"] else 1)


if __name__ == "__main__":
    main()
