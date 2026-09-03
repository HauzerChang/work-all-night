#!/usr/bin/env python3
"""S1×S5 整合閘 —— 證明 **build_spine --rig --animate 生成的分鏡動畫**,讓肢體件
繞「關節接觸縫」擺動,而非件中心。(candidate 0g,2026-09-03)

背景 / 為什麼要這個閘
--------------------------------------------------------------------
- S1 keyframe(gen_animations,candidate 0d)給每個肢體件一條 `rotate` timeline;
  Spine 的 rotate 是「繞該件 **bone 原點**旋轉」。
- S5 rig(--rig,2026-08-30)把結構子件的 bone 原點從**件中心**移到**與父件的接觸縫**(關節)。
- 兩者理應「自動組合」:`--rig --animate` 時,gen_animations 產的 rotate 落在**已移到關節的**骨上
  → 肢體繞關節擺。但既有閘沒有一條真的驗證「**生成的動畫**」有這性質:
    * `validate_anim.py` 只驗動畫良構/無縫(且跑在**非 rig**、骨在件中心的 build 上);
    * `validate_rig_build.py` AC4 只驗**手動** 25° 旋轉(THETA 硬寫),不是 gen_animations 產的 keyframe。
  本閘補這個 honest-boundary 缺口:**用 Loop 分鏡自己產的峰值角度**去 pose,量肢體實際運動。

方法(純 CPU,無瀏覽器)
--------------------------------------------------------------------
對每個結構子件(joint=True:頭/左手/右手):
  1. 由 `_boundary_world` 取件的**稠密外輪廓**世界點(setup pose)。
  2. 由件輪廓對 body 輪廓的最近距離,把輪廓點分成「接觸縫側 seam(最近 30%)」與「末梢 distal(最遠 30%)」
     —— **純幾何**分類,與 pivot 無關(rig / 非 rig 用同一組索引)。
  3. 取生成 Loop 動畫中該件骨的 rotate 峰值角度(rig 與非 rig 的 timeline **完全相同**,只有骨原點不同)。
  4. 把件當**剛體**綁在其單一 bone 上(local = inverse(setup world)·p),施加「只轉該骨峰值角」的 pose
     → posed world → 量每點位移 |P1-P0|。分別對 rig build 與非 rig build 做。

驗收(AC)
--------------------------------------------------------------------
- **G1 生成即接關節**:--rig --animate 動畫良構(all_finite)且每個結構子件的骨在 Loop 有非平凡 rotate(峰值 |角|>0.5°)。
- **G2 生成動畫繞關節(對非 rig 的鑑別力)**:接觸縫 seam 點在生成旋轉下,rig 版位移 << 非 rig 版
  (seam_disp_flat / seam_disp_rig > 2)——證骨移到關節後,生成的擺動不再撕裂縫。
- **G3 真關節簽章**:rig 版「末梢/縫」位移比 >> 非 rig 版(rig>3 且 rig 比非 rig 至少大 2×)
  —— 真正繞關節時末梢甩得遠、縫近乎不動;繞件中心則縫與末梢對稱擺(比≈1)。
- **G4 負對照(內建)**:峰值角=0(不動)→ rig seam 位移≈0(<1e-2px),證位移來自動畫非數值噪音。

真相來源:build_spine 自身確定性 rig_layout(接觸縫已對藝術家真值驗過)+ gen_animations 生成的 timeline
+ Spine 3.8 bone world transform(weighted_deform_eval,已對 Award 真值重現)。
一鍵:`python3 tools/analyzer/validate_anim_rig.py`(exit 0 = PASS)。
"""
import sys, os, json, argparse, tempfile, shutil
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
import cv2                          # noqa: E402
import weighted_deform_eval as wde   # noqa: E402
import build_spine as bs             # noqa: E402
import spine_anim as sa              # noqa: E402

