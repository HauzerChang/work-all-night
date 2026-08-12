#!/usr/bin/env python3
"""端到端驗收:真實生產 PSD 件 → S3 v2 mesh，對照 Award 真實生產 mesh。

背景(見 STATE.md next-action #1、log 2026-06-26-005/006):
  機器人拆件的 3 個 mesh 件(光暈/身體/左手)在生產 spine `Award` 裡是 **weighted mesh**
  (bone 驅動,`vertices.length != uvs.length`),且 **無 deform timeline**(靠骨骼變形)。
  → 真實位移場 deform 閘(transfer_deform_check)對這些件 **N/A**(沒有 deform 場可轉移)。
  本工具做「靜態」端到端驗收:S3 v2 生成 mesh 的覆蓋率 / 拓樸 / 頂點經濟度,對照藝術家真值。

比對框架(單一一致座標系 = atlas 抽出的 region 影像):
  1. atlas_crop.extract(Award.atlas, page, name) → 該件影像(生產貼圖,~0.70 縮小,已 derotate)。
     log 006 已證 PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 = 同素材,故 atlas 件足以代表 PSD 件,
     且能直接疊 Award mesh(其 uvs 為 atlas UV)。
  2. generate_mesh_v2 對該件 → evaluate_mesh 靜態 AC(IoU / 重心 / 退化 / 孤兒 / 頂點預算 / 格式)。
  3. Award 真實 mesh 基準:uvs(atlas UV)→ region 局部像素(自校準:正規化 uv bbox→影像 bbox,
     v 翻轉兩式取 IoU 高者,並要求 artist IoU 夠高以確認映射正確)→ 光柵化三角 → artist_iou。
  4. 閘:v2 IoU >= artist IoU - margin;拓樸全過;頂點 <= 預算。輸出 artist 頂點數作經濟度對照。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate


def award_mesh(sk, slot, name):
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    a = att[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return uvs, tris, a


def raster_iou(uvs_local, tris, mask):
    H, W = mask.shape
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(uvs_local[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def artist_baseline(uvs, tris, mask):
    """自校準把 atlas-UV 疊到 derotate 後的 region 影像。

    atlas 打包可能把件旋轉 90°(rotate=true),extract() 已 derotate 影像,但 uvs 仍在 atlas
    page 軸上 → uv 軸與影像軸可能差一個二面體變換。故枚舉 8 個正規化二面體方位(4 旋轉 × 2 翻轉),
    取 IoU 最高者(= 正確方位)。要求結果 IoU 夠高(mapping_ok)以確認映射可信,才拿來當基準。
    這與 atlas_crop 用 PSD 外部真值校準 derotate 方向是同一套「以重疊度定方位」的紀律。
    """
    H, W = mask.shape
    umin, vmin = uvs.min(0)
    umax, vmax = uvs.max(0)
    nx = (uvs[:, 0] - umin) / max(umax - umin, 1e-9)  # 0..1
    ny = (uvs[:, 1] - vmin) / max(vmax - vmin, 1e-9)  # 0..1
    best = None
    for k in range(4):          # 旋轉 90*k
        for flip in (False, True):
            a, b = nx.copy(), ny.copy()
            if flip:
                a = 1.0 - a
            for _ in range(k):  # 每次 90° CW: (a,b)->(1-b,a)
                a, b = 1.0 - b, a
            loc = np.column_stack([a * (W - 1), b * (H - 1)])
            iou = raster_iou(loc, tris, mask)
            if best is None or iou > best[0]:
                best = (iou, k, flip)
    return best  # (iou, rot90_k, flipped)


def run_one(sk, atlas, page, slot, name, tmp, margin=0.0, budget=64):
    sub = extract(atlas, page, name)
    crop = os.path.join(tmp, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = (sub[:, :, 3] > 8).astype(np.uint8) if sub.ndim == 3 and sub.shape[2] == 4 \
        else (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)

    # S3 v2 生成 + 靜態評估
    mesh = gen_v2(crop, mode="auto")
    ev = evaluate(mesh, mask, vertex_budget=budget)
    my_iou = ev["criteria"]["AC1_iou"]["value"]
    topo_pass = all(ev["criteria"][k]["pass"] for k in
                    ("AC2a_centroid_in_mask", "AC2b_degenerate", "AC2c_orphans", "AC3_vertex_budget"))

    # 藝術家真值基準
    a_uvs, a_tris, a = award_mesh(sk, slot, name)
    base_iou, rot_k, flip = artist_baseline(a_uvs, a_tris, mask)
    a_nv = len(a_uvs)

    # 藝術家基準是否可信:Award.json uvs 在原始 atlas 座標系,shipped PNG 為 ~0.70 repack,
    # 直接 page-normalize 可能對不上(見 knowledge/s4-psd-to-spine-real.md)。以「藝術家 mesh 應緊貼
    # 自身 alpha」為 sanity:base_iou 夠高才採信;否則退回 AC.md 的絕對門檻 0.90(無可信藝術家參照)。
    mapping_ok = base_iou >= 0.85
    iou_thresh = (base_iou - margin) if mapping_ok else 0.90
    iou_pass = my_iou >= iou_thresh

    return {
        "slot": slot, "name": name,
        "region_px": [int(sub.shape[1]), int(sub.shape[0])],
        "v2": {"vertices": ev["vertices"], "hull": mesh["hull"], "triangles": ev["triangles"],
               "mode": mesh.get("_mode"), "iou": round(my_iou, 4), "topology_pass": topo_pass,
               "criteria": {k: ev["criteria"][k].get("value", ev["criteria"][k].get("pass"))
                            for k in ev["criteria"]}},
        "artist": {"vertices": a_nv, "triangles": len(a_tris), "hull": a.get("hull"),
                   "weighted": len(a["vertices"]) != len(a["uvs"]),
                   "iou_baseline": round(base_iou, 4), "uv_orient": {"rot90": rot_k, "flip": flip},
                   "mapping_ok": mapping_ok},
        "gates": {"iou_pass": iou_pass, "iou_thresh": round(iou_thresh, 4),
                  "iou_ref": "artist" if mapping_ok else "fallback-0.90",
                  "topology_pass": topo_pass,
                  "vertex_economy": f"{ev['vertices']} vs artist {a_nv}",
                  "deform_gate": "N/A — 件為 weighted mesh 且無 deform timeline(骨骼驅動)"},
        "overall_pass": bool(iou_pass and topo_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--page", default="assets/Award.png")  # extract 會用 region 所屬 page 覆寫
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.0)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    targets = [
        ("機器人拆件/光暈", "機器人拆件/光暈"),
        ("機器人拆件/身體", "機器人拆件/身體"),
        ("機器人拆件/左手", "機器人拆件/左手"),
    ]
    reps = [run_one(sk, a.atlas, a.page, s, n, a.tmp, a.margin) for s, n in targets]
    allpass = all(r["overall_pass"] for r in reps)
    print(json.dumps({"results": reps, "all_pass": allpass}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
