#!/usr/bin/env python3
"""端到端 AC:PSD 圖層件 → S3 generate_mesh_v2 → 對照真實生產 spine mesh(靜態覆蓋)。

這是把 S4(切圖)與 S3(mesh 生成)串成端到端、並對「真實生產標的」驗收的整合閘。
資料鏈:`robot_parts.psd`(機器人拆件)→ psd_slice 切件 →(每個 mesh 件)generate_mesh_v2
        → 覆蓋率 IoU / 拓樸 / 頂點預算,對照 `Award.json` 中同名 slot 的**真實藝術家 mesh**。

為何用「靜態覆蓋」而非 deform 閘(重要,記取):
  這 3 件在 Award 是 **weighted mesh(骨骼驅動)且無 deform timeline**(見
  knowledge/s4-psd-to-spine-real.md)。沒有真實逐頂點位移場可轉移,依 RULES 不得用
  未校準的 stress_field 下 pass/fail → 本閘只判「靜態覆蓋 + 拓樸乾淨 + 頂點預算」,
  不對這些件下 deform 判定(unweighted + 有 deform 的窗簾件由 validate_against_real.py 管)。

座標對齊(已實測校正,2026-07-15):
  Award mesh 的 `uvs` 為 **region-local 0..1**(非 atlas-page),y 與影像同向(y-down),
  無需 flip;直接 uvs×(pieceW,pieceH) 疊在 psd_slice 切件 alpha 上 → 藝術家自身覆蓋率
  0.948/0.948/0.977。負對照:任一軸 flip 掉到 0.40–0.61,證明此覆蓋率量測有鑑別力。

AC(逐件):
  ① AC_iou       : gen 覆蓋率 IoU ≥ 藝術家 mesh 覆蓋率 − margin(預設 margin=0)。
  ② AC_topology  : 0 退化三角 / 0 孤兒頂點 / 三角索引合法(setup pose)。
  ③ AC_budget    : gen 頂點數 ≤ budget(預設對齊藝術家頂點數 ×1.25)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate

# 機器人拆件:PSD 圖層名 ⇄ Award spine slot(見 knowledge/s4-psd-to-spine-real.md)
DEFAULT_MESH_MAP = {"光暈": "機器人拆件/光暈", "身體": "機器人拆件/身體", "左手": "機器人拆件/左手"}


def artist_mesh(skeleton, slot, name=None):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)[slot]
    name = name or (slot if slot in atts else next(iter(atts)))
    a = atts[name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return uvs, tris


def coverage_iou(uvs, tris, mask, flip=None):
    """region-local uvs 疊在 mask 上的覆蓋率 IoU。flip in {None,'x','y'} 供負對照。"""
    H, W = mask.shape
    u = uvs.copy()
    if flip == "x":
        u[:, 0] = 1 - u[:, 0]
    elif flip == "y":
        u[:, 1] = 1 - u[:, 1]
    rp = np.column_stack([u[:, 0] * W, u[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return inter / union if union else 0.0


def validate_piece(piece_img, skeleton, slot, epsilon, margin, budget_factor):
    mask = (piece_img[:, :, 3] > 8).astype(np.uint8) if piece_img.shape[2] == 4 \
        else (cv2.cvtColor(piece_img, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8)

    # 藝術家真實 mesh 覆蓋率 + 負對照(鑑別力)
    a_uvs, a_tris = artist_mesh(skeleton, slot)
    base = coverage_iou(a_uvs, a_tris, mask)
    neg = max(coverage_iou(a_uvs, a_tris, mask, "x"), coverage_iou(a_uvs, a_tris, mask, "y"))
    artist_nv = len(a_uvs)
    budget = int(round(artist_nv * budget_factor))

    # 生成 mesh(auto:blob 件走 v1 Delaunay;epsilon 控制邊界保真)
    tmp = "/tmp/_ptm_piece.png"
    cv2.imwrite(tmp, piece_img)
    from generate_mesh import generate as gv1
    mesh = gen_v2(tmp, mode="auto")
    if mesh.get("_mode") == "delaunay-v1":
        mesh = gv1(tmp, epsilon_frac=epsilon)[0]
        mesh["_mode"] = f"delaunay-v1(eps={epsilon})"

    ev = evaluate(mesh, mask, vertex_budget=budget, iou_thresh=0.0)
    gi = ev["criteria"]["AC1_iou"]["value"]
    nv = ev["vertices"]
    topo_ok = (ev["criteria"]["AC2b_degenerate"]["pass"]
               and ev["criteria"]["AC2c_orphans"]["pass"]
               and ev["criteria"]["AC4_format"]["pass"])

    ac_iou = gi >= base - margin
    ac_budget = nv <= budget
    return {
        "slot": slot,
        "mesh": {"mode": mesh.get("_mode"), "vertices": nv, "triangles": ev["triangles"],
                 "hull": mesh["hull"]},
        "AC_iou": {"gen": round(gi, 4), "artist_baseline": round(base, 4),
                   "negative_control_flip": round(neg, 4), "margin": margin,
                   "pass": ac_iou},
        "AC_topology": {"degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                        "orphans": ev["criteria"]["AC2c_orphans"]["value"],
                        "format_ok": ev["criteria"]["AC4_format"]["pass"], "pass": topo_ok},
        "AC_budget": {"vertices": nv, "artist_vertices": artist_nv, "budget": budget,
                      "pass": ac_budget},
        "overall_pass": ac_iou and topo_ok and ac_budget,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--epsilon", type=float, default=0.002,
                    help="v1 Douglas-Peucker 邊界簡化係數(細緻件 0.002 對齊藝術家覆蓋率)")
    ap.add_argument("--margin", type=float, default=0.0)
    ap.add_argument("--budget-factor", type=float, default=1.25)
    a = ap.parse_args()

    sk = json.load(open(a.skeleton))
    _, _, parts = slice_psd(a.psd)
    by_name = {e["name"]: im for e, im in parts}

    reports = []
    for layer, slot in DEFAULT_MESH_MAP.items():
        if layer not in by_name:
            reports.append({"slot": slot, "error": f"PSD 無圖層 {layer}", "overall_pass": False})
            continue
        img = np.array(by_name[layer])[:, :, ::-1] if False else \
            cv2.cvtColor(np.array(by_name[layer]), cv2.COLOR_RGBA2BGRA)
        reports.append(validate_piece(img, sk, slot, a.epsilon, a.margin, a.budget_factor))

    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "epsilon": a.epsilon,
                      "note": "weighted/bone-driven, no deform timeline → 靜態覆蓋閘(不下 deform 判定)",
                      "pieces": reports}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
