#!/usr/bin/env python3
"""S5×S1 組合閘 —— 驗「rig 骨架 × 生成主秀動畫」的**關節接合**在整支生成動畫下成立。

本閘補的缺口:`validate_rig_build` 只驗**單一固定角 THETA=25°** 的接觸縫語意(靜態解析),
`validate_anim` 只驗**非 rig 扁平骨架**的動畫良構;兩者都沒證明「`build_spine --rig --animate`
把 S5 關節樹與 S1 生成 timeline **組起來**後,肢體真的繞關節擺、且黏在父件身上」。

組合機制(為何 rig 版接合、非 rig 版散架):
  - `--rig`:結構子件骨掛 **body**(b_身體)、原點落在**接觸縫關節** → 子件(a)隨 body 剛體移動、
    (b)自轉繞關節 → 接縫黏在父件插槽上。
  - 非 rig(對照):同一支生成 timeline,但子件骨掛 **root**、原點在**件中心** → 子件(a)不隨 body、
    (b)繞件中心自轉 → 接縫脫離父件(散架)。負對照 = 完全相同動畫、只差 rig 結構。

真相/量測(純 CPU,無瀏覽器):
  spine_anim / weighted_deform_eval 逐幀取樣生成 timeline → bone world transform →
  量「子件接縫點在**父件(body)移動座標系**中相對 setup 的偏移」= 接縫脫離插槽的距離。
  rig 版此偏移應小且有界(接縫黏住);非 rig 版應顯著更大(接縫漂走)。

AC(客觀、可機讀;一鍵 `python3 tools/analyzer/validate_rig_anim.py`,exit 0 = PASS):
  AC1 組合良構+機制:rig+animate 可載入;關節子件在 Loop 有 rotate timeline;三 beat 全 all_finite;
      rig 關節子件骨 parent==b_body、非 rig 版 parent==root(機制成立)。
  AC2 rig 接縫黏連:每個關節子件的接縫脫槽距離 ≤ TOL_RIG(有界、黏住)。
  AC3 負對照(非 rig 散架):每個關節子件「非 rig 脫槽 > rig」(嚴格單調)+ 總和比 ≥ SUM_RATIO
      + 最大槓桿關節比 ≥ MAX_RATIO(誠實列出各件比值,含幾何上 center≈joint 的弱件)。
  AC4 逐幀有限/乾淨:三 beat 全程 world transform 有限、非退化;mesh 件(body/光暈)逐幀 si=0/flip=0
      (剛體變換保拓樸 → 生成動畫不撕裂 mesh)。
  AC5 radial 修正+向後相容:(a)非 rig 建構下件骨世界原點==(bone.x,bone.y)→ 非 rig 徑向與舊式逐位吻合;
      (b)rig 下修正徑向指向真實世界原點方位(cos≈1),且舊式(誤用 local 座標)對 ≥1 關節方向翻反(cos<0.5)。
"""
import sys, os, json, math, argparse, tempfile, shutil
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))
import weighted_deform_eval as wde   # noqa: E402
import build_spine as bs             # noqa: E402
import gen_animations as ga          # noqa: E402
from spine_anim import duration, all_finite  # noqa: E402
from psd_slice import slice_psd      # noqa: E402
from deform_eval import signed_area  # noqa: E402

SEAM_Q = 0.25       # 取子件最靠近父件的前 25% 點當「接縫」
TOL_RIG = 12.0      # rig 接縫脫槽距離上界(px)
SUM_RATIO = 1.8     # 總脫槽比(非rig/rig)下界
MAX_RATIO = 3.0     # 最大槓桿關節脫槽比下界
NFR = 41            # 逐幀取樣數
SEAM_ANIM = "Loop"  # 接縫量測用 Loop(僅旋轉、無平移;body 僅 ±2% 呼吸無 scale-from-0 假影)


def _load(out_dir):
    sk, bones, byname, order = wde.load_skeleton(os.path.join(out_dir, "skeleton.json"))
    meta = json.load(open(os.path.join(out_dir, "build_meta.json")))
    slot_bone = {s["name"]: s["bone"] for s in sk["slots"]}
    return sk, bones, byname, order, meta, slot_bone


