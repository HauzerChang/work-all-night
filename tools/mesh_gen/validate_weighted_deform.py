#!/usr/bin/env python3
"""S3 — weighted-mesh deform 評估器的**可信度自驗**(校準閘的雙向鑑別力)。

閘要可信,必須同時:
  (正) 美術真值 weighted mesh 對照**自己的基準線** → PASS(margin=0,恆成立 → 自一致)。
  (負) 對美術 mesh 做已知破壞(交換相鄰頂點的骨綁定)→ 變形拓樸應爆掉 → 對基準線 FAIL。

⚠️ 為何不是「絕對 si==0 & flips==0」:見 `skinning_eval.py` 校準教訓(光暈/superwin 美術真值本身非零)。
此腳本證明「相對基準線」的閘既不誤殺美術、又抓得到真破壞。

跑法:`PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/validate_weighted_deform.py`
      全 PASS → exit 0。
"""
import json, copy, sys
import numpy as np
import skinning_eval as S


def corrupt_swap_bindings(wv):
    """負對照:交換相鄰頂點的整組骨綁定 → 頂點被拉到錯位置 → 撕裂/自交。"""
    bad = copy.deepcopy(wv)
    for i in range(0, len(bad) - 1, 2):
        bad[i], bad[i + 1] = bad[i + 1], bad[i]
    return bad


def eval_wv(skel, wv, tris, anims):
    """對任意 weighted-vertex 陣列(不從 json 讀,直接算)逐動畫聚合,回傳 anims dict。"""
    W0 = skel.world(skel.setup); v0 = S.skin_deform(skel, wv, W0)
    signs = [S.signed_area(v0, t) > 0 for t in tris]
    setup_area = sum(abs(S.signed_area(v0, t)) for t in tris)
    bn = set(skel.bones[bi]["name"] for e in wv for (bi, *_ ) in e)
    per = {}
    for anim in anims:
        kts = skel.anim_keytimes(anim, bone_filter=bn)
        if len(kts) <= 1:
            continue
        times = []
        for i, t in enumerate(kts):
            times.append(t)
            if i + 1 < len(kts):
                for s in range(1, 4):
                    times.append(t + (kts[i + 1] - t) * s / 4)
        res = []
        for t in times:
            W = skel.world(skel.pose_local(anim, t)); v = S.skin_deform(skel, wv, W)
            r = S.eval_pose(v, tris, signs, setup_area)
            ecv, acv = S.smoothness(v, tris)
            r["edge_cv"] = ecv; r["area_cv"] = acv
            res.append(r)
        per[anim] = {
            "frames": len(res),
            "max_self_intersections": max(r["self_intersections"] for r in res),
            "max_triangle_flips": max(r["triangle_flips"] for r in res),
            "max_degenerate": max(r["degenerate"] for r in res),
            "area_ratio_range": [min(r["area_ratio"] for r in res), max(r["area_ratio"] for r in res)],
            "max_edge_cv": max(r["edge_cv"] for r in res),
            "max_area_cv": max(r["area_cv"] for r in res),
            "all_clean": all(r["clean"] for r in res),
        }
    return per


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    sk = json.load(open(path)); skel = S.Skel(sk)
    pieces = S.all_weighted_pieces(sk)
    anims = list(sk["animations"].keys())

    pos_pass = 0; neg_caught = 0; total = 0
    print(f"# weighted-deform 閘自驗(校準式相對基準線),{len(pieces)} 件\n")
    for slot, nm in pieces:
        a = S.get_mesh(sk, slot, nm)
        wv = S.parse_weighted(a["vertices"])
        tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
        base = eval_wv(skel, wv, tris, anims)
        if not base:
            print(f"  - {slot}/{nm}: (無動畫驅動,略過)")
            continue
        total += 1
        # 正對照:自己 vs 自己基準線 → 必 PASS
        ok_pos, r_pos = S.gate_against_baseline(base, base)
        # 負對照:破壞綁定 vs 原基準線 → 必 FAIL
        badwv = corrupt_swap_bindings(wv)
        badm = eval_wv(skel, badwv, tris, anims)
        ok_neg, r_neg = S.gate_against_baseline(badm, base)
        pos_pass += int(ok_pos); neg_caught += int(not ok_neg)
        # 摘要:此件在真實動畫下的美術基準(worst across anims)
        wsi = max(v["max_self_intersections"] for v in base.values())
        wfl = max(v["max_triangle_flips"] for v in base.values())
        tag = "PASS" if (ok_pos and not ok_neg) else "**FAIL**"
        print(f"  - {slot}/{nm}: baseline(worst si={wsi} flips={wfl})  "
              f"self→{'PASS' if ok_pos else 'FAIL'}  corrupt→{'caught' if not ok_neg else 'MISSED'}  [{tag}]")
        if not ok_pos:
            print(f"      self-consistency broke: {r_pos[:3]}")
        if ok_neg:
            print(f"      negative control MISSED (gate too loose)")

    print(f"\n== 正對照(自一致){pos_pass}/{total}  負對照(抓到破壞){neg_caught}/{total}")
    all_ok = (pos_pass == total and neg_caught == total and total > 0)
    print("RESULT:", "PASS ✅ 閘雙向可信" if all_ok else "FAIL ❌")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
