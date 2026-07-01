#!/usr/bin/env python3
"""S1 塊2 — 運動分群成件:把動態前景依「時序運動簽名」分成差動區塊(候選可動件)。

方法:每像素取跨幀光流時序 (dx_t,dy_t) 當運動簽名 + 空間座標 → kmeans2 分群 → 每群取
連通區為候選件。剛體件(繞 pivot 旋轉)的像素共享一致的旋轉速度場 → 可被運動簽名分開。

★ 評估器(每能力必配):用**剛綁好的 rig** 產生「已知件」的合成剛體旋轉光流當 ground truth,
  跑分群器 → 對已知 part mask 算**召回率**(貪婪 IoU 指派)。閉環、純 CPU、有精確真值。
  (舞蹈影片的機器人與 robot_parts 是不同角色,不能逐件比對;故用合成 GT 驗方法,再套真實影片產候選。)
"""
import argparse, json, os, sys, math, tempfile
import numpy as np
import cv2
from scipy.cluster.vq import kmeans2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from psd_slice import slice_psd


# ---------------- 分群核心:affine 運動模型 EM ----------------
# 剛體件的每幀光流在像素座標上是 affine:flow=[a·x+b·y+c, d·x+e·y+f](小角旋轉/平移皆是)。
# 樸素 flow-kmeans 會把「旋轉件」拆碎(遠端像素流差異大);改用「每群一組 per-frame affine 模型,
# 依殘差指派像素」的 EM(經典多剛體運動分割)→ 同件像素被同一 affine 解釋 → 正確聚在一起。
def _affine_em(P, F, K, iters=8, seed=0):
    """P:(N,2) 像素座標;F:(T,N,2) 光流。回傳 (labels, total_residual)。seed 選種不看真值。"""
    T, N, _ = F.shape
    A = np.column_stack([P[:, 0], P[:, 1], np.ones(N)])          # N×3
    _, labels = kmeans2(np.column_stack([P[:, 0], P[:, 1]]).astype(np.float64) /
                        (P.max(0) + 1e-6), K, seed=seed, minit="++", missing="warn")
    for _ in range(iters):
        R = np.full((N, K), 1e18)
        for k in range(K):
            m = labels == k
            if m.sum() < 6:
                continue
            Ak = A[m]; tot = np.zeros(N)
            for t in range(T):
                cx, *_ = np.linalg.lstsq(Ak, F[t, m, 0], rcond=None)
                cy, *_ = np.linalg.lstsq(Ak, F[t, m, 1], rcond=None)
                tot += (F[t, :, 0] - A @ cx) ** 2 + (F[t, :, 1] - A @ cy) ** 2
            R[:, k] = tot
        labels = R.argmin(1)
    return labels, float(R[np.arange(N), labels].sum())


def segment_flows(flows, fg_mask=None, k=5, mag_pct=55, seeds=6):
    """flows:(T,h,w,2)。fg_mask 給定則用之,否則用能量門檻定前景。
    多 seed 跑 affine-EM,選**總殘差最小**者(非監督,不看真值)。回傳 (label_img,-1=背景, k, fg)."""
    T, h, w, _ = flows.shape
    if fg_mask is None:
        energy = np.sqrt((flows ** 2).sum(-1)).sum(0)
        thr = max(1e-3, np.percentile(energy[energy > 0], mag_pct)) if (energy > 0).any() else 0
        fg_mask = energy > thr
    ys, xs = np.where(fg_mask)
    if len(xs) < k * 3:
        return np.full((h, w), -1, np.int32), 0, fg_mask
    P = np.column_stack([xs, ys]).astype(np.float64)
    F = flows[:, ys, xs, :]
    best = None
    for s in range(seeds):
        labels, res = _affine_em(P, F, k, seed=s)
        if best is None or res < best[1]:
            best = (labels, res)
    lab = np.full((h, w), -1, np.int32)
    lab[ys, xs] = best[0]
    return lab, k, fg_mask


