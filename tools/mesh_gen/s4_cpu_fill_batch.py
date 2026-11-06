#!/usr/bin/env python3
"""S4 chunk 305: 九尾狐 v3 低難度件 CPU 補圖批次(head/leg_left/leg_right/sleeve_left/hair_main)。
洞 = 該件被「z 較小(較前)」件遮住的區域(含污染像素:切件內含遮擋件顏色);補法用 inpaint_eval
的 nearest/cv2_telea/cv2_ns 候選 + 1b 自我參照盲選(無真值)。輸出 chunk60/cpu_fill/。"""
import json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import inpaint_eval as ie

D = os.path.join(os.path.dirname(__file__), "s4_data/chunk60")
CUT = os.path.join(D, "cut_sam"); OUT = os.path.join(D, "cpu_fill")
TARGETS = sys.argv[1:] or ["head", "leg_left", "leg_right", "sleeve_left", "hair_main"]
os.makedirs(OUT, exist_ok=True)
# z 僅為切件順序,非前後層;語意上明確的遮擋關係覆寫(依 knowledge/s4-inpaint-requirements-jiuwei-v3.md)
OCCLUDERS = {"head": ["hair_front_left", "hair_front_right", "earrings", "choker"],
             "sleeve_left": ["hand_left"]}
man = json.load(open(os.path.join(CUT, "manifest.json")))
W, H = man["size"]
layers = {}
for p in man["parts"]:
    im = ie.load_rgba(os.path.join(CUT, p["file"]))
    full = np.zeros((H, W, 4)); ox, oy = p["offset"]; h, w = im.shape[:2]
    full[oy:oy+h, ox:ox+w] = im
    layers[p["id"]] = (p["z"], full)

k = lambda n: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))
report = {}
for pid in TARGETS:
    z, full = layers[pid]
    a = full[..., 3] > 128
    occ = np.zeros((H, W), bool)
    for q, (qz, qf) in layers.items():
        if (q in OCCLUDERS[pid]) if pid in OCCLUDERS else (qz < z): occ |= qf[..., 3] > 128
    # 洞只限件輪廓內:被遮擋件顏色污染的像素 + 輪廓內被遮擋件吃掉的封閉缺口(closing 補出的部分),
    # 不外擴到輪廓外(v1 外擴 17px 會讓補圖在身體外長出條紋,目測不可信)。
    ext = cv2.morphologyEx(a.astype(np.uint8), cv2.MORPH_CLOSE, k(15)).astype(bool)
    hole = ext & occ
    hole = cv2.dilate(hole.astype(np.uint8), k(3)).astype(bool) & ext
    ext = ext | hole
    ys, xs = np.where(ext); y0, y1, x0, x1 = ys.min(), ys.max()+1, xs.min(), xs.max()+1
    crop = lambda m: m[y0:y1, x0:x1]
    hm = crop(hole)
    if hm.sum() < 20:
        report[pid] = {"hole_px": int(hm.sum()), "skipped": "無實質遮擋"}; continue
    g = full[y0:y1, x0:x1].copy()
    holed = g.copy(); holed[hm] = 0
    ring = cv2.dilate(hm.astype(np.uint8), k(5)).astype(bool) & ~hm
    edge_touch = (ring & (g[..., 3] <= 8)).sum() / max(ring.sum(), 1)
    mode = "edge" if edge_touch > 0.15 else "interior"
    sc = ie.score_candidates(holed, hm, mode=mode)
    best, why = ie.select_best(sc, applicable=next(iter(sc.values()))["score"]["applicable"] is not False)
    ie.save_rgba(os.path.join(OUT, f"{pid}_holed.png"), holed)
    ie.save_rgba(os.path.join(OUT, f"{pid}_filled.png"), sc[best]["recon"])
    s = sc[best]["score"]
    report[pid] = {"hole_px": int(hm.sum()), "content_px": int((g[..., 3] > 8).sum()), "mode": mode,
                   "edge_touch": round(float(edge_touch), 2), "best": best, "why": why,
                   "bbox": [int(x0), int(y0), int(x1-x0), int(y1-y0)],
                   "scores": {n: {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in sc[n]["score"].items()} for n in sc}}
json.dump(report, open(os.path.join(OUT, "report.json"), "w"), ensure_ascii=False, indent=1, default=str)
for pid, r in report.items():
    print(pid, {k2: r.get(k2) for k2 in ("hole_px", "content_px", "mode", "best", "why", "skipped")})
