#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實藝術家 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 光暈/身體/左手
三件在生產 spine `Award` 中為 **weighted mesh**(藝術家手做)。本工具把「同一張真實素材」
分別餵給我的 S3 生成器與藝術家真值,做**靜態輪廓保真(coverage IoU)+ 拓樸(頂點/三角)**對照。

⚠️ 誠實邊界:這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
故此處**沒有可轉移的真實位移場** → 不做 deform 閘(依 RULES:不得用未校準 stress_field 冒充)。
本工具只回答:「我的生成器在真實生產件上的輪廓覆蓋是否 ≈ 藝術家?頂點預算是否合理?」

真值 mesh 的 `uvs` 為 region-normalized [0,1](經驗證);還原成件像素座標即可與切件 alpha 比對。
v 軸方向以「取 IoU 較高者」自動判定(經驗校正,避免上下顛倒誤判)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_mesh_v2 as g2
import evaluate_mesh as em


# robot_parts 三個 mesh 件 → Award slot 對應(切件檔名見 psd_slice manifest)
MESH_PIECES = {
    "光暈": {"file": "00_光暈.png", "slot": "機器人拆件/光暈"},
    "身體": {"file": "03_身體.png", "slot": "機器人拆件/身體"},
    "左手": {"file": "04_左手.png", "slot": "機器人拆件/左手"},
}


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"無法讀取: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        a = (g > 0).astype(np.uint8) * 255
    return (a > 8).astype(np.uint8)


def real_mesh(award_json, slot):
    d = json.load(open(award_json))
    for sk in d["skins"]:
        atts = sk.get("attachments", {}).get(slot)
        if atts:
            a = next(iter(atts.values()))
            return a
    raise SystemExit(f"找不到 slot: {slot}")


def coverage_iou(px, py, tris, mask):
    """把三角形填滿 → 與件 alpha 比 IoU。px,py 為件像素座標。"""
    H, W = mask.shape
    recon = np.zeros((H, W), np.uint8)
    pts = np.stack([px, py], axis=1)
    for t in tris:
        poly = np.round(pts[t]).astype(np.int32)
        cv2.fillConvexPoly(recon, poly, 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return inter / union if union else 0.0


def eval_real_mesh(mesh, mask):
    """真值 mesh 用 region-normalized uvs 還原件像素座標;v 方向取 IoU 高者。"""
    uv = mesh["uvs"]
    u = np.array(uv[0::2]); v = np.array(uv[1::2])
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    H, W = mask.shape
    px = u * W
    # 兩種 v 方向都試,取覆蓋較佳者(自動判定 v 原點)
    iou_down = coverage_iou(px, v * H, tris, mask)
    iou_up = coverage_iou(px, (1 - v) * H, tris, mask)
    flip = iou_up > iou_down
    return {
        "verts": len(u), "tris": len(tris), "hull": mesh["hull"],
        "iou": round(max(iou_down, iou_up), 4), "v_flipped": bool(flip),
    }


def run(parts_dir, award_json, budget=64):
    rows = []
    for label, info in MESH_PIECES.items():
        piece = os.path.join(parts_dir, info["file"])
        mask = load_alpha(piece)
        # 我的生成器
        mine = g2.generate(piece)
        rep = em.evaluate(mine, mask, vertex_budget=budget)
        c = rep["criteria"]
        mine_verts = rep["vertices"]
        mine_iou = c["AC1_iou"]["value"]
        # 幾何乾淨 = 格式對 + 無退化 + 無孤兒 + 重心在內(不含「絕對 0.95 IoU」那條)
        clean_geom = (c["AC4_format"]["pass"] and c["AC2b_degenerate"]["pass"]
                      and c["AC2c_orphans"]["pass"] and c["AC2a_centroid_in_mask"]["pass"]
                      and c["AC3_vertex_budget"]["pass"])
        # 藝術家真值
        rm = eval_real_mesh(real_mesh(award_json, info["slot"]), mask)
        rows.append({
            "piece": label, "slot": info["slot"],
            "mine": {"mode": mine.get("_mode"), "verts": mine_verts,
                     "tris": rep["triangles"], "iou": mine_iou,
                     "clean_geom": clean_geom,
                     "abs_iou95": c["AC1_iou"]["pass"]},
            "real": rm,
            # 覆蓋達標:我的 IoU 不低於藝術家 IoU - 容差(藝術家 mesh 是基準,非絕對 0.95)
            "iou_gap": round(mine_iou - rm["iou"], 4),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default=None, help="psd_slice 輸出目錄")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--tol", type=float, default=0.02,
                    help="IoU 覆蓋容差(我的 ≥ 藝術家 - tol 視為達標)")
    a = ap.parse_args()
    parts = a.parts
    if parts is None:
        # 就地切 PSD 到暫存
        import tempfile
        import psd_slice
        parts = tempfile.mkdtemp(prefix="robot_parts_")
        psd_slice.slice_psd("assets/robot_parts.psd", parts)
    rows = run(parts, a.award, a.budget)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    # 總判定:每件「我的輪廓 IoU ≥ 藝術家 - tol」(相對藝術家,非絕對 0.95)且「幾何乾淨」
    ok = all(r["iou_gap"] >= -a.tol and r["mine"]["clean_geom"] for r in rows)
    print(f"\n=== overall_pass = {ok} (相對藝術家 tol={a.tol}) ===")
    for r in rows:
        m, rl = r["mine"], r["real"]
        print(f"  {r['piece']:4s} slot={r['slot']}")
        print(f"       mine[{m['mode']}]: {m['verts']}v/{m['tris']}t IoU={m['iou']} "
              f"clean_geom={m['clean_geom']} abs_iou≥.95={m['abs_iou95']}")
        print(f"       real(artist):     {rl['verts']}v/{rl['tris']}t IoU={rl['iou']} (v_flip={rl['v_flipped']})")
        print(f"       iou_gap(mine-real)={r['iou_gap']:+.4f}  →節省頂點 {rl['verts']-m['verts']}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