def clusters_to_regions(lab, min_area=30):
    """每群取連通區(可能多塊,取最大)為候選件 mask。回傳 [(label, mask, area, centroid)]."""
    out = []
    for c in range(lab.max() + 1):
        m = (lab == c).astype(np.uint8)
        if m.sum() < min_area:
            continue
        n, cc, stats, cent = cv2.connectedComponentsWithStats(m)
        if n <= 1:
            continue
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mm = (cc == big).astype(np.uint8)
        out.append((c, mm, int(stats[big, cv2.CC_STAT_AREA]),
                    (float(cent[big][0]), float(cent[big][1]))))
    return out


# ---------------- 合成 GT(用 rig 驗召回) ----------------
def synth_flow_from_parts(masks_z, pivots, W, H, scale, T=12):
    """每件繞自身 pivot 獨立擺動,生成合成剛體光流 (T-1,h,w,2) + GT 標籤圖(件→id)。"""
    h, w = int(H * scale), int(W * scale)
    # GT 標籤:每像素指派給「最上層(z 大)」覆蓋它的件
    gt = np.full((h, w), -1, np.int32)
    order = sorted(masks_z, key=lambda kv: kv[1][1])  # by z asc
    names = []
    for name, (m, z) in order:
        ms = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST) > 0
        if name not in names:
            names.append(name)
        gt[ms] = names.index(name)
    # 每件角速度排程(度):手臂大、頭中、身體/光暈小
    amp = {"左手": 16, "右手": 16, "頭": 9, "身體": 5, "光暈": 4}
    ph = {"左手": 0.0, "右手": math.pi, "頭": 0.5, "身體": 0.0, "光暈": 0.0}
    def theta(name, t):
        A = amp.get(name, 6); return math.radians(A * math.sin(2 * math.pi * t / T + ph.get(name, 0)))
    # 每件 pivot(px→scale);身體/無 pivot 用件質心
    piv = {}
    for name, (m, z) in masks_z:
        if name in pivots:
            piv[name] = (pivots[name][0] * scale, pivots[name][1] * scale)
        else:
            ys, xs = np.where(cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST) > 0)
            piv[name] = (xs.mean(), ys.mean())
    yy, xx = np.mgrid[0:h, 0:w]
    def posrot(name, t):
        c, s = math.cos(theta(name, t)), math.sin(theta(name, t))
        px, py = piv[name]
        dx = c * (xx - px) - s * (yy - py) + px
        dy = s * (xx - px) + c * (yy - py) + py
        return dx, dy
    flows = []
    for t in range(T - 1):
        fx = np.zeros((h, w)); fy = np.zeros((h, w))
        for nid, name in enumerate(names):
            reg = gt == nid
            x0, y0 = posrot(name, t); x1, y1 = posrot(name, t + 1)
            fx[reg] = (x1 - x0)[reg]; fy[reg] = (y1 - y0)[reg]
        flows.append(np.dstack([fx, fy]))
    return np.array(flows), gt, names


def recall_eval(lab, gt, names, iou_thresh=0.4, exclude=None):
    exclude = set(exclude or [])
    regions = clusters_to_regions(lab, min_area=20)
    per = []
    used = set()
    for nid, name in enumerate(names):
        if name in exclude:            # 背景件(如光暈halo)非articulated,不列召回標的
            continue
        gm = gt == nid
        if gm.sum() < 20:
            continue
        best, bc = 0.0, None
        for (c, mm, area, cent) in regions:
            inter = np.logical_and(gm, mm > 0).sum(); uni = np.logical_or(gm, mm > 0).sum()
            iou = inter / uni if uni else 0
            if iou > best:
                best, bc = iou, c
        per.append({"part": name, "best_iou": round(float(best), 3),
                    "cluster": None if bc is None else int(bc),
                    "recovered": bool(best >= iou_thresh)})
        if bc is not None and best >= iou_thresh:
            used.add(bc)
    rec = sum(p["recovered"] for p in per) / max(len(per), 1)
    return {"recall": round(rec, 3), "iou_thresh": iou_thresh, "per_part": per,
            "clusters_found": len(regions)}


