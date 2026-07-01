#!/usr/bin/env python3
"""S1 反推分析器 — 塊 1:運動場提取 + 動態前景定位 + 全域運動特徵。

PLAN S1:影片 → Asset & Rig Requirement Spec。非人形機器人走 **Farneback 稠密光流 + 運動分群**。
本塊只做**最底層、可自我驗證**的一步(運動事實提取),後續塊才做「分群成件 → 需求規格」:

  1. 逐相鄰幀 Farneback 稠密光流 → 每像素運動向量。
  2. 累積運動能量圖(magnitude 總和)→ 定位「會動的前景」(vs 靜態背景)。
  3. 全域運動特徵:動態像素的水平/垂直平均流隨時間序列 → 偵測「左右律動」
     (dx 時間序列過零次數 + 振幅)與「上下彈跳」(dy)。

自我驗證 AC(機讀,不靠肉眼):
  AC1 前景定位:四角(背景)運動能量 << 中央(機器人);corner/center 比 < 0.15。
  AC2 律動偵測:動態像素 dx 時間序列**過零 ≥4 次**且振幅 > 0.3px → 確認「左右律動舞蹈」。
  AC3 產出視覺化(運動熱圖疊圖 + dx/dy 律動曲線)供人審。
"""
import argparse, json, os, sys
import numpy as np
import cv2


def read_frames(path, max_frames=None):
    v = cv2.VideoCapture(path)
    fps = v.get(cv2.CAP_PROP_FPS)
    frames = []
    while True:
        ok, f = v.read()
        if not ok:
            break
        frames.append(f)
        if max_frames and len(frames) >= max_frames:
            break
    v.release()
    return frames, fps


def flow_stats(frames):
    """回傳 (energy HxW, dx_series, dy_series, moving_mask)。"""
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    H, W = grays[0].shape
    energy = np.zeros((H, W), np.float64)
    dx_series, dy_series = [], []
    for i in range(len(grays) - 1):
        fl = cv2.calcOpticalFlowFarneback(grays[i], grays[i + 1], None,
                                          0.5, 3, 21, 3, 5, 1.2, 0)
        mag = np.hypot(fl[..., 0], fl[..., 1])
        energy += mag
        # 動態像素(該幀對 magnitude 顯著者)的平均水平/垂直流
        m = mag > max(0.5, np.percentile(mag, 92))
        if m.sum() > 20:
            dx_series.append(float(fl[..., 0][m].mean()))
            dy_series.append(float(fl[..., 1][m].mean()))
        else:
            dx_series.append(0.0); dy_series.append(0.0)
    energy /= max(len(grays) - 1, 1)
    thr = max(0.3, np.percentile(energy, 80))
    moving = (energy > thr).astype(np.uint8)
    return energy, np.array(dx_series), np.array(dy_series), moving


def zero_crossings(series):
    s = np.sign(series)
    s[s == 0] = 1
    return int((np.diff(s) != 0).sum())


def corner_center_ratio(energy):
    H, W = energy.shape
    ch, cw = H // 4, W // 4
    corners = [energy[:ch, :cw], energy[:ch, -cw:], energy[-ch:, :cw], energy[-ch:, -cw:]]
    corner = float(np.mean([c.mean() for c in corners]))
    center = float(energy[H // 2 - ch:H // 2 + ch, W // 2 - cw:W // 2 + cw].mean())
    return corner, center, (corner / center if center > 1e-6 else 1.0)


def draw_curve(series, w, h, label, color=(80, 220, 80)):
    canvas = np.full((h, w, 3), 30, np.uint8)
    cv2.line(canvas, (0, h // 2), (w, h // 2), (90, 90, 90), 1)   # 零線
    if len(series) > 1:
        amp = max(np.abs(series).max(), 1e-6)
        pts = [(int(i * (w - 1) / (len(series) - 1)), int(h / 2 - (v / amp) * (h / 2 - 6)))
               for i, v in enumerate(series)]
        cv2.polylines(canvas, [np.array(pts, np.int32)], False, color, 2)
    cv2.putText(canvas, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return canvas


def visualize(frame0, energy, dx, dy, out_png):
    H, W = energy.shape
    heat = cv2.applyColorMap((255 * energy / max(energy.max(), 1e-6)).astype(np.uint8), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(frame0, 0.5, heat, 0.5, 0)
    cv2.putText(overlay, "motion energy", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cx = draw_curve(dx, W, 120, "dx (side-to-side sway)", (80, 220, 80))
    cy = draw_curve(dy, W, 120, "dy (up-down bob)", (80, 160, 240))
    stack = np.vstack([overlay, cx, cy])
    cv2.imwrite(out_png, stack)


def analyze(video_path, out_png=None, max_frames=None):
    frames, fps = read_frames(video_path, max_frames)
    energy, dx, dy, moving = flow_stats(frames)
    corner, center, ratio = corner_center_ratio(energy)
    zc_x, zc_y = zero_crossings(dx), zero_crossings(dy)
    amp_x, amp_y = float(np.abs(dx).max()), float(np.abs(dy).max())

    ac1 = ratio < 0.15
    ac2 = zc_x >= 4 and amp_x > 0.3
    if out_png:
        visualize(frames[0], energy, dx, dy, out_png)
    ac3 = bool(out_png and os.path.exists(out_png))

    return {
        "video": {"frames": len(frames), "fps": round(fps, 2),
                  "size": [frames[0].shape[1], frames[0].shape[0]]},
        "AC1_foreground": {"pass": ac1, "corner_energy": round(corner, 4),
                           "center_energy": round(center, 4), "corner_center_ratio": round(ratio, 4)},
        "AC2_sway": {"pass": ac2, "dx_zero_crossings": zc_x, "dx_amplitude_px": round(amp_x, 3),
                     "dominant_axis": "horizontal" if amp_x >= amp_y else "vertical"},
        "AC3_viz": {"pass": ac3, "out": out_png},
        "motion_signature": {"dy_zero_crossings": zc_y, "dy_amplitude_px": round(amp_y, 3),
                             "moving_area_ratio": round(float(moving.mean()), 4)},
        "overall_pass": ac1 and ac2 and ac3,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?", default="assets/robot_dance.mp4")
    ap.add_argument("-o", "--out", default="knowledge/figures/s1_motion.png")
    ap.add_argument("--max-frames", type=int, default=None)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    rep = analyze(a.video, a.out, a.max_frames)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
