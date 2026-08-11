#!/usr/bin/env python3
"""端到端閘:PSD 件 → S3 生成 mesh → 對照「真實生產 spine」的藝術家 mesh。

這是 S3+S4 的接縫驗收(見 knowledge/s4-psd-to-spine-real.md 的「下一步」):
把真實 PSD 切出的件當來源,跑 generate_mesh，和同一件在生產 spine 裡的**真實 mesh**
比覆蓋率(coverage IoU vs alpha)。真實 mesh 是外部真值(非自產),故這是強驗收。

判準(每件):
  - gen_iou >= artist_iou - margin   (生成 mesh 覆蓋率不輸藝術家手做)
  - 生成 mesh 通過 evaluate() 全 AC(格式/退化/孤兒/預算)
  - 頂點數不高於藝術家(效率不輸)—— 資訊性,不作 hard gate

關鍵發現(2026-08-11,robot_parts×Award):v1 的 coverage 由**邊界取樣密度
epsilon_frac** 決定(非內部點)。預設 0.008 對平滑窗簾夠,但對機器人光暈/手等
複雜有機輪廓略輸藝術家;調到 0.004 三件全 BEAT 藝術家且頂點更少。
邊界越細,凹形輪廓可能出現孤兒頂點(見 --epsilon 0.004 的 光暈)——待修的下一步。

Award 機器人拆件的真實 mesh/region 分配(ground truth):
  光暈 mesh(78v)、身體 mesh(98v)、左手 mesh(80v);右手/頭為 region(旋轉)。
Award mesh 的 uvs 為 region-local [0,1](已驗:artist 重建 IoU≈0.95 合理),
故可直接對「PSD 切件的原尺寸 alpha」比對(+2px atlas padding 對 IoU 影響可忽略)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask
from psd_slice import slice_psd  # noqa

# 預設:robot_parts.psd 圖層 → Award slot(皆為 mesh 的 3 件)
DEFAULT_PIECES = [
    ("光暈", "機器人拆件/光暈"),
    ("身體", "機器人拆件/身體"),
    ("左手", "機器人拆件/左手"),
]


def award_mesh(skeleton, slot):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][slot]


def artist_iou(att, mask):
    """真實(藝術家)mesh 用 region-local uvs 重建填滿 → vs alpha 的 coverage IoU。"""
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union) if union else 0.0


def find_piece_png(pieces_dir, layer):
    for f in os.listdir(pieces_dir):
        if f.endswith(".png") and layer in f:
            return os.path.join(pieces_dir, f)
    raise SystemExit(f"找不到圖層 {layer} 的切件 PNG(於 {pieces_dir})")


def run(psd, skeleton_path, pieces, gen_fn, gen_name, pieces_dir, margin):
    if pieces_dir is None:
        pieces_dir = "/tmp/_psdmesh_pieces"
        slice_psd(psd, pieces_dir)
    sk = json.load(open(skeleton_path))
    rows, all_pass = [], True
    for layer, slot in pieces:
        png = find_piece_png(pieces_dir, layer)
        mask = load_mask(png)
        att = award_mesh(sk, slot)
        base = artist_iou(att, mask)
        gm = gen_fn(png)
        if isinstance(gm, tuple):
            gm = gm[0]
        ev = evaluate(gm, mask, vertex_budget=max(64, len(att["uvs"]) // 2 + 8))
        gi = ev["criteria"]["AC1_iou"]["value"]
        gv = ev["vertices"]
        av = len(att["uvs"]) // 2
        cov_pass = gi >= base - margin
        ac_pass = ev["overall_pass"]
        ok = cov_pass and ac_pass
        all_pass = all_pass and ok
        rows.append({
            "piece": layer, "slot": slot, "gen_mode": gm.get("_mode"),
            "artist_iou": round(base, 4), "gen_iou": round(gi, 4),
            "artist_v": av, "gen_v": gv,
            "coverage_pass": cov_pass, "ac_overall_pass": ac_pass,
            "ac_fails": [k for k, r in ev["criteria"].items() if not r["pass"]],
            "pass": ok,
        })
    return {"generator": gen_name, "margin": margin, "pieces": rows, "overall_pass": all_pass}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v1")
    ap.add_argument("--epsilon", type=float, default=0.004,
                    help="v1 邊界取樣密度(越小越貼合輪廓;coverage 主控旋鈕)")
    ap.add_argument("--margin", type=float, default=0.0,
                    help="coverage 容差:gen_iou >= artist_iou - margin 即過")
    ap.add_argument("--pieces-dir", default=None,
                    help="已切好的件目錄(略過即時切 PSD)")
    a = ap.parse_args()
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p, epsilon_frac=a.epsilon)
        name = f"v1(epsilon={a.epsilon})"
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")
        name = "v2(auto)"
    rep = run(a.psd, a.skeleton, DEFAULT_PIECES, gen, name, a.pieces_dir, a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
