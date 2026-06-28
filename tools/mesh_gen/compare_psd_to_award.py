#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 生成 mesh → 對照 Award 真實(藝術家)mesh。

里程碑(2026-06-28):把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,並對**真實生產標的**
(Award spine 的機器人 mesh 件)驗收。

流程(純 CPU,不需 Award.png):
  robot_parts.psd ─psd_slice→ 件 alpha ─generate_mesh_v2→ 我的 mesh
  ↘ evaluate_mesh(我的 IoU/拓樸)
  Award.json 該 slot 的藝術家 mesh ─artist_iou(同一份件 alpha)→ 藝術家基準 IoU

AC(這些 Award mesh 皆 weighted/骨驅、**無 deform timeline** → 用靜態閘,非 deform 轉移閘):
  1. 我的 mesh 格式合法、0 退化、0 孤兒、三角重心全落在 mask 內(拓樸乾淨)。
  2. IoU parity:我的 IoU ≥ 藝術家 IoU − margin(覆蓋率不輸藝術家)。
  3. 頂點節約:我的頂點數 ≤ 藝術家頂點數。

評估器可信度:artist_iou 對「錯件 mask」的負對照 IoU 應顯著下降(見 --neg)。
"""
import argparse, json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask

# robot_parts.psd 中為 mesh 的 3 件(對照 Award slot 機器人拆件/<名>)
MESH_PIECES = {"光暈": "00_光暈.png", "身體": "03_身體.png", "左手": "04_左手.png"}


def get_attachment(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][slot]


def artist_iou(uvs, tris, mask, flip_v=False):
    H, W = mask.shape
    u = np.array(uvs).reshape(-1, 2).copy()
    if flip_v:
        u[:, 1] = 1.0 - u[:, 1]
    rp = np.column_stack([u[:, 0] * W, u[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in np.array(tris).reshape(-1, 3):
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    return float(np.logical_and(recon, m).sum() / np.logical_or(recon, m).sum())


def compare(award_json, parts_dir, margin=0.02):
    sk = json.load(open(award_json))
    rep = {}
    for nm, fn in MESH_PIECES.items():
        path = os.path.join(parts_dir, fn)
        mask = load_mask(path)
        mesh = gen_v2(path, mode="auto")
        ev = evaluate(mesh, mask, vertex_budget=128)
        my_iou = ev["criteria"]["AC1_iou"]["value"]
        my_nv = ev["vertices"]
        a = get_attachment(sk, f"機器人拆件/{nm}")
        # v 方向:取 IoU 較高者(揭示 uvs 慣例;經驗證為 flip_v=False)
        i0 = artist_iou(a["uvs"], a["triangles"], mask, False)
        i1 = artist_iou(a["uvs"], a["triangles"], mask, True)
        a_iou, flip = (i1, True) if i1 > i0 else (i0, False)
        a_nv = len(a["uvs"]) // 2
        clean = (ev["criteria"]["AC2b_degenerate"]["value"] == 0 and
                 ev["criteria"]["AC2c_orphans"]["value"] == 0 and
                 ev["criteria"]["AC2a_centroid_in_mask"]["value"] >= 0.99 and
                 ev["criteria"]["AC4_format"]["pass"])
        rep[nm] = {
            "mode": mesh.get("_mode"),
            "my": {"vertices": my_nv, "tris": ev["triangles"], "hull": mesh["hull"], "iou": round(my_iou, 4)},
            "artist": {"vertices": a_nv, "tris": len(a["triangles"]) // 3, "hull": a["hull"],
                       "iou": round(a_iou, 4), "v_flip": flip, "weighted": len(a["vertices"]) != len(a["uvs"])},
            "AC1_topology_clean": clean,
            "AC2_iou_parity": my_iou >= a_iou - margin,
            "AC3_vertex_economy": my_nv <= a_nv,
        }
        rep[nm]["overall_pass"] = all(rep[nm][k] for k in ("AC1_topology_clean", "AC2_iou_parity", "AC3_vertex_economy"))
    return rep


def negative_control(award_json, parts_dir):
    """藝術家 mesh 對『錯件 mask』→ IoU 應顯著低於 self(評估器鑑別力)。"""
    sk = json.load(open(award_json))
    masks = {nm: load_mask(os.path.join(parts_dir, fn)) for nm, fn in MESH_PIECES.items()}
    out = {}
    for nm in MESH_PIECES:
        a = get_attachment(sk, f"機器人拆件/{nm}")
        out[nm] = {tgt: round(artist_iou(a["uvs"], a["triangles"], mk), 3) for tgt, mk in masks.items()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts", default="/tmp/robot_parts", help="psd_slice 輸出目錄")
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--neg", action="store_true", help="只跑負對照")
    a = ap.parse_args()
    if a.neg:
        print(json.dumps(negative_control(a.award, a.parts), ensure_ascii=False, indent=2))
        return
    rep = compare(a.award, a.parts, a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(v["overall_pass"] for v in rep.values()) else 1)


if __name__ == "__main__":
    main()
