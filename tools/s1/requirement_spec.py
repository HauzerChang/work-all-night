#!/usr/bin/env python3
"""S1 塊3 — Asset & Rig Requirement Spec:把運動場(塊1)+分群(塊2)+**每件運動型態**組成需求規格。

每候選件由其 per-frame affine 運動模型抽出:
  - 旋轉率序列 dθ_t = (∂fy/∂x − ∂fx/∂y)/2(affine 反對稱部分)→ 積分得 θ_t → **振幅(度)**。
  - **pivot** = affine 不動點(M·p=−t),以 |dθ| 加權平均(旋轉大的幀較可信)。
  - 平移振幅 = 件質心位移中「非旋轉」殘量。
  - motion_type:旋轉主導 / 平移主導。
→ 每件輸出 {region, motion_type, rot_amp_deg, pivot, trans_amp_px} = rig 需求(哪些件要動、怎麼動)。

★ 評估器:合成 GT **注入已知運動**(手臂±16°/頭±9°… + 已知 pivot),反推後比對 pivot/振幅誤差
  → 精確真值閘(不同於塊2 只驗「分對區塊」,這裡驗「運動參數量化正確」)。
"""
import argparse, json, os, sys, math, tempfile
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from psd_slice import slice_psd
from motion_segment import (segment_flows, synth_flow_from_parts, synth_known_params,
                            clusters_to_regions, video_flows, SYNTH_AMP)


def extract_motion(xs, ys, flows):
    """xs,ys:件像素;flows:(T,h,w,2)。回傳運動參數。"""
    T = flows.shape[0]
    A = np.column_stack([xs, ys, np.ones(len(xs))]).astype(np.float64)
    dth, piv_acc, wsum = [], np.zeros(2), 0.0
    cx0, cy0 = xs.mean(), ys.mean()
    center_disp = []
    for t in range(T):
        fx = flows[t, ys, xs, 0]; fy = flows[t, ys, xs, 1]
        cx, *_ = np.linalg.lstsq(A, fx, rcond=None)
        cy, *_ = np.linalg.lstsq(A, fy, rcond=None)
        a, b, c = cx; d, e, f = cy
        w = (d - b) / 2.0
        dth.append(w)
        M = np.array([[a, b], [d, e]])
        if abs(np.linalg.det(M)) > 1e-8:
            p = np.linalg.solve(M, [-c, -f])
            piv_acc += abs(w) * p; wsum += abs(w)
        center_disp.append([a * cx0 + b * cy0 + c, d * cx0 + e * cy0 + f])
    dth = np.array(dth)
    theta = np.cumsum(dth)
    rot_amp = math.degrees((theta.max() - theta.min()) / 2) if T else 0.0
    pivot = (piv_acc / wsum) if wsum > 1e-9 else np.array([cx0, cy0])
    cd = np.array(center_disp)
    trans_amp = float(np.hypot(cd[:, 0].max() - cd[:, 0].min(), cd[:, 1].max() - cd[:, 1].min()) / 2)
    # 旋轉主導?比較旋轉造成的邊緣位移幅度 vs 平移
    radius = float(np.hypot(xs - pivot[0], ys - pivot[1]).mean())
    rot_disp = math.radians(rot_amp) * radius
    return {"motion_type": "rotation" if rot_disp >= trans_amp else "translation",
            "rot_amp_deg": round(rot_amp, 2), "pivot_px": [round(float(pivot[0]), 1), round(float(pivot[1]), 1)],
            "trans_amp_px": round(trans_amp, 2), "mean_radius_px": round(radius, 1)}


def build_spec(flows, lab):
    regions = clusters_to_regions(lab, min_area=30)
    spec = []
    for (c, mm, area, cent) in sorted(regions, key=lambda r: -r[2]):
        ys, xs = np.where(mm > 0)
        m = extract_motion(xs, ys, flows)
        spec.append({"cluster": int(c), "area_px": int(area),
                     "centroid_px": [round(cent[0], 1), round(cent[1], 1)], **m})
    return spec


