#!/usr/bin/env python3
"""端到端「PSD 件 → S3 mesh → 對照 Award 真實生產 mesh」整合驗證(靜態幾何 AC)。

背景(見 knowledge/s3-psd-to-award-mesh.md):
  Award(big win)spine 裡機器人拆件的 光暈/身體/左手 是 **mesh** attachment,且**無 deform
  timeline**(靠 weighted bone 變形,非逐頂點 deform)。與 main_draw 窗簾(strip、逐頂點 deform)
  是**不同類別**的 mesh —— 正好用來測 S3 生成器對「另一種真實生產 mesh」的通用性。

因為這 3 件無 deform timeline,**不套用 real-deform 轉移閘**(誠實地標 N/A);
改用「靜態幾何」三條 AC 對照藝術家真值:
  AC_iou   : 生成 mesh 覆蓋率(vs 件 alpha)>= 藝術家 mesh 對同一 alpha 的覆蓋率(baseline)。
  AC_topo  : evaluate_mesh 全過(格式 / 重心在 mask / 無退化 / 無孤兒)。
  AC_budget: 生成頂點數 <= 藝術家頂點數 × budget_ratio(精簡度不落後藝術家太多)。

發現(2026-08-10):`auto` 正確把這 3 件 blob 路由到 v1 Delaunay(非 strip)。v1 預設
epsilon_frac=0.008(為窗簾調)對羽化/凹形件**覆蓋率略低於藝術家**(光暈 0.933<0.949、
左手 0.964<0.977)。覆蓋率單調隨邊界取樣密度上升 → 加 **adaptive** 模式:自動把 epsilon
往下降(邊界加密)直到 IoU >= 藝術家 baseline(有界步數),3 件全 PASS。

來源真值:件 alpha 取自 `psd_slice` 切出的 PSD 件 PNG(= spine 生產貼圖素材,已於 session 006
以 alpha-IoU 0.92~0.99 確認同素材)。藝術家 mesh uvs 為 region-local 0..1(rotate 件亦然,
本檔開頭已實測對齊 PSD 件 alpha IoU 0.95~0.98),故直接以 uv*W, uv*H 填入件座標比對。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh import generate as gen_v1
from evaluate_mesh import evaluate

# Award 裡「機器人拆件」的 3 個 mesh 件 → psd_slice 切出的 PSD 件檔名
ROBOT_MESH_PARTS = {
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def part_alpha(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"讀不到件: {path}")
    if im.ndim == 3 and im.shape[2] == 4:
        return (im[:, :, 3] > 8).astype(np.uint8)
    g = im if im.ndim == 2 else cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def artist_attachment(award_json, part):
    sk = json.load(open(award_json))
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    slot = f"機器人拆件/{part}"
    return att[slot][slot]


def artist_iou(att, mask):
    """把藝術家 mesh 三角填入件座標(uv*W, uv*H),與件 alpha 比 IoU(覆蓋率 baseline)。"""
    uv = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uv[:, 0] * W, uv[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())


def gen_adaptive(path, target_iou, eps_ladder=(0.008, 0.005, 0.003, 0.002, 0.0015, 0.001)):
    """沿 epsilon 階梯加密邊界,直到覆蓋率 >= target 且拓樸全過(有界步數)。
    回傳 (mesh, mask, chosen_eps, iou, topo_ok)。取『達標的第一個』(最精簡)。"""
    mask = part_alpha(path)
    best = None
    for eps in eps_ladder:
        m, _ = gen_v1(path, epsilon_frac=eps)
        ev = evaluate(m, mask, vertex_budget=256)
        iou = ev["criteria"]["AC1_iou"]["value"]
        topo = ev["overall_pass"]
        best = (m, mask, eps, iou, topo, ev)
        if iou >= target_iou and topo:
            return best
    return best  # 用盡階梯仍以最後(最密)一版回傳


def validate_part(part_file_dir, award_json, part, budget_ratio=1.15, adaptive=True,
                  fixed_eps=0.008):
    path = os.path.join(part_file_dir, ROBOT_MESH_PARTS[part])
    att = artist_attachment(award_json, part)
    mask = part_alpha(path)
    art_iou = artist_iou(att, mask)
    art_v = len(att["uvs"]) // 2

    if adaptive:
        m, mask, eps, gi, topo, ev = gen_adaptive(path, target_iou=art_iou)
    else:
        m, _ = gen_v1(path, epsilon_frac=fixed_eps)
        ev = evaluate(m, mask, vertex_budget=256)
        gi = ev["criteria"]["AC1_iou"]["value"]
        topo = ev["overall_pass"]
        eps = fixed_eps
    gv = len(m["uvs"]) // 2

    ac_iou = gi >= art_iou
    ac_budget = gv <= art_v * budget_ratio
    ac_topo = topo
    return {
        "part": part, "mode": m.get("_mode", "delaunay-v1"), "chosen_eps": eps,
        "gen": {"vertices": gv, "hull": m["hull"], "triangles": len(m["triangles"]) // 3, "iou": round(gi, 4)},
        "artist": {"vertices": art_v, "iou": round(art_iou, 4)},
        "AC_iou": {"pass": bool(ac_iou), "gen": round(gi, 4), "baseline": round(art_iou, 4)},
        "AC_topo": {"pass": bool(ac_topo),
                    "detail": {k: v["pass"] for k, v in ev["criteria"].items()}},
        "AC_budget": {"pass": bool(ac_budget), "gen_v": gv, "artist_v": art_v,
                      "limit": round(art_v * budget_ratio, 1)},
        "AC_real_deform": "N/A (Award 這 3 件無 deform timeline;靠 weighted bone 變形)",
        "overall_pass": bool(ac_iou and ac_topo and ac_budget),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", required=True, help="psd_slice 切出的 PSD 件目錄")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--no-adaptive", action="store_true", help="用固定 epsilon(展示預設不足)")
    ap.add_argument("--eps", type=float, default=0.008)
    a = ap.parse_args()
    rep = {}
    for part in ROBOT_MESH_PARTS:
        rep[part] = validate_part(a.parts_dir, a.award, part,
                                  adaptive=not a.no_adaptive, fixed_eps=a.eps)
    allpass = all(r["overall_pass"] for r in rep.values())
    print(json.dumps({"overall_pass": allpass, "parts": rep}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