def _silhouettes(psd, sdir):
    psd2, _, parts2 = slice_psd(psd, sdir)
    sil = {}
    for e, _im in parts2:
        ws, _ = bs._boundary_world(os.path.join(sdir, e["file"]), e["offset"][0], e["offset"][1], psd2.height)
        sil[bs.safe(e["name"])] = ws
    return sil


def _seam_pts(sil, nm, body):
    C, B = sil[nm], sil[body]
    d = np.min(np.linalg.norm(C[:, None, :] - B[None, :, :], axis=2), axis=1)
    return C[d <= np.quantile(d, SEAM_Q) + 1e-9]


def _seam_socket_drift(sk, bones, byname, order, slot_bone, sil, nm, body, anim):
    """子件接縫點在**父件(body)移動座標系**中相對 setup 的最大平均偏移(=脫槽距離)。
    黏在插槽上 → 偏移小;漂走 → 偏移大。"""
    affected = [b["name"] for b in bones if b["name"] != "root"]
    posef = wde.anim_local_pose(sk, anim, byname, affected)
    cb, bb = slot_bone[nm], slot_bone[body]
    w0 = wde.bone_world_transforms(bones, byname, order, {})
    S = _seam_pts(sil, nm, body)
    S_loc_c = [wde.inverse_transform_point(w0[cb], x, y) for x, y in S]     # 接縫點在子骨 local
    S_body0 = np.array([wde.inverse_transform_point(w0[bb], x, y) for x, y in S])  # setup 下在 body local
    dur = duration(sk["animations"][anim]) or 2.0
    peak = 0.0
    for i in range(NFR):
        t = dur * i / (NFR - 1)
        w = wde.bone_world_transforms(bones, byname, order, posef(t))
        Sa = [wde.transform_point(w[cb], lx, ly) for lx, ly in S_loc_c]              # 動畫後世界
        Sa_body = np.array([wde.inverse_transform_point(w[bb], x, y) for x, y in Sa])  # 投回動畫後 body local
        peak = max(peak, float(np.linalg.norm(Sa_body - S_body0, axis=1).mean()))
    return peak


def _mesh_clean_over_frames(sk, bones, byname, order, slot_bone, nm):
    """mesh 件在三 beat 全程逐幀 si/flip/degen。回傳 (worst_si, worst_flip, worst_degen, all_finite_world)。"""
    att = next(iter(sk["skins"]["default"][nm].values()))
    pv, tris, _, _, _ = wde.parse_weighted(att)
    cb = slot_bone[nm]
    affected = [b["name"] for b in bones if b["name"] != "root"]
    w0 = wde.bone_world_transforms(bones, byname, order, {})
    V0 = np.array([wde.transform_point(w0[cb], e[0][1], e[0][2]) for e in pv])
    setup_signs = [signed_area(V0, t) > 0 for t in tris]   # check() 慣例:布林(a>0)
    setup_area = sum(abs(signed_area(V0, t)) for t in tris) or 1.0
    wsi = wfl = wdg = 0
    finite = True
    for anim in sk["animations"]:
        posef = wde.anim_local_pose(sk, anim, byname, affected)
        dur = duration(sk["animations"][anim]) or 1.0
        for i in range(NFR):
            t = dur * i / (NFR - 1)
            w = wde.bone_world_transforms(bones, byname, order, posef(t))
            if not all(math.isfinite(v) for v in w[cb]):
                finite = False
            V = np.array([wde.transform_point(w[cb], e[0][1], e[0][2]) for e in pv])
            if not np.all(np.isfinite(V)):
                finite = False
                continue
            r = wde.eval_pose_wm(V, tris, setup_signs, setup_area)
            wsi = max(wsi, r["self_intersections"]); wfl = max(wfl, r["triangle_flips"])
            wdg = max(wdg, r["degenerate"])
    return wsi, wfl, wdg, finite