# ---------------- 真實影片 ----------------
def video_flows(path, scale=0.35, max_frames=None, step=2):
    v = cv2.VideoCapture(path); frames = []
    while True:
        ok, f = v.read()
        if not ok:
            break
        frames.append(f)
        if max_frames and len(frames) >= max_frames:
            break
    v.release()
    frames = frames[::step]
    small = [cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), None, fx=scale, fy=scale) for f in frames]
    flows = [cv2.calcOpticalFlowFarneback(small[i], small[i + 1], None, 0.5, 3, 15, 3, 5, 1.2, 0)
             for i in range(len(small) - 1)]
    return np.array(flows), cv2.resize(frames[0], None, fx=scale, fy=scale)


def viz_segments(base_bgr, lab, out_png):
    h, w = lab.shape
    palette = [(60, 220, 60), (40, 150, 235), (0, 200, 255), (230, 80, 200),
               (80, 80, 240), (240, 200, 40), (200, 120, 40)]
    ov = base_bgr.copy()
    for c in range(lab.max() + 1):
        ov[lab == c] = (0.45 * np.array(palette[c % len(palette)]) + 0.55 * ov[lab == c]).astype(np.uint8)
    cv2.imwrite(out_png, ov)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="assets/robot_dance.mp4")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--rig-config", default="assets/robot_parts.rig.json")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--out", default="knowledge/figures/s1_segments.png")
    a = ap.parse_args()

    # ① 合成 GT 驗召回(方法可信度)
    _, manifest, parts = slice_psd(a.psd, tempfile.mkdtemp())
    W, H = manifest["size"]
    masks = {}
    for e, im in parts:
        canvas = np.zeros((H, W), np.uint8)
        l, t = e["offset"]; wd, ht = e["size"]
        canvas[t:t + ht, l:l + wd] = (np.array(im.split()[-1]) > 8).astype(np.uint8)
        masks[e["name"]] = (canvas, e["z"])
    pivots = (json.load(open(a.rig_config)).get("pivots") if os.path.exists(a.rig_config) else {}) or {}
    flows_s, gt, names = synth_flow_from_parts(list(masks.items()), pivots, W, H, scale=0.35)
    # 背景件(面積 > 40% 畫布,如光暈 halo)非 articulated → 不列召回標的,但仍餵入前景
    areas = {nid: int((gt == nid).sum()) for nid in range(len(names))}
    canvas_area = gt.shape[0] * gt.shape[1]
    backdrop = [names[nid] for nid, ar in areas.items() if ar > 0.40 * canvas_area]
    lab_s, _, _ = segment_flows(flows_s, fg_mask=(gt >= 0), k=len(names))
    ev = recall_eval(lab_s, gt, names, exclude=backdrop)
    ev["excluded_backdrop"] = backdrop

    # ② 套真實影片產候選件
    flows_v, base = video_flows(a.video, scale=0.35)
    lab_v, _, mask_v = segment_flows(flows_v, k=a.k)
    regions = clusters_to_regions(lab_v)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    viz_segments(base, lab_v, a.out)
    cand = [{"cluster": int(c), "area_px": area, "centroid": [round(x, 1), round(y, 1)]}
            for (c, mm, area, (x, y)) in sorted(regions, key=lambda r: -r[2])]

    rep = {
        "synthetic_recall_eval": ev,
        "video_candidates": {"k": a.k, "clusters": len(regions), "regions": cand, "viz": a.out},
        "pass": ev["recall"] >= 0.8,   # 合成 GT 至少召回 80% 已知件才算方法可信
    }
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["pass"] else 1)


if __name__ == "__main__":
    main()
