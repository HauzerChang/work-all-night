"""S5 rig pivot 推斷器的**自我品質閘**(對真實 Award 機器人 rig 真值 + 負對照)。

真值:Award.json 中機器人子 rig 的骨世界位置(藝術家親手放的 pivot):
  身體=4_LEG3(子 rig 根)、頭=4_LEG4、左手=4_LEG5、右手=4_LEG6。
輸入:各件世界多邊形(mesh hull 世界頂點 / region 由 atlas alpha 取真實輪廓)。

四道校驗(客觀、可機讀 pass/fail):
  AC1 準度   —— 每個結構關節 err/rig_scale < TAU(TAU=0.10;draft 級,人再微調)。
  AC2 勝過天真 baseline —— contact-seam 中位誤差 < 用子件質心當 pivot 的中位誤差。
  AC3 負對照 —— (a) 隨機 pivot、(b) 關節互換,兩者中位 err/rig 皆 >> TAU(閘抓得到 → 有鑑別力)。
  AC4 輸入保真依賴 —— 用粗略 bounding-rect 代理(--no-alpha)時 max err 爆掉(> TAU);
                    佐證「pivot 推斷品質取決於件輪廓保真」= PSD-first 論點在 rig 階段的再現。

誠實界定:本閘只驗「關節落在父子接觸縫」這個**可客觀化**子問題;pivot 沿肢體軸的精修、
以及動起來的手感,屬美術微調(RULES A 類),不在此閘。
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import infer_pivots as ip  # noqa: E402

TAU = 0.10          # 準度門檻(rig_scale 分數)
SEED = 20260829     # 負對照可重現


def rig_scale(parts, tree):
    """正規化基準 = 父件(軀幹)bounding box 對角線 —— 肢體 pivot 相對軀幹擺放,
    軀幹是穩定參考;不用整體聯集(會被外伸的手+劍撐爆,虛化誤差)。"""
    parents = {tree[c] for c in tree if tree[c] in parts}
    diags = [float(np.hypot(*(parts[p].max(0) - parts[p].min(0)))) for p in parents]
    return float(np.mean(diags)) if diags else 1.0


def errors(inf, truth, tree):
    return {c: float(np.linalg.norm(inf[c] - truth[c])) for c in tree if c in inf}


def evaluate(award_path="assets/Award.json", use_alpha=True, verbose=True):
    parts, truth, tree, fid = ip.load_award_robot(award_path, use_alpha=use_alpha)
    scale = rig_scale(parts, tree)

    inf = ip.infer_pivots(parts, tree)
    err = errors(inf, truth, tree)
    base = ip.centroid_baseline(parts, tree)
    berr = errors(base, truth, tree)

    rel = {c: err[c] / scale for c in err}
    max_rel = max(rel.values())
    med_rel = float(np.median(list(rel.values())))
    med_err = float(np.median(list(err.values())))
    med_base = float(np.median(list(berr.values())))

    # ---- 負對照 (a) 隨機 pivot ----
    rng = np.random.default_rng(SEED)
    allp = np.vstack([parts[c] for c in tree])
    lo, hi = allp.min(0), allp.max(0)
    rand = {c: lo + rng.random(2) * (hi - lo) for c in tree}
    rerr = errors(rand, truth, tree)
    rand_med_rel = float(np.median([rerr[c] / scale for c in tree]))

    # ---- 負對照 (b) 關節互換(把推斷值輪轉指派給錯誤關節)----
    keys = list(tree.keys())
    rot = {keys[i]: inf[keys[(i + 1) % len(keys)]] for i in range(len(keys))}
    swerr = errors(rot, truth, tree)
    swap_med_rel = float(np.median([swerr[c] / scale for c in tree]))

    ac1 = max_rel < TAU
    ac2 = med_err < med_base
    ac3 = (rand_med_rel > TAU) and (swap_med_rel > TAU)

    if verbose:
        print(f"rig_scale(diag) = {scale:.1f}px   TAU = {TAU}")
        print(f"{'joint':<16}{'fidelity':<10}{'err_px':>9}{'err/rig':>9}{'baseline_px':>13}")
        for c in tree:
            print(f"{c:<16}{fid[c]:<10}{err[c]:9.2f}{rel[c]:9.3f}{berr[c]:13.2f}")
        print(f"\nAC1 準度       max err/rig={max_rel:.3f} (<{TAU})  -> {'PASS' if ac1 else 'FAIL'}")
        print(f"AC2 勝 baseline 中位 {med_err:.1f}px < baseline {med_base:.1f}px  -> {'PASS' if ac2 else 'FAIL'}")
        print(f"AC3 負對照     random med/rig={rand_med_rel:.3f}, swap med/rig={swap_med_rel:.3f} (皆>{TAU}) -> {'PASS' if ac3 else 'FAIL'}")

    return dict(scale=scale, err=err, rel=rel, max_rel=max_rel, med_rel=med_rel,
                med_err=med_err, med_base=med_base, fidelity=fid,
                rand_med_rel=rand_med_rel, swap_med_rel=swap_med_rel,
                ac1=ac1, ac2=ac2, ac3=ac3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--json", action="store_true", help="輸出機讀 JSON 摘要")
    args = ap.parse_args()

    print("=" * 70)
    print("S5 rig pivot 推斷閘 —— 真值=Award 機器人 rig(藝術家 pivot)")
    print("=" * 70)
    r = evaluate(args.award, use_alpha=True, verbose=True)

    # ---- AC4:輸入保真依賴(rect 代理應爆掉)----
    print("\n--- AC4 輸入保真依賴(rect 代理 vs alpha 輪廓)---")
    rr = evaluate(args.award, use_alpha=False, verbose=False)
    ac4 = rr["max_rel"] > TAU
    print(f"rect 代理 max err/rig = {rr['max_rel']:.3f}  (alpha={r['max_rel']:.3f}) "
          f"-> rect 爆閘 {'PASS' if ac4 else 'FAIL(未爆,代理已足夠?)'}")

    overall = r["ac1"] and r["ac2"] and r["ac3"] and ac4
    print("\n" + "=" * 70)
    print(f"OVERALL: {'PASS ✅' if overall else 'FAIL ❌'}  "
          f"(AC1={r['ac1']} AC2={r['ac2']} AC3={r['ac3']} AC4={ac4})")
    print("=" * 70)

    if args.json:
        out = {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items()})
               for k, v in r.items()}
        out["ac4"] = ac4
        out["overall"] = bool(overall)
        print(json.dumps(out, ensure_ascii=False, default=float, indent=2))

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