def _best_cluster_mask(lab, gt_region):
    best, bm = 0.0, None
    for c in range(lab.max() + 1):
        mm = lab == c
        inter = np.logical_and(gt_region, mm).sum(); uni = np.logical_or(gt_region, mm).sum()
        iou = inter / uni if uni else 0
        if iou > best:
            best, bm = iou, mm
    return best, bm


def validate_synthetic(psd, rig_config, scale=0.35):
    _, manifest, parts = slice_psd(psd, tempfile.mkdtemp())
    W, H = manifest["size"]
    masks = {}
    for e, im in parts:
        canvas = np.zeros((H, W), np.uint8)
        l, t = e["offset"]; wd, ht = e["size"]
        canvas[t:t + ht, l:l + wd] = (np.array(im.split()[-1]) > 8).astype(np.uint8)
        masks[e["name"]] = (canvas, e["z"])
    pivots = (json.load(open(rig_config)).get("pivots") if os.path.exists(rig_config) else {}) or {}
    known = synth_known_params(list(masks.items()), pivots, W, H, scale)
    flows, gt, names = synth_flow_from_parts(list(masks.items()), pivots, W, H, scale)
    lab, _, _ = segment_flows(flows, fg_mask=(gt >= 0), k=len(names))

    per = []
    for nid, name in enumerate(names):
        gm = gt == nid
        if gm.sum() < 30:
            continue
        iou, bm = _best_cluster_mask(lab, gm)
        if bm is None:
            continue
        ys, xs = np.where(bm)
        rec = extract_motion(xs, ys, flows)
        k = known[name]
        piv_err = math.hypot(rec["pivot_px"][0] - k["pivot_px"][0], rec["pivot_px"][1] - k["pivot_px"][1])
        amp_err = abs(rec["rot_amp_deg"] - k["amp_deg"])
        per.append({"part": name, "iou": round(float(iou), 3),
                    "amp_deg": {"recovered": rec["rot_amp_deg"], "injected": k["amp_deg"],
                                "err": round(amp_err, 2)},
                    "pivot_px": {"recovered": rec["pivot_px"], "injected": k["pivot_px"],
                                 "err_px": round(piv_err, 1)}})
    # 對「有明顯運動、且分對(iou≥0.4)」的件驗參數;振幅誤差<3.5°、pivot 誤差<12px
    checked = [p for p in per if p["iou"] >= 0.4 and known[p["part"]]["amp_deg"] >= 8]
    amp_ok = all(p["amp_deg"]["err"] < 3.5 for p in checked)
    piv_ok = all(p["pivot_px"]["err_px"] < 12 for p in checked)
    return {"per_part": per, "checked_parts": [p["part"] for p in checked],
            "amp_ok": amp_ok, "pivot_ok": piv_ok, "pass": bool(checked and amp_ok and piv_ok)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="assets/robot_dance.mp4")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--rig-config", default="assets/robot_parts.rig.json")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--out", default="assets/robot_dance_spec.json")
    a = ap.parse_args()

    ev = validate_synthetic(a.psd, a.rig_config)              # ① 參數反推精度(合成真值)
    flows_v, base = video_flows(a.video, scale=0.35)          # ② 真實影片需求規格
    lab_v, _, _ = segment_flows(flows_v, k=a.k)
    spec = build_spec(flows_v, lab_v)
    doc = {"source": os.path.basename(a.video), "scale": 0.35, "n_parts": len(spec),
           "parts": spec, "note": "候選可動件 + 運動型態;pivot/amp 於合成 GT 驗證(見 synthetic_eval)"}
    json.dump(doc, open(a.out, "w"), ensure_ascii=False, indent=2)

    print(json.dumps({"synthetic_param_eval": ev, "video_spec": doc, "spec_out": a.out},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if ev["pass"] else 1)


if __name__ == "__main__":
    main()
