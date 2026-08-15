#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 生成 mesh → 對照「真實生產 spine」的藝術家 mesh(ground truth)。

這是 S3+S4 串起來、對**真實生產標的**的整合閘(不再是合成 fixture,也不再只對
main_draw 內部一致比對):
  分層 PSD 的每個 mesh 件  ──psd_slice──▶  緊湊 PNG(alpha)
                                          │
                                          ├─ generate_mesh_v2 ─▶ 生成 mesh
                                          │
  真實 spine(assets/Award.json)藝術家手做 mesh  ── ground truth ──┐
                                                                     ▼
  對「同一張 PSD alpha」渲染兩者三角形,量 coverage IoU、頂點/三角/hull 預算、格式合法性。

★ 為何用 coverage IoU 當 ground-truth 指標(而非 deform 閘):
  機器人這幾件在 Award 是 **weighted(骨骼權重驅動)且無 deform timeline**
  (見 knowledge/s4-psd-to-spine-real.md)。它們靠骨骼變形,不是逐頂點 deform,
  所以「真實位移場轉移」閘對它們 N/A。可比的真值是「藝術家 mesh 對自身素材的覆蓋率」。

★ 判定(每件):
  1. AC_coverage:gen_iou >= artist_iou - margin(margin 預設 0.02,吸收 PSD↔atlas 跨源
     取樣/0.70 縮放/羽化邊 的 ~1–2% 雜訊,見 s4-psd-to-spine-real 的 alpha-IoU 0.92~0.99)。
  2. AC_budget:生成頂點數 <= 藝術家頂點數(不能用更多頂點換覆蓋率;要「同覆蓋、更精簡」)。
  3. AC_format:evaluate_mesh 的格式檢查(unweighted 合法、hull-first、三角索引在界內)。

★ 評估器可信度(內建雙保險):
  - 正對照:藝術家 mesh 對自身 PSD 素材的 IoU(應該高,~0.95;是低多邊形逼近曲線輪廓的自然上限)。
  - 負對照:同一藝術家 mesh 但 y 翻轉(uv_y→1-uv_y)→ IoU 應大幅崩掉,證明指標對「錯位」有鑑別力。

用法:
  python3 tools/mesh_gen/validate_psd_mesh_vs_spine.py \
      --psd assets/robot_parts.psd --spine assets/Award.json --prefix 機器人拆件
"""
import argparse, json, os, sys, tempfile
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh, load_mask as load_alpha


def load_spine_attachments(spine_path):
    sk = json.load(open(spine_path))
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)


def render_triangles(uvs, tris, W, H):
    """把 region-local uvs(0..1)× (W,H) 的三角形填成遮罩。"""
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def validate_piece(zh, png_path, art_attach, margin):
    mask = load_alpha(png_path)          # 0/1 alpha at PSD full-res
    H, W = mask.shape

    # --- 藝術家 mesh(ground truth) ---
    uvs = np.array(art_attach["uvs"]).reshape(-1, 2)
    tris = np.array(art_attach["triangles"]).reshape(-1, 3)
    art_nv = len(uvs)
    art_recon = render_triangles(uvs, tris, W, H)
    art_iou = iou(art_recon, mask)
    # 負對照:y 翻轉應崩掉
    uvs_flip = uvs.copy(); uvs_flip[:, 1] = 1.0 - uvs_flip[:, 1]
    art_iou_flip = iou(render_triangles(uvs_flip, tris, W, H), mask)

    # --- 生成 mesh ---
    mesh = gen_v2(png_path, mode="auto")
    rep = eval_mesh(mesh, mask, vertex_budget=max(art_nv, 64))
    gen_iou = rep["criteria"]["AC1_iou"]["value"]
    gen_nv = rep["vertices"]

    ac_cov = gen_iou >= art_iou - margin
    ac_bud = gen_nv <= art_nv
    ac_fmt = rep["criteria"]["AC4_format"]["pass"]
    # 評估器可信度:藝術家自身覆蓋率夠高、且負對照(翻轉)明顯崩掉
    trust = (art_iou >= 0.85) and (art_iou - art_iou_flip >= 0.15)

    return {
        "piece": zh,
        "mask": [W, H],
        "gen": {"mode": mesh.get("_mode"), "iou": round(gen_iou, 4),
                "vertices": gen_nv, "triangles": rep["triangles"], "hull": mesh["hull"]},
        "artist": {"iou": round(art_iou, 4), "iou_flipY_negctrl": round(art_iou_flip, 4),
                   "vertices": art_nv, "triangles": len(tris), "hull": art_attach.get("hull")},
        "AC_coverage": {"pass": bool(ac_cov), "gen_iou": round(gen_iou, 4),
                        "artist_baseline": round(art_iou, 4), "margin": margin,
                        "delta": round(gen_iou - art_iou, 4)},
        "AC_budget": {"pass": bool(ac_bud), "gen_nv": gen_nv, "artist_nv": art_nv,
                      "vertex_saving_pct": round(100.0 * (art_nv - gen_nv) / art_nv, 1)},
        "AC_format": {"pass": bool(ac_fmt)},
        "evaluator_trust": {"pass": bool(trust), "artist_self_iou": round(art_iou, 4),
                            "negctrl_flipY_iou": round(art_iou_flip, 4)},
        "piece_pass": bool(ac_cov and ac_bud and ac_fmt and trust),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--spine", default="assets/Award.json")
    ap.add_argument("--prefix", default="機器人拆件",
                    help="spine slot 命名前綴 = <PSD檔名 namespace>;slot = <prefix>/<圖層名>")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()

    att = load_spine_attachments(a.spine)
    tmp = tempfile.mkdtemp(prefix="psd_pieces_")
    _, _, parts = slice_psd(a.psd, tmp)
    part_png = {e["name"]: os.path.join(tmp, e["file"]) for e, _ in parts}

    reports = []
    for name, png in part_png.items():
        slot = f"{a.prefix}/{name}"
        art = att.get(slot, {}).get(slot)
        if not art or art.get("type") != "mesh":
            continue  # 只驗真實 spine 中被做成 mesh 的件
        reports.append(validate_piece(name, png, art, a.margin))

    overall = bool(reports) and all(r["piece_pass"] for r in reports)
    out = {"psd": os.path.basename(a.psd), "spine": os.path.basename(a.spine),
           "prefix": a.prefix, "mesh_pieces": len(reports),
           "overall_pass": overall, "pieces": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
