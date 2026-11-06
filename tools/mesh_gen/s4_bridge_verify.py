#!/usr/bin/env python3
"""S4 chunk 307:驗收 Codex bridge 回傳的補圖(chunk60/filled/<id>_filled.png)。
流程(每件):
 1. 尺寸/通道檢查;尺寸不同但長寬比相同 → 縮放回 460x898 並標 `resized`(警告),否則 FAIL。
 2. 遮罩黑區漂移:bridge 產圖通常重新編碼,黑區不可能逐像素相同 → 量 premult MAE 當報告,
    **最終件一律合成**:黑區取原件、白區取 bridge 補圖(邊界 3px 羽化),寫 `composed/<id>.png`。
 3. 白區 1b 自我參照閘(inpaint_eval.score_1b;mode 依洞是否咬輪廓自動判)+ 白區殘留透明比例。
 4. 蒙太奇 `montage.png`(原件 / 遮罩 / bridge 原圖 / 合成)供目視;report.json。
用法:python s4_bridge_verify.py [--chunk chunk60] [ids...]
校準:--selftest 用 inpaint_eval 的 nearest 當假 bridge 輸出跑正對照,並以「黑區被改」「尺寸錯」當負對照。"""
import argparse, glob, json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import inpaint_eval as ie

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("ids", nargs="*")
ap.add_argument("--chunk", default="chunk60")
ap.add_argument("--selftest", action="store_true")
a = ap.parse_args()
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s4_data", a.chunk)
BR = os.path.join(D, "bridge"); FILLED = os.path.join(D, "filled" if not a.selftest else "filled_selftest")
OUT = os.path.join(D, "verify" if not a.selftest else "verify_selftest"); os.makedirs(os.path.join(OUT, "composed"), exist_ok=True)
tasks = {t["part"]: t for t in json.load(open(os.path.join(BR, "tasks.json")))}
k = lambda n: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))

def verify(pid, filled_path):
    r = {"part": pid, "file": os.path.relpath(filled_path, D), "checks": {}, "warnings": []}
    orig = ie.load_rgba(os.path.join(BR, f"{pid}.png")) if os.path.exists(os.path.join(BR, f"{pid}.png")) else ie.load_rgba(os.path.join(BR, "ref", f"{pid}.png"))
    mask = cv2.imread(os.path.join(BR, "ref", f"{pid}_mask.png"), 0) > 127
    H, W = orig.shape[:2]
    f = cv2.imread(filled_path, cv2.IMREAD_UNCHANGED)
    if f is None: r["checks"]["readable"] = False; r["pass"] = False; return r
    r["checks"]["has_alpha"] = (f.ndim == 3 and f.shape[2] == 4)
    if not r["checks"]["has_alpha"]: r["warnings"].append("無 alpha 通道:白區 alpha 以 255 計,需人工確認")
    fil = ie.load_rgba(filled_path)
    if fil.shape[:2] != (H, W):
        fh, fw = fil.shape[:2]
        if abs(fw / fh - W / H) < 0.01:
            fil = cv2.resize(fil, (W, H), interpolation=cv2.INTER_AREA); r["warnings"].append(f"尺寸 {fw}x{fh} ≠ {W}x{H},已依等比縮放"); r["checks"]["size"] = "resized"
        else:
            r["checks"]["size"] = f"FAIL {fw}x{fh}"; r["pass"] = False; return r
    else: r["checks"]["size"] = "ok"
    keep = ~mask
    r["checks"]["black_region_premult_mae"] = round(float(ie.premult_mae(fil, orig, keep)), 3)
    r["checks"]["black_region_alpha_mae"] = round(float(ie.alpha_mae(fil, orig, keep)), 3)
    # 合成:黑區取原件,白區取 bridge;邊界羽化
    w = cv2.GaussianBlur(mask.astype(np.float32), (7, 7), 0)[..., None]
    comp = orig * (1 - w) + fil * w
    comp[keep & ~(cv2.dilate(mask.astype(np.uint8), k(7)) > 0)] = orig[keep & ~(cv2.dilate(mask.astype(np.uint8), k(7)) > 0)]
    # 白區仍透明比例(bridge 沒畫到)
    r["checks"]["white_region_alpha_gap"] = round(float(((comp[..., 3] <= 8) & mask).sum() / max(mask.sum(), 1)), 4)
    content = comp[..., 3] > 8
    ring = cv2.dilate(mask.astype(np.uint8), k(5)).astype(bool) & ~mask
    edge_touch = (ring & (orig[..., 3] <= 8)).sum() / max(ring.sum(), 1)
    mode = "edge" if edge_touch > 0.15 else "interior"
    # 白區梯度能量比(白區內部 / 周圍 21px 環帶內容):噪聲≥1.34、CPU/真實紋理≤0.95(chunk307 校準)→ 1.25 擋「畫了但是雜訊」
    gm = ie._gradmag(comp); ring21 = cv2.dilate(mask.astype(np.uint8), k(21)).astype(bool) & ~mask & content
    inner = cv2.erode(mask.astype(np.uint8), k(5)).astype(bool)
    gr = float(gm[inner].mean() / (gm[ring21].mean() + 1e-6)) if inner.sum() >= 30 and ring21.sum() >= 30 else None
    r["checks"]["white_region_grad_ratio"] = None if gr is None else round(gr, 3)
    s = ie.score_1b(comp, mask, content, mode=mode)
    s["pass"] = ie.passes_1b(s, mode) if s["applicable"] else None
    r["checks"]["1b"] = {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in s.items()}; r["checks"]["1b_mode"] = mode
    ie.save_rgba(os.path.join(OUT, "composed", f"{pid}.png"), comp)
    hard_fail = r["checks"]["white_region_alpha_gap"] > 0.05 or (gr is not None and gr > 1.25) or s["pass"] is False
    # 1b 不適用(洞吃掉整段輪廓,如腿)→ 不能算 pass,標 None 交目視
    r["pass"] = False if hard_fail else (True if s["pass"] else None)
    r["needs_visual"] = (r["pass"] is None) or bool(r["warnings"])
    return r, orig, mask, fil, comp

