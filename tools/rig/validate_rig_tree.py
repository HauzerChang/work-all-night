"""S5 (b) 的自我品質閘 —— 「推斷 pivot → Spine 骨鏈」接得對不對。

真值 rig:Award 機器人子 rig(身體=根,頭/左手/右手=子;藝術家骨位=真值關節)。
與 validate_pivots 共用 loader / rig_scale;此閘驗的是 **接成骨鏈後的關節行為**,
不是 pivot 座標本身(那由 validate_pivots 顧)。

四道客觀校驗(機讀 pass/fail):
  AC1 setup round-trip —— jointed rig 在 setup(全骨 identity)重建的世界點雲 == 原件世界點雲
                          (接骨鏈不得移動任何件)。max 位移 < 0.01 px(骨座標 3 位小數捨入下限)。
  AC2 關節行為正確     —— 逐子件「轉自己的骨」θ,解剛體旋轉不動點,應落在真值關節上
                          (max err/rig < TAU)。且 **整體(中位)贏過 flat rig**(flat 骨在件中心,
                          不動點 = 件質心)。用中位而非逐件:緊湊肢體(右手)質心偶爾恰近其關節,
                          逐件宰制是灌水;中位才是誠實的集體宣稱(與 validate_pivots AC2 一致)。
  AC3 父件繼承         —— 轉「身體(根件)」骨:jointed rig 子件**跟著動**且整體維持剛體
                          (件間距零變化);flat rig 子件**不動**(各綁 root,不繼承)→ 脫節。
                          證明骨鏈把肢體正確掛上父件。
  AC4 泛化界定(誠實)  —— 實查 Award:僅機器人件被拆解(機器人拆件/*),OMG/SUP/MEG 角色
                          為單一 slot 無拆件 → 接觸縫關節推斷 **無多 rig 真值可驗**。
                          此為資產限制,非方法限制;如實回報,不灌水。
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import infer_pivots as ip          # noqa: E402
import validate_pivots as vp       # noqa: E402
import build_rig as br             # noqa: E402

TAU = 0.10
THETA = 25.0                       # 測試旋轉角(度)


def flat_chain(parts_world):
    """負對照 rig:每件骨 = 件質心、parent=root(即 build_spine 現況)。"""
    bones = [{"name": "root"}]
    part_bone, part_local = {}, {}
    for p in parts_world:
        c = np.asarray(parts_world[p]).reshape(-1, 2).mean(0)
        bn = f"b_{br._safe(p)}"
        part_bone[p] = bn
        bones.append({"name": bn, "parent": "root",
                      "x": round(float(c[0]), 3), "y": round(float(c[1]), 3)})
        part_local[p] = np.asarray(parts_world[p]).reshape(-1, 2) - c
    return bones, part_bone, part_local


def evaluate(award_path="assets/Award.json", verbose=True):
    parts, truth, tree, fid = ip.load_award_robot(award_path, use_alpha=True)
    # 只留結構件(tree 中的父/子);光暈(effect)不列入結構關節
    struct = set(tree) | {tree[c] for c in tree}
    parts = {p: parts[p] for p in parts if p in struct}
    scale = vp.rig_scale(parts, tree)

    pivots = ip.infer_pivots(parts, tree)
    jb, jpb, jpl = br.build_bone_chain(parts, tree, pivots)   # jointed rig
    fb, fpb, fpl = flat_chain(parts)                          # flat rig(負對照)

    # ---- AC1 setup round-trip(jointed 不移動任何件)----
    max_setup = 0.0
    for p in parts:
        w = br.part_world(p, jb, jpb, jpl, pose=None)
        max_setup = max(max_setup, float(np.abs(w - parts[p]).max()))
    ac1 = max_setup < 1e-2

    # ---- AC2 逐子件「轉自己骨」→ 不動點應落在真值關節 ----
    rows = []
    for c in tree:
        bnj = jpb[c]
        w0 = br.part_world(c, jb, jpb, jpl, pose=None)
        w1 = br.part_world(c, jb, jpb, jpl, pose={bnj: THETA})
        fpt_j = br.fixed_point_of_rotation(w0, w1)
        errj = float(np.linalg.norm(fpt_j - truth[c]))
        # flat:轉同名件骨
        bnf = fpb[c]
        f0 = br.part_world(c, fb, fpb, fpl, pose=None)
        f1 = br.part_world(c, fb, fpb, fpl, pose={bnf: THETA})
        fpt_f = br.fixed_point_of_rotation(f0, f1)
        errf = float(np.linalg.norm(fpt_f - truth[c]))
        rows.append((c, errj, errj / scale, errf, errf / scale))
    max_rel_j = max(r[2] for r in rows)
    med_j = float(np.median([r[1] for r in rows]))
    med_f = float(np.median([r[3] for r in rows]))
    ac2 = (max_rel_j < TAU) and (med_j < med_f)

    # ---- AC3 轉「身體(根件)」→ jointed 子件跟著動且剛體;flat 子件不動 ----
    root_part = [p for p in parts if p not in tree][0]
    # jointed:轉根件骨,量子件位移 + 全機剛體性
    j_disp, f_disp = {}, {}
    # 記全件 setup 世界點,及旋轉後世界點
    def all_world(bones, pb, pl, pose):
        return {p: br.part_world(p, bones, pb, pl, pose) for p in parts}
    jw0 = all_world(jb, jpb, jpl, None)
    jw1 = all_world(jb, jpb, jpl, {jpb[root_part]: THETA})
    fw0 = all_world(fb, fpb, fpl, None)
    fw1 = all_world(fb, fpb, fpl, {fpb[root_part]: THETA})
    for c in tree:
        j_disp[c] = float(np.linalg.norm(jw1[c].mean(0) - jw0[c].mean(0)))
        f_disp[c] = float(np.linalg.norm(fw1[c].mean(0) - fw0[c].mean(0)))
    # 全機剛體性:任兩件質心間距 setup vs 旋轉後 變化(jointed 應≈0)
    cen0 = {p: jw0[p].mean(0) for p in parts}
    cen1 = {p: jw1[p].mean(0) for p in parts}
    plist = list(parts)
    dchg = []
    for i in range(len(plist)):
        for k in range(i + 1, len(plist)):
            a, b = plist[i], plist[k]
            d0 = np.linalg.norm(cen0[a] - cen0[b]); d1 = np.linalg.norm(cen1[a] - cen1[b])
            dchg.append(abs(d1 - d0))
    rigid_max = float(max(dchg)) if dchg else 0.0
    child_moves = min(j_disp.values()) > 1.0            # jointed 子件確實跟著動
    flat_static = max(f_disp.values()) < 1e-6           # flat 子件完全不動(脫節)
    ac3 = child_moves and (rigid_max < 1e-6) and flat_static

    # ---- AC4 泛化界定(誠實)----
    sk = json.load(open(award_path))
    slot_names = [s["name"] for s in sk["slots"]]
    decomposed = sorted({n.split("/")[0] for n in slot_names if "/" in n})
    char_singletons = [n for n in slot_names if ("角色" in n)]
    ac4 = (decomposed == ["機器人拆件"]) and len(char_singletons) >= 3  # 僅機器人被拆

    if verbose:
        print(f"rig_scale(diag) = {scale:.1f}px   TAU={TAU}   θ={THETA}°\n")
        print("AC1 setup round-trip(jointed 不移件)")
        print(f"    max 位移 = {max_setup:.2e}px  -> {'PASS' if ac1 else 'FAIL'}\n")
        print("AC2 轉子件骨 → 不動點落在真值關節(jointed vs flat 負對照)")
        print(f"    {'joint':<16}{'jointed_px':>11}{'j/rig':>8}{'flat_px':>10}{'f/rig':>8}")
        for c, ej, rj, ef, rf in rows:
            print(f"    {c:<16}{ej:11.2f}{rj:8.3f}{ef:10.2f}{rf:8.3f}")
        print(f"    max jointed/rig={max_rel_j:.3f}(<{TAU})、中位 jointed {med_j:.1f}px < flat {med_f:.1f}px  -> {'PASS' if ac2 else 'FAIL'}\n")
        print("AC3 轉根件(身體)骨 → jointed 子件跟動+全機剛體;flat 子件不動")
        print(f"    jointed 子件位移 min={min(j_disp.values()):.1f}px(需>1)、"
              f"全機件距最大變化={rigid_max:.2e}(需≈0)")
        print(f"    flat 子件位移 max={max(f_disp.values()):.2e}px(需≈0,證明 flat 脫節)  -> {'PASS' if ac3 else 'FAIL'}\n")
        print("AC4 泛化界定(誠實)")
        print(f"    Award 被拆解群組={decomposed};單一 slot 角色={char_singletons}")
        print(f"    → 僅機器人被拆件,其餘角色單圖無拆件,無多 rig 接觸縫真值可驗  -> {'PASS(如實)' if ac4 else 'FAIL'}")

    return dict(scale=scale, max_setup=max_setup, ac2_rows=rows, max_rel_j=max_rel_j,
                j_disp=j_disp, f_disp=f_disp, rigid_max=rigid_max,
                decomposed=decomposed, char_singletons=char_singletons,
                ac1=ac1, ac2=ac2, ac3=ac3, ac4=ac4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    print("=" * 72)
    print("S5(b) pivot→骨鏈 接合閘 —— 真值=Award 機器人 rig")
    print("=" * 72)
    r = evaluate(a.award, verbose=True)
    overall = r["ac1"] and r["ac2"] and r["ac3"] and r["ac4"]
    print("\n" + "=" * 72)
    print(f"OVERALL: {'PASS ✅' if overall else 'FAIL ❌'}  "
          f"(AC1={r['ac1']} AC2={r['ac2']} AC3={r['ac3']} AC4={r['ac4']})")
    print("=" * 72)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=float, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
