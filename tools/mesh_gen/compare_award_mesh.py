#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 mesh 生成 → 對照 Award 真實生產 mesh(靜態拓樸/覆蓋)。

STATE.md 最高優先 bounded chunk:用 robot_parts.psd 的機器人 mesh 件(光暈/左手/身體,
在 Award 中為 mesh)跑 generate_mesh_v2,與 Award 真實 mesh 做覆蓋 IoU / 頂點預算對照。

⚠️ 這 3 件在 Award 全部動畫中 **無 deform timeline**(靜態 weighted mesh,只靠骨變形),
   故沒有「真實位移場」可轉移 → 本閘為**靜態**對照(覆蓋 + 預算),deform 閘 N/A(誠實標註)。

⚠️ 校正(2026-07-21,本 session 實測):Award mesh uvs **其實是 region 局部 [0,1]**(非 atlas 全頁
   UV,STATE 舊註記有誤)。直接 uvs*(W,H) 落在 atlas_crop 切出的 region-local upright 圖上即對齊
   (rotate 件也對齊 → 反證 atlas_crop 的 CW derotation 正確)。u 上翻(flip)會崩到 ~0.5,故不翻。

自檢(負對照精神):藝術家 mesh 依定義覆蓋素材輪廓 → 對齊正確時其 region-local 覆蓋 IoU 必高
   (實測 3 件 0.97~0.98)。若對齊/rotation 錯,此值崩落。故 artist_iou≥0.9 即對齊正確之證據。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from psd_tools import PSDImage
from atlas_crop import parse_atlas, extract
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh, load_mask as load_mask_arr

PAGE = {"Award.png": (2040, 2040), "Award2.png": (1780, 1376)}


def psd_piece_alpha(psd_path, layer_name, out_png):
    psd = PSDImage.open(psd_path)
    for l in psd.descendants():
        if not l.is_group() and l.is_visible() and l.name == layer_name:
            im = l.topil().convert("RGBA")
            im.save(out_png)
            return out_png
    raise SystemExit(f"PSD 無此圖層: {layer_name}")


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    a = atts[slot][name]
    uvs = np.array(a["uvs"], float).reshape(-1, 2)
    tris = np.array(a["triangles"], int).reshape(-1, 3)
    return uvs, tris


def uv_to_region_local(uvs, img_w, img_h):
    """Award mesh uvs 為 region 局部 [0,1] → 落到 region-local upright 圖(atlas_crop 產出)的像素。
    無需 Y 翻轉(實測 flip 會崩到 ~0.5);rotate 件靠 atlas_crop 已 derotate 至 upright。"""
    return np.column_stack([uvs[:, 0] * img_w, uvs[:, 1] * img_h])


def coverage_iou(pts_xy, tris, mask):
    """把三角形 rasterize 到 mask 尺寸,算與 alpha 的 IoU。"""
    H, W = mask.shape
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts_xy[t]).astype(np.int32)
        cv2.fillConvexPoly(recon, poly, 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / max(union, 1)), recon


PIECES = [
    # (psd_layer, award_slot/name)
    ("光暈", "機器人拆件/光暈"),
    ("左手", "機器人拆件/左手"),
    ("身體", "機器人拆件/身體"),
]


def run(psd_path, skel_path, atlas_path, tmp="/tmp", margin=0.03):
    sk = json.load(open(skel_path))
    reg = parse_atlas(atlas_path)
    report = {"pieces": [], "note": "robot mesh pieces have NO deform timeline in Award; static-only comparison"}
    for layer, an in PIECES:
        r = reg[an]
        page_png = os.path.join(os.path.dirname(atlas_path), r["page"])

        # --- 我方 pipeline:PSD 件 → S3 mesh → 覆蓋 IoU(over PSD alpha) ---
        piece_png = os.path.join(tmp, f"psd_{layer}.png")
        psd_piece_alpha(psd_path, layer, piece_png)
        my_mask = load_mask_arr(piece_png)
        # 覆蓋自收斂:大柔邊件(光暈)預設 epsilon 過粗,evaluator 驅動加密邊界至達標
        my_mesh = gen_v2(piece_png, mode="auto", refine_coverage=True, target_iou=0.95, budget=64)
        my_ev = eval_mesh(my_mesh, my_mask)
        my_iou = my_ev["criteria"]["AC1_iou"]["value"]
        my_degen = my_ev["criteria"]["AC2b_degenerate"]["value"]
        my_orphan = my_ev["criteria"]["AC2c_orphans"]["value"]
        my_nv = len(my_mesh["uvs"]) // 2

        # --- 藝術家 mesh:region-local uvs 覆蓋 IoU(over atlas region alpha) ---
        sub = extract(atlas_path, page_png, an)          # region-local 上正圖 (h,w)
        reg_alpha = (sub[:, :, 3] > 8).astype(np.uint8) if sub.ndim == 3 and sub.shape[2] == 4 else (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)
        Himg, Wimg = reg_alpha.shape
        uvs, tris = artist_mesh(sk, an, an)
        art_pts = uv_to_region_local(uvs, Wimg, Himg)
        art_iou, _ = coverage_iou(art_pts, tris, reg_alpha)
        art_iou = round(art_iou, 4)
        art_nv = len(uvs)

        report["pieces"].append({
            "piece": layer, "award": an,
            "rotate": r.get("rotate", "false"),
            "atlas_size": r["size"], "psd_alpha_px": [int(my_mask.shape[1]), int(my_mask.shape[0])],
            "mine": {"mode": my_mesh.get("_mode"), "vertices": my_nv,
                     "triangles": len(my_mesh["triangles"]) // 3,
                     "coverage_iou": round(my_iou, 4),
                     "degenerate": my_degen, "orphans": my_orphan,
                     "refine": my_mesh.get("_refine")},
            "artist": {"vertices": art_nv, "triangles": len(tris),
                       "coverage_iou": art_iou},
            "vertex_ratio_mine_over_artist": round(my_nv / art_nv, 3),
            "AC_coverage_parity": my_iou >= art_iou - margin,
            "AC_clean_topology": my_degen == 0 and my_orphan == 0,
            "AC_artist_alignment_sane": art_iou >= 0.9,  # 自檢:對齊正確則藝術家覆蓋必高
        })
    report["overall_pass"] = all(
        p["AC_coverage_parity"] and p["AC_clean_topology"] and p["AC_artist_alignment_sane"]
        for p in report["pieces"])
    return report


if __name__ == "__main__":
    rep = run("assets/robot_parts.psd", "assets/Award.json", "assets/Award.atlas",
              tmp=os.environ.get("TMPDIR", "/tmp"))
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)
