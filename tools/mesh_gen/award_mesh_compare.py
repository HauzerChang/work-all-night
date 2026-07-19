#!/usr/bin/env python3
"""S3×S4 端到端驗收 — 真實生產 PSD 件 → generate_mesh_v2 → 對照 Award 真實 mesh。

背景(knowledge/s4-psd-to-spine-real.md):`robot_parts.psd`(機器人拆件)5 圖層 ⇄ 生產
spine `Award` 的 slot `機器人拆件/<圖層名>`。其中 3 件在 Award 是 **mesh**:
  光暈(78v/76t/hull78,純 boundary ring)、身體(98v/154t/hull40)、左手(80v/116t/hull42)。

本工具把「PSD 件 → S3 mesh」對這 3 件跑通,並與 Award 藝術家 mesh 做量化對照。

⚠️ 兩個關鍵事實決定了對照方法(不要用錯):
  (1) 這 3 件在 Award 是 **weighted mesh 且無 deform timeline** —— 靠骨骼/權重變形,
      不是逐頂點 deform。故 S3 的「真實位移場 deform 閘」在此**不適用**;正確的閘是
      **靜態輪廓覆蓋率 + 拓樸健全 + 頂點預算**(對照藝術家的實際出貨規格)。
  (2) Award atlas region 有旋轉(光暈/身體 rotate:true)且縮小打包(~0.70),藝術家 mesh
      vertices 是 weighted 攤平格式、uvs 是 atlas UV。要把藝術家 mesh 對到「件」的像素空間,
      **不靠 atlas 幾何**(那正是專案踩過的 derotate 方向雷),改用:把藝術家 mesh 的 uvs
      正規化到自身 bbox → 對「件 alpha」(全解析度原始美術、無旋轉=真值)試 8 個二面體擺放,
      取 IoU 最高者當藝術家覆蓋基準。這是自校準對齊,honest 且避開旋轉歧義。

真值來源:PSD 件 alpha(原始美術,無縮放無旋轉)。

用法:
  python3 tools/mesh_gen/award_mesh_compare.py                 # 跑 3 件、印報告、exit 0/1
  python3 tools/mesh_gen/award_mesh_compare.py --dump /tmp/out # 另存件 alpha + gen mesh JSON
"""
import argparse, json, os, re, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh

# 靜態輪廓覆蓋率絕對閘:main_draw 藝術家 mesh 的輪廓覆蓋約 0.91-0.92
# (curtain_left 0.918,見 knowledge/s3-four-mesh-generalization.md);取 0.90 為 gen 覆蓋門檻。
COVERAGE_MIN = 0.90

# PSD 圖層名 → Award slot(= slot 同名 attachment)。只列 Award 中為 mesh 的 3 件。
MESH_PIECES = ["光暈", "身體", "左手"]
ART_STATS = {  # Award 藝術家 mesh 出貨規格(ground truth,見上方 docstring)
    "光暈": {"verts": 78, "tris": 76, "hull": 78},
    "身體": {"verts": 98, "tris": 154, "hull": 40},
    "左手": {"verts": 80, "tris": 116, "hull": 42},
}


def award_mesh(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][slot]


def atlas_rotate(atlas_path, region):
    """該 region 在 atlas 是否旋轉打包(決定 uv→件像素對齊是否可信)。"""
    txt = open(atlas_path).read()
    i = txt.find(region)
    if i < 0:
        return None
    m = re.search(r"rotate:\s*(true|false)", txt[i:i + 120])
    return m.group(1) == "true" if m else None


def _fill(tris_xy, W, H):
    m = np.zeros((H, W), np.uint8)
    for t in tris_xy:
        cv2.fillConvexPoly(m, np.round(t).astype(np.int32), 1)
    return m


# 8 個二面體(正方形對稱群)對 (u,v) in [0,1] 的變換
def _dihedral(uv, k):
    u, v = uv[:, 0], uv[:, 1]
    variants = [
        (u, v), (1 - u, v), (u, 1 - v), (1 - u, 1 - v),          # 0/180 + flips
        (v, u), (1 - v, u), (v, 1 - u), (1 - v, 1 - u),          # 90/270 + flips
    ][k]
    return np.column_stack(variants)


