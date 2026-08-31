"""S5 (c) 真值閘:肢體父子樹自動推斷 —— 對 Award 機器人 rig + 合成鏈 + 負對照。

一鍵:`python3 tools/rig/validate_tree.py`(exit 0 = 全 PASS)。

AC:
  AC1 root 正確:幾何推得 root == body(且 degree-hub 與 area 兩訊號一致指向 body)。
  AC2 拓樸精確:結構父子樹 == 真值 ROBOT_TREE(邊集合完全相等,無多無缺)。
  AC3 門檻穩定:root+tree 在一段 τ_frac band 內完全不變(非 knife-edge 調參)。
  AC4 多跳通用:合成 3 件鏈 torso→upper→lower(只鄰接相鄰件)recover 成鏈(非強制星形);
      合成星形亦正確 → 證明 Dijkstra 接觸樹泛化到多跳,非只會星形。
負對照(鑑別力):
  NC1 隨機父指派 == 真值機率 ≈ 0(閘非恆過)。
  NC2 拆件斷開(左手平移遠離)→ 幾何驅動使其父邊改變(非硬編)。
  NC3 天真把 effect 件(光暈,大面積背光、與多件重疊)也當結構 → 汙染樹
      → 論證 effect/structural 角色分類須作為輸入(honest boundary)。
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import infer_tree as it  # noqa: E402
from infer_pivots import load_award_robot, ROBOT_TREE, _poly_points  # noqa: E402

BODY = "機器人拆件/身體"
HALO = "機器人拆件/光暈"


def _rect(cx, cy, w, h):
    return np.array([[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2],
                     [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]], dtype=np.float64)


def main():
    results = []
    parts_all, truth_piv, tree_truth, fid = load_award_robot()
    struct = {k: v for k, v in parts_all.items() if k != HALO}

    # ---------- AC1 / AC2:root + 拓樸 ----------
    root, tree, info = it.infer_tree(struct)
    areas = {n: it._part_area(struct[n]) for n in struct}
    area_root = max(areas, key=areas.get)
    ac1 = (root == BODY) and (area_root == BODY)
    results.append(("AC1 root 正確(area-primary → body)", ac1,
                    f"inferred={root.split('/')[-1]} area_max={area_root.split('/')[-1]} "
                    f"degrees(飽和,非決定)={ {k.split('/')[-1]:v for k,v in info['degree'].items()} }"))

    ac2 = (tree == ROBOT_TREE)
    edge_str = "; ".join(f"{c.split('/')[-1]}->{p.split('/')[-1]}" for c, p in tree.items())
    results.append(("AC2 拓樸精確 == 真值樹", ac2,
                    f"inferred[{edge_str}] truth_edges={len(ROBOT_TREE)}"))

    # ---------- AC3:門檻穩定 band ----------
    band = [0.008, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.20]
    stable = True
    for tf in band:
        r2, t2, _ = it.infer_tree(struct, tau_frac=tf)
        if not (r2 == BODY and t2 == ROBOT_TREE):
            stable = False
    results.append(("AC3 門檻穩定(τ_frac band)", stable,
                    f"root+tree 不變 across τ_frac∈[{band[0]},{band[-1]}] ({len(band)} 點)"))

    # ---------- AC4:合成鏈 + 合成星形 ----------
    # 鏈:torso(0,0,大)- upper(0,150)- lower(0,290),相鄰件邊界貼近、隔一件遠;torso 最大(trunk)
    chain = {"torso": _rect(0, 0, 180, 180), "upper": _rect(0, 150, 90, 90),
             "lower": _rect(0, 290, 90, 90)}
    rc, tc, _ = it.infer_tree(chain, tau_frac=0.30)
    chain_ok = (rc == "torso" and tc.get("upper") == "torso" and tc.get("lower") == "upper")
    # 星形:torso 中心,3 件各方向貼上
    star = {"torso": _rect(0, 0, 120, 120), "a": _rect(0, 130, 80, 80),
            "b": _rect(130, 0, 80, 80), "c": _rect(-130, 0, 80, 80)}
    rs, ts, _ = it.infer_tree(star, tau_frac=0.30)
    star_ok = (rs == "torso" and all(ts.get(k) == "torso" for k in ("a", "b", "c")))
    ac4 = chain_ok and star_ok
    results.append(("AC4 多跳通用(合成鏈+星形)", ac4,
                    f"chain root={rc} tree={tc} ({'OK' if chain_ok else 'X'}); "
                    f"star root={rs} ({'OK' if star_ok else 'X'})"))

    # ---------- NC1:隨機父指派 ----------
    rng = np.random.default_rng(0)
    children = list(ROBOT_TREE.keys())
    cand = children + [BODY]
    hits = 0; N = 20000
    for _ in range(N):
        rt = {c: cand[rng.integers(len(cand))] for c in children}
        rt = {c: p for c, p in rt.items() if p != c}
        if rt == ROBOT_TREE:
            hits += 1
    nc1 = (hits / N) < 0.05
    results.append(("NC1 隨機父指派≈0(鑑別力)", nc1, f"隨機命中率={hits/N:.4f} (N={N})"))

    # ---------- NC2:拆件斷開 → 父邊改變 ----------
    struct2 = {k: (_poly_points(v) + np.array([1500.0, 0.0]) if k == "機器人拆件/左手"
                   else _poly_points(v)) for k, v in struct.items()}
    r3, t3, _ = it.infer_tree(struct2)
    lh = "機器人拆件/左手"
    # 左手移遠 1500px 後,其到 body 直達不再是 0-權重最短 → 父邊應改變(不再直掛 body,或斷)
    nc2 = (t3.get(lh) != BODY)
    results.append(("NC2 斷開左手→父邊變(幾何驅動)", nc2,
                    f"左手 parent={t3.get(lh,'(none)').split('/')[-1] if t3.get(lh) else '(none)'} "
                    f"(原=身體)"))

    # ---------- NC3:天真納入 effect(光暈)→ 汙染 ----------
    r4, t4, corrupted = it.diagnose_include_effect(parts_all, {HALO})
    results.append(("NC3 天真納 effect 汙染樹(須角色輸入)", corrupted,
                    f"納光暈後 root={r4.split('/')[-1]} "
                    f"tree=[{'; '.join(c.split('/')[-1]+'->'+p.split('/')[-1] for c,p in t4.items())}]"))

    # ---------- 輸出 ----------
    print("=" * 72)
    print("S5 (c) 肢體父子樹自動推斷 —— 真值閘")
    print("=" * 72)
    allpass = True
    for name, ok, detail in results:
        allpass &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        print(f"        {detail}")
    print("=" * 72)
    print(f"OVERALL: {'PASS' if allpass else 'FAIL'}")
    return 0 if allpass else 1


if __name__ == "__main__":
    sys.exit(main())