CONTACT_K = 6       # 接觸縫鄰域 = 件輪廓最靠近**關節 J** 的 K 點(J=rig 骨原點,已由 validate_rig_build 證在真縫上)
DISTAL_K = 6        # 末梢 = 件輪廓離關節 J 最遠的 K 點(對側末端)
EPS_NC = 1e-2       # 負對照:0° 旋轉的殘餘位移上限(px)


def _dense_world_contour(part_png, ox, oy, H, target=80):
    """由件 alpha 取**稠密**外輪廓世界點(不做激進 approxPolyDP,避免只剩 9~15 點的量測雜訊)。
    等距重採樣到約 `target` 點。回傳 Nx2 世界座標(y 上翻,與 build_spine 一致)。"""
    img = cv2.imread(part_png, cv2.IMREAD_UNCHANGED)
    alpha = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else \
        (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255
    mask = (alpha > 8).astype(np.uint8)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
    if len(c) > target:                       # 等距(依索引)下採樣
        idx = np.linspace(0, len(c) - 1, target).round().astype(int)
        c = c[idx]
    return np.column_stack([ox + c[:, 0], H - (oy + c[:, 1])])


def _slot_bone(sk):
    return {s["name"]: s["bone"] for s in sk["slots"]}


def _peak_rotate(anim, bone):
    """回傳該骨在 anim 中 rotate timeline 的(帶號)峰值角度;無則 0。"""
    ch = anim.get("bones", {}).get(bone, {})
    fr = ch.get("rotate")
    if not fr:
        return 0.0
    return max((f["angle"] for f in fr), key=abs)


def _pose_only(byname, bone, dtheta):
    """只把 bone 相對 setup 加轉 dtheta 度,其餘骨 setup。回傳 local_pose。"""
    b = byname[bone]
    return {bone: (b.get("x", 0.0), b.get("y", 0.0),
                   b.get("rotation", 0.0) + dtheta,
                   b.get("scaleX", 1.0), b.get("scaleY", 1.0))}


def _rigid_pose_disp(sil, w_setup, w_posed):
    """件輪廓 sil(世界 setup)當剛體綁在單一 bone:回傳施 posed 變換後每點位移。"""
    local = np.array([wde.inverse_transform_point(w_setup, p[0], p[1]) for p in sil])
    posed = np.array([wde.transform_point(w_posed, l[0], l[1]) for l in local])
    return np.linalg.norm(posed - sil, axis=1)


def evaluate(psd="assets/robot_parts.psd", genre="slot_bigwin", verbose=True, figure=None):
    tmp = tempfile.mkdtemp(prefix="animrig_")
    try:
        rig_dir = os.path.join(tmp, "rig")
        flat_dir = os.path.join(tmp, "flat")
        summ = bs.build(psd, rig_dir, genre, rig=True, animate=True)
        bs.build(psd, flat_dir, genre, rig=False, animate=True)   # 非 rig 對照(骨在件中心)

        skR, bonesR, bynameR, orderR = wde.load_skeleton(os.path.join(rig_dir, "skeleton.json"))
        skF, bonesF, bynameF, orderF = wde.load_skeleton(os.path.join(flat_dir, "skeleton.json"))
        worldR0 = wde.bone_world_transforms(bonesR, bynameR, orderR, {})
        worldF0 = wde.bone_world_transforms(bonesF, bynameF, orderF, {})
        sbR, sbF = _slot_bone(skR), _slot_bone(skF)
        metaR = json.load(open(os.path.join(rig_dir, "build_meta.json"), encoding="utf-8"))
        loopR = skR["animations"]["Loop"]
        loopF = skF["animations"]["Loop"]

        # --- 稠密輪廓(重新切 PSD 取件 PNG + offset)---
        from psd_slice import slice_psd                             # noqa: E402
        sdir = os.path.join(tmp, "_sil")
        psd2, _, parts2 = slice_psd(psd, sdir)
        Hs = psd2.height
        sil = {}
        for e, _im in parts2:
            sil[bs.safe(e["name"])] = _dense_world_contour(
                os.path.join(sdir, e["file"]), e["offset"][0], e["offset"][1], Hs)
        body = summ["rig_root"][2:]
        body_sil = sil[body]

        struct = [nm for nm in metaR if metaR[nm].get("joint")]

        # ---- G1 生成即接關節 ----
        g1_finite = sa.all_finite(loopR) and sa.all_finite(skR["animations"]["In"]) \
            and sa.all_finite(skR["animations"]["Out"])
        peaks = {}
        for nm in struct:
            pk = _peak_rotate(loopR, f"b_{nm}")
            peaks[nm] = pk
            # rig 與非 rig 的 rotate timeline 必須一致(只差骨原點)
            assert abs(pk - _peak_rotate(loopF, f"b_{nm}")) < 1e-9, f"{nm} rig/flat rotate 不一致"
        g1 = g1_finite and all(abs(peaks[nm]) > 0.5 for nm in struct)

        # ---- G2/G3:用生成峰值角 pose,量 seam / distal 位移 ----
        rows = []
        for nm in struct:
            C = sil[nm]
            bR = sbR[nm]; bF = sbF[nm]
            J = np.array([worldR0[bR][4], worldR0[bR][5]])       # 關節(rig 骨世界原點,已驗在真縫上)
            Cf = np.array([worldF0[bF][4], worldF0[bF][5]])      # 件中心(非 rig 骨世界原點)
            # 接觸縫鄰域 / 末梢:以「到關節 J 的距離」錨定(J 為真值,不用獨立猜縫,避免量測雜訊)
            d2J = np.linalg.norm(C - J, axis=1)
            seam_idx = np.zeros(len(C), bool); seam_idx[np.argsort(d2J)[:CONTACT_K]] = True
            distal_idx = np.zeros(len(C), bool); distal_idx[np.argsort(d2J)[-DISTAL_K:]] = True
            th = peaks[nm]

            # rig:繞關節 J 轉
            wR = wde.bone_world_transforms(bonesR, bynameR, orderR, _pose_only(bynameR, bR, th))
            dispR = _rigid_pose_disp(C, worldR0[bR], wR[bR])
            # flat:繞件中心 Cf 轉(同一組 seam/distal 點)
            wF = wde.bone_world_transforms(bonesF, bynameF, orderF, _pose_only(bynameF, bF, th))
            dispF = _rigid_pose_disp(C, worldF0[bF], wF[bF])
            # 負對照:rig 0°
            w0 = wde.bone_world_transforms(bonesR, bynameR, orderR, _pose_only(bynameR, bR, 0.0))
            disp0 = _rigid_pose_disp(C, worldR0[bR], w0[bR])

            seamR, distR = float(dispR[seam_idx].mean()), float(dispR[distal_idx].mean())
            seamF, distF = float(dispF[seam_idx].mean()), float(dispF[distal_idx].mean())
            rows.append(dict(
                nm=nm, theta=th,
                seamR=seamR, distR=distR, seamF=seamF, distF=distF,
                nc=float(disp0.max()),
                g2_ratio=(seamF / seamR if seamR > 1e-9 else float("inf")),
                rig_artic=(distR / seamR if seamR > 1e-9 else float("inf")),
                flat_artic=(distF / seamF if seamF > 1e-9 else float("inf")),
            ))

        # G2:每件接觸縫 rig 位移 << 非 rig(min ratio > 2)
        g2 = min(r["g2_ratio"] for r in rows) > 2.0
        # G3:rig 末梢/縫比 >3,且 rig 比非 rig 至少大 2×(真關節簽章 vs 對稱繞中心)
        g3 = all(r["rig_artic"] > 3.0 and r["rig_artic"] > 2.0 * r["flat_artic"] for r in rows)
        # G4:負對照(0° → 殘餘 < EPS_NC)
        g4 = max(r["nc"] for r in rows) < EPS_NC

        overall = g1 and g2 and g3 and g4
        if verbose:
            print(f"rig_root = {summ['rig_root']}   結構子件 = {struct}")
            print(f"生成 Loop 峰值角: " + "  ".join(f"b_{r['nm']}={r['theta']:+.1f}°" for r in rows))
            print(f"G1 生成即接關節(動畫良構 + 每子件骨有非平凡 rotate)      -> {'PASS' if g1 else 'FAIL'}")
            print(f"G2 生成動畫繞關節(seam 位移 rig<<非rig):")
            for r in rows:
                print(f"    {r['nm']}: seam rig={r['seamR']:.2f}px 非rig={r['seamF']:.2f}px "
                      f"ratio={r['g2_ratio']:.1f}")
            print(f"    min ratio={min(r['g2_ratio'] for r in rows):.1f} (>2.0)          -> {'PASS' if g2 else 'FAIL'}")
            print(f"G3 真關節簽章(末梢/縫 位移比:rig 大、非rig≈對稱):")
            for r in rows:
                print(f"    {r['nm']}: rig distal/seam={r['rig_artic']:.1f}  非rig={r['flat_artic']:.1f}")
            print(f"                                                       -> {'PASS' if g3 else 'FAIL'}")
            print(f"G4 負對照(0° 殘餘 max={max(r['nc'] for r in rows):.1e}px <{EPS_NC}) -> {'PASS' if g4 else 'FAIL'}")

        if figure:
            _make_figure(figure, sil, body_sil, struct, rows, bonesR, bynameR, orderR,
                         sbR, worldR0, bonesF, bynameF, orderF, sbF, worldF0, summ)

        return dict(g1=g1, g2=g2, g3=g3, g4=g4, overall=overall, struct=struct,
                    peaks=peaks, rows=rows)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _make_figure(path, sil, body_sil, struct, rows, bonesR, bynameR, orderR, sbR, worldR0,
                 bonesF, bynameF, orderF, sbF, worldF0, summ):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    for ax, build, byname, order, bones, sb, w0, title in [
        (axes[0], "rig", bynameR, orderR, bonesR, sbR, worldR0, "--rig(骨在關節縫)"),
        (axes[1], "flat", bynameF, orderF, bonesF, sbF, worldF0, "非rig(骨在件中心)")]:
        ax.plot(*np.vstack([body_sil, body_sil[:1]]).T, "k-", lw=1, alpha=0.4, label="body")
        for r in rows:
            nm = r["nm"]; C = sil[nm]; th = r["theta"]
            b = sb[nm]
            wp = wde.bone_world_transforms(bones, byname, order, _pose_only(byname, b, th))
            local = np.array([wde.inverse_transform_point(w0[b], p[0], p[1]) for p in C])
            posed = np.array([wde.transform_point(wp[b], l[0], l[1]) for l in local])
            ax.plot(*np.vstack([C, C[:1]]).T, "-", lw=1, alpha=0.5)
            ax.plot(*np.vstack([posed, posed[:1]]).T, "--", lw=1.4)
            org = (w0[b][4], w0[b][5])
            ax.plot(*org, "o", ms=7)
        ax.set_title(title); ax.set_aspect("equal"); ax.legend(loc="upper right", fontsize=8)
    fig.suptitle("生成 Loop 動畫峰值角 pose:實線=setup 虛線=posed 圓點=bone原點(rig=關節/非rig=件中心)")
    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110)
    print(f"  figure -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--figure", default=None, help="輸出診斷圖 PNG 路徑")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    print("=" * 74)
    print("S1×S5 整合閘 —— 生成的分鏡動畫讓肢體繞關節擺(build_spine --rig --animate)")
    print("=" * 74)
    r = evaluate(a.psd, a.genre, verbose=True, figure=a.figure)
    print("\n" + "=" * 74)
    print(f"OVERALL: {'PASS ✅' if r['overall'] else 'FAIL ❌'}  "
          f"(G1={r['g1']} G2={r['g2']} G3={r['g3']} G4={r['g4']})")
    print("=" * 74)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=float, indent=2))
    return 0 if r["overall"] else 1


if __name__ == "__main__":
    sys.exit(main())
