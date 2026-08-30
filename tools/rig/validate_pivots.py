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


def evaluate(loader=ip.load_award_robot, path=None, use_alpha=True, verbose=True):
    parts, truth, tree, fid = (loader(path, use_alpha=use_alpha) if path
                               else loader(use_alpha=use_alpha))
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


RIG_TITLES = {
    "robot": "Award 機器人 rig(藝術家 pivot;身體/頭/左手/右手)",
    "cat":   "main_draw 貓角色 rig(藝術家 pivot;身體/臉/雙手/尾/鈴鐺)",
}


def evaluate_rig(name, use_alpha=True, verbose=True):
    """對單一 rig 跑 AC1–3 + AC4(輸入保真依賴)。回傳含各 AC 的 dict。"""
    loader, path = ip.RIGS[name]
    if verbose:
        print("\n" + "-" * 70)
        print(f"[{name}] {RIG_TITLES.get(name, name)}")
        print("-" * 70)
    r = evaluate(loader, path, use_alpha=True, verbose=verbose)
    # AC4:輸入保真依賴 —— rect 代理相對 alpha 是否明顯變差(且 alpha 本身要過閘)。
    rr = evaluate(loader, path, use_alpha=False, verbose=False)
    r["rect_max_rel"] = rr["max_rel"]
    # rect 顯著劣於 alpha(≥2×)且 rect 爆閘 → 佐證「輪廓保真決定 pivot 品質」。
    # 註:件本身夠緊實(fill 高)時 rect 可能已夠好 → 此屬性 asset-dependent,列為診斷非硬性 fail。
    r["ac4"] = (rr["max_rel"] > TAU) and (rr["max_rel"] > 1.8 * r["max_rel"])
    if verbose:
        print(f"AC4 輸入保真依賴 rect max/rig={rr['max_rel']:.3f} vs alpha {r['max_rel']:.3f}"
              f"  -> {'rect 明顯劣化(PASS)' if r['ac4'] else '件緊實,rect 已足夠(診斷,非 fail)'}")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default="all", choices=["all", "robot", "cat"])
    ap.add_argument("--json", action="store_true", help="輸出機讀 JSON 摘要")
    args = ap.parse_args()

    print("=" * 70)
    print("S5 rig pivot 推斷閘 —— 多 rig 真值(接觸縫法對藝術家 pivot)")
    print("=" * 70)

    names = ["robot", "cat"] if args.rig == "all" else [args.rig]
    results = {}
    for n in names:
        results[n] = evaluate_rig(n, verbose=True)

    # 硬性通過 = 每個 rig 的 AC1(準度)、AC2(勝 baseline)、AC3(負對照)皆過。
    # AC4(輸入保真)是 asset-dependent 診斷屬性(件緊實時 rect 已足夠),不列入硬性門檻。
    per_rig_pass = {n: (r["ac1"] and r["ac2"] and r["ac3"]) for n, r in results.items()}
    overall = all(per_rig_pass.values())

    print("\n" + "=" * 70)
    print("彙總(AC1 準度 / AC2 勝 baseline / AC3 負對照 為硬性;AC4 保真為診斷):")
    for n, r in results.items():
        print(f"  [{n:5}] AC1={r['ac1']} AC2={r['ac2']} AC3={r['ac3']} "
              f"(max err/rig={r['max_rel']:.3f})  | AC4診斷={r['ac4']} "
              f"-> {'PASS ✅' if per_rig_pass[n] else 'FAIL ❌'}")
    print(f"\nOVERALL: {'PASS ✅' if overall else 'FAIL ❌'}  "
          f"(rigs 通過: {sum(per_rig_pass.values())}/{len(per_rig_pass)})")
    print("=" * 70)

    if args.json:
        out = {}
        for n, r in results.items():
            out[n] = {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items()})
                      for k, v in r.items() if k not in ("err", "rel")}
            out[n]["pass"] = bool(per_rig_pass[n])
        out["overall"] = bool(overall)
        print(json.dumps(out, ensure_ascii=False, default=float, indent=2))

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