def tile(rgba, box, S=220):
    x0, y0, x1, y1 = box; pad = 12
    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(rgba.shape[1], x1 + pad), min(rgba.shape[0], y1 + pad)
    c = rgba[y0:y1, x0:x1]; al = c[..., 3:] / 255
    chk = np.full(c.shape[:2] + (1,), 90.); chk[::16, ::16] = 140
    img = (c[..., :3][..., ::-1] * al + chk * (1 - al)).astype(np.uint8)
    h, w = img.shape[:2]; f = min(S / h, S / w); return cv2.resize(img, (max(1, int(w * f)), max(1, int(h * f))))

if a.selftest:
    os.makedirs(FILLED, exist_ok=True)
    for pid in tasks:
        orig = ie.load_rgba(os.path.join(BR, "ref", f"{pid}.png")); mask = cv2.imread(os.path.join(BR, "ref", f"{pid}_mask.png"), 0) > 127
        holed = orig.copy(); holed[mask] = 0
        ie.save_rgba(os.path.join(FILLED, f"{pid}_filled.png"), ie.fill_nearest(holed, None, mask))   # 正對照(CPU 假補)
        ie.save_rgba(os.path.join(FILLED, f"{pid}_filled.empty.png"), holed)                                # 負對照 A:白區沒畫(必 FAIL:alpha_gap)
        ie.save_rgba(os.path.join(FILLED, f"{pid}_filled.noise.png"), ie.fill_random(holed, None, mask))     # 負對照 B:白區噪聲(應 FAIL:1b)
        # 黑區被改(+40)不是負對照:合成步驟一律以原件覆蓋黑區,故只記錄 black_region_mae 供參考
        ie.save_rgba(os.path.join(FILLED, f"{pid}_filled.wrongsize.png"), cv2.resize(orig, (512, 512)))
files = sorted(glob.glob(os.path.join(FILLED, "*_filled*.png")))
if a.ids: files = [f for f in files if os.path.basename(f).split("_filled")[0] in a.ids]
rows, report = [], []
for fp in files:
    pid = os.path.basename(fp).split("_filled")[0]
    if pid not in tasks: continue
    res = verify(pid, fp)
    if isinstance(res, tuple):
        r, orig, mask, fil, comp = res
        box = tasks[pid]["bbox"]; mk = np.dstack([mask * 255] * 3 + [np.full(mask.shape, 255)]).astype(float)
        row = np.hstack([tile(orig, box), tile(mk, box), tile(fil, box), tile(comp, box)])
        cv2.putText(row, f"{os.path.basename(fp)} pass={r['pass']} 1b={r['checks']['1b']['pass']} gr={r['checks']['white_region_grad_ratio']}", (4, 12), 0, 0.38, (0, 255, 255), 1)
        rows.append(row)
    else: r = res
    report.append(r); print(json.dumps(r, ensure_ascii=False))
if rows:
    Wm = max(x.shape[1] for x in rows); cv2.imwrite(os.path.join(OUT, "montage.png"), np.vstack([np.pad(x, ((0, 6), (0, Wm - x.shape[1]), (0, 0))) for x in rows]))
json.dump(report, open(os.path.join(OUT, "report.json"), "w"), ensure_ascii=False, indent=1)
print(f"pass={sum(1 for r in report if r.get('pass') is True)} visual={sum(1 for r in report if r.get('pass') is None)} fail={sum(1 for r in report if r.get('pass') is False)} / {len(report)} → {OUT}")