def artist_coverage(art, piece_mask):
    """藝術家 mesh 對「件 alpha」的最佳擺放覆蓋率(自校準旋轉/翻轉)。回傳 (iou, orient)。

    ⚠️ 僅對 **rotate:false** 的 region 可信(uv 軸對齊件像素軸)。rotate:true 時 uv 空間受
    atlas 90° 旋轉 + page 長寬比糾纏,dihedral 剛體擺放無法對齊(實測 身體 IoU 卡 0.64、
    綠恤紅偏斜,見 log)。故本值標為 informational,不當 pass/fail 閘;閘用 gen 的絕對覆蓋。"""
    H, W = piece_mask.shape
    uvs = np.array(art["uvs"]).reshape(-1, 2)
    tris = np.array(art["triangles"]).reshape(-1, 3)
    u0, v0 = uvs.min(0); u1, v1 = uvs.max(0)
    norm = (uvs - [u0, v0]) / [max(u1 - u0, 1e-9), max(v1 - v0, 1e-9)]
    best = (-1.0, -1)
    for k in range(8):
        d = _dihedral(norm, k)
        px = np.column_stack([d[:, 0] * (W - 1), d[:, 1] * (H - 1)])
        recon = _fill([px[t] for t in tris], W, H)
        inter = np.logical_and(recon, piece_mask).sum()
        union = np.logical_or(recon, piece_mask).sum()
        iou = float(inter / union) if union else 0.0
        if iou > best[0]:
            best = (iou, k)
    return best


def run(psd_path="assets/robot_parts.psd", award_path="assets/Award.json",
        atlas_path="assets/Award.atlas", budget=64, coverage_min=COVERAGE_MIN, dump=None):
    sk = json.load(open(award_path))
    _, _, parts = slice_psd(psd_path)
    by_name = {e["name"]: im for e, im in parts}
    if dump:
        os.makedirs(dump, exist_ok=True)

    rows = []
    for name in MESH_PIECES:
        im = by_name[name].convert("RGBA")
        alpha = (np.array(im.split()[-1]) > 8).astype(np.uint8)
        H, W = alpha.shape
        # 存件 alpha 給 generate(它讀檔),用 RGBA 保留 alpha 通道
        tmp = os.path.join(dump or "/tmp", f"_piece_{name}.png")
        cv2.imwrite(tmp, np.dstack([np.array(im)[:, :, 2::-1], np.array(im.split()[-1])]))

        gen = gen_v2(tmp, mode="auto")
        gev = eval_mesh(gen, alpha, vertex_budget=budget)
        gen_iou = gev["criteria"]["AC1_iou"]["value"]
        fmt_ok = (gev["criteria"]["AC4_format"]["pass"]
                  and gev["criteria"]["AC2b_degenerate"]["pass"]
                  and gev["criteria"]["AC2c_orphans"]["pass"])

        art = award_mesh(sk, f"機器人拆件/{name}")
        art_iou, orient = artist_coverage(art, alpha)
        rot = atlas_rotate(atlas_path, f"機器人拆件/{name}")

        a = ART_STATS[name]
        nv = len(gen["uvs"]) // 2
        row = {
            "piece": name, "piece_px": [W, H],
            "gen": {"mode": gen.get("_mode"), "verts": nv,
                    "tris": len(gen["triangles"]) // 3, "hull": gen["hull"],
                    "iou": round(gen_iou, 4)},
            "artist": {"verts": a["verts"], "tris": a["tris"], "hull": a["hull"]},
            # 對照 Award 真實 mesh 的兩個「可信」量:①gen 靜態覆蓋(絕對閘)②頂點預算 vs 藝術家
            "AC_coverage": {"pass": gen_iou >= coverage_min, "value": round(gen_iou, 4),
                            "thresh": coverage_min},
            "AC_vertex_budget": {"pass": nv <= budget,
                                 "gen_v_vs_artist": f"{nv}/{a['verts']}",
                                 "ratio": round(nv / a["verts"], 2)},
            "AC_format": {"pass": fmt_ok},
            # informational:藝術家 mesh 對件的覆蓋(僅 rotate:false 可信,見 artist_coverage docstring)
            "_artist_iou_on_piece": {"value": round(art_iou, 4), "orient": orient,
                                     "atlas_rotate": rot, "reliable": rot is False},
        }
        row["piece_pass"] = (row["AC_coverage"]["pass"]
                             and row["AC_vertex_budget"]["pass"] and fmt_ok)
        rows.append(row)
        if dump:
            json.dump(gen, open(os.path.join(dump, f"gen_{name}.json"), "w"),
                      ensure_ascii=False)

    return {"overall_pass": all(r["piece_pass"] for r in rows), "pieces": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--coverage-min", type=float, default=COVERAGE_MIN)
    ap.add_argument("--dump", default=None)
    a = ap.parse_args()
    rep = run(a.psd, a.award, a.atlas, a.budget, a.coverage_min, a.dump)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