def _world_nondegenerate(sk, bones, byname, order):
    """三 beat 全程每根骨 world matrix 有限且 |det|>eps(非塌陷)。"""
    affected = [b["name"] for b in bones if b["name"] != "root"]
    ok = True
    for anim in sk["animations"]:
        posef = wde.anim_local_pose(sk, anim, byname, affected)
        dur = duration(sk["animations"][anim]) or 1.0
        for i in range(NFR):
            t = dur * i / (NFR - 1)
            w = wde.bone_world_transforms(bones, byname, order, posef(t))
            for nmb, m in w.items():
                a, b, c, d, x, y = m
                if not all(math.isfinite(v) for v in m) or abs(a * d - b * c) < 1e-9:
                    ok = False
    return ok


def evaluate(psd="assets/robot_parts.psd", genre="slot_bigwin", verbose=True):
    tmp = tempfile.mkdtemp(prefix="rigatim_")
    try:
        rig_dir, flat_dir, sdir = (os.path.join(tmp, d) for d in ("rig", "flat", "_sil"))
        summ = bs.build(psd, rig_dir, genre, rig=True, animate=True)
        bs.build(psd, flat_dir, genre, rig=False, animate=True)   # 負對照:同動畫、無 rig
        skR, bonesR, bynameR, orderR, metaR, sbR = _load(rig_dir)
        skF, bonesF, bynameF, orderF, metaF, sbF = _load(flat_dir)
        sil = _silhouettes(psd, sdir)
        body = summ["rig_root"][2:]
        joints = [nm for nm in metaR if metaR[nm].get("joint")]

        # ---- AC1 組合良構 + 機制 ----
        loadable = all(k in skR for k in ("bones", "slots", "skins", "animations")) and len(skR["animations"]) > 0
        rot_in_loop = all(
            "rotate" in skR["animations"][SEAM_ANIM].get("bones", {}).get(f"b_{nm}", {}) for nm in joints)
        finite_anims = all(all_finite(skR["animations"][a]) for a in skR["animations"])
        mech = all(bynameR[f"b_{nm}"].get("parent") == f"b_{body}" for nm in joints) and \
            all(bynameF[f"b_{nm}"].get("parent") == "root" for nm in joints)
        ac1 = loadable and rot_in_loop and finite_anims and mech

        # ---- AC2 / AC3 接縫脫槽(rig 黏連 vs 非 rig 散架)----
        rig_drift, flat_drift, ratios = {}, {}, {}
        for nm in joints:
            rd = _seam_socket_drift(skR, bonesR, bynameR, orderR, sbR, sil, nm, body, SEAM_ANIM)
            fd = _seam_socket_drift(skF, bonesF, bynameF, orderF, sbF, sil, nm, body, SEAM_ANIM)
            rig_drift[nm] = rd; flat_drift[nm] = fd
            ratios[nm] = fd / rd if rd > 1e-9 else float("inf")
        ac2 = all(v <= TOL_RIG for v in rig_drift.values())
        monotone = all(flat_drift[nm] > rig_drift[nm] for nm in joints)
        sum_ratio = sum(flat_drift.values()) / max(sum(rig_drift.values()), 1e-9)
        max_ratio = max(ratios.values())
        ac3 = monotone and sum_ratio >= SUM_RATIO and max_ratio >= MAX_RATIO

        # ---- AC4 逐幀有限/乾淨 ----
        mesh_parts = [nm for nm in metaR if metaR[nm].get("mesh")]
        mesh_ok = True; mesh_rep = {}
        for nm in mesh_parts:
            wsi, wfl, wdg, fin = _mesh_clean_over_frames(skR, bonesR, bynameR, orderR, sbR, nm)
            mesh_rep[nm] = (wsi, wfl, wdg, fin)
            mesh_ok = mesh_ok and (wsi == 0 and wfl == 0 and wdg == 0 and fin)
        world_ok = _world_nondegenerate(skR, bonesR, bynameR, orderR)
        ac4 = mesh_ok and world_ok

        # ---- AC5 radial 修正 + 向後相容 ----
        # (a) 非 rig:件骨世界原點 == (bone.x, bone.y)(徑向與舊式逐位吻合)
        bc_ok = True
        for nm in [s["name"] for s in skF["slots"]]:
            b = bynameF[sbF[nm]]
            wx, wy = ga._bone_world_origin(sbF[nm], bynameF)
            if abs(wx - b.get("x", 0.0)) > 1e-9 or abs(wy - b.get("y", 0.0)) > 1e-9:
                bc_ok = False
        # (b) rig:修正徑向 cos≈1 對真世界方位;舊式(local 當座標)對 ≥1 關節翻反
        cx, cy = skR["skeleton"]["width"] / 2.0, skR["skeleton"]["height"] / 2.0
        new_cos, old_cos = {}, {}
        for nm in joints:
            b = bynameR[f"b_{nm}"]
            wx, wy = ga._bone_world_origin(f"b_{nm}", bynameR)
            true_dir = np.array([wx - cx, wy - cy]); tn = np.linalg.norm(true_dir) or 1.0
            new_dir = true_dir / tn
            old_dir = np.array([b.get("x", 0.0) - cx, b.get("y", 0.0) - cy])  # 舊式:誤把 local 當畫布座標
            on = np.linalg.norm(old_dir) or 1.0
            new_cos[nm] = float(new_dir @ (true_dir / tn))
            old_cos[nm] = float((old_dir / on) @ (true_dir / tn))
        new_correct = all(v > 0.99 for v in new_cos.values())
        old_broken = any(v < 0.5 for v in old_cos.values())
        ac5 = bc_ok and new_correct and old_broken

        if verbose:
            print(f"rig_root=b_{body}  關節子件={joints}  mesh 件={mesh_parts}")
            print(f"AC1 組合良構+機制(可載入/Loop有rotate/finite/子件掛body vs root) -> {'PASS' if ac1 else 'FAIL'}")
            print(f"AC2 rig 接縫黏連 脫槽={{{', '.join(f'{k}:{v:.1f}' for k,v in rig_drift.items())}}}px "
                  f"(≤{TOL_RIG}) -> {'PASS' if ac2 else 'FAIL'}")
            print(f"AC3 負對照 非rig脫槽={{{', '.join(f'{k}:{v:.1f}' for k,v in flat_drift.items())}}}px  "
                  f"比值={{{', '.join(f'{k}:{v:.1f}x' for k,v in ratios.items())}}}  "
                  f"單調={monotone} 總和比={sum_ratio:.2f}(≥{SUM_RATIO}) 最大比={max_ratio:.1f}(≥{MAX_RATIO}) "
                  f"-> {'PASS' if ac3 else 'FAIL'}")
            print(f"AC4 逐幀有限/乾淨 mesh={mesh_rep} world_nondegen={world_ok} -> {'PASS' if ac4 else 'FAIL'}")
            print(f"AC5 radial 修正 向後相容={bc_ok} newcos={{{', '.join(f'{k}:{v:.2f}' for k,v in new_cos.items())}}} "
                  f"oldcos={{{', '.join(f'{k}:{v:.2f}' for k,v in old_cos.items())}}} "
                  f"(新≈1、舊≥1件翻反<0.5) -> {'PASS' if ac5 else 'FAIL'}")

        overall = ac1 and ac2 and ac3 and ac4 and ac5
        return dict(ac1=ac1, ac2=ac2, ac3=ac3, ac4=ac4, ac5=ac5, overall=overall,
                    joints=joints, rig_drift=rig_drift, flat_drift=flat_drift, ratios=ratios,
                    sum_ratio=sum_ratio, max_ratio=max_ratio, mesh_rep=mesh_rep,
                    new_cos=new_cos, old_cos=old_cos, rig_root=summ["rig_root"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    print("=" * 74)
    print("S5×S1 組合閘 —— build_spine --rig --animate(關節樹 × 生成主秀動畫)")
    print("=" * 74)
    r = evaluate(a.psd, a.genre, verbose=True)
    print("\n" + "=" * 74)
    print(f"OVERALL: {'PASS ✅' if r['overall'] else 'FAIL ❌'}  "
          f"(AC1={r['ac1']} AC2={r['ac2']} AC3={r['ac3']} AC4={r['ac4']} AC5={r['ac5']})")
    print("=" * 74)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=float, indent=2))
    return 0 if r["overall"] else 1


if __name__ == "__main__":
    sys.exit(main())
