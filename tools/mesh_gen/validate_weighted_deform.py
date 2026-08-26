#!/usr/bin/env python3
"""驗證 weighted-mesh deform 評估器本身可信(對 Award.json 真實 7 weighted mesh)。

補上 STATE 反覆標記的唯一未驗維度:weighted mesh 的**骨骼變形平滑度**(靜態 IoU 不涵蓋)。
評估器 = Spine 骨骼世界變換(normal mode,無 shear)+ linear blend skinning 重現;
幾何閘沿用自交/翻面/退化(向量化)。本檔跑三條可機讀 AC:

  AC1 skinning 正確性:7 個真實 weighted mesh 在 setup pose 重現皆為有效幾何
      (0 自交 / 0 退化)。骨/LBS 若錯,藝術 mesh 連靜止都會壞 → 這是評估器正確性的硬自檢。
  AC2 可見性 gating 生效:mesh 只在 slot 可見(alpha>0 且 attachment active)時被評估;
      驗證「alpha=0 fade-in 的髒幀」被正確排除(對照雷點 #3),且各 hero mesh 只落在自己 tier 的動畫。
  AC3 鑑別力(負對照):把一個藝術家乾淨 mesh(身體)的骨綁動一動(shift bone / jitter bind)
      → 可見幀必須變髒。證明閘非虛過。

誠實界定(重要):並非所有生產 weighted mesh 在可見幀都拓樸乾淨 —— 最複雜的 hero(superwin,
112v)在其擠壓/縮放 In 動畫可見階段真的自交(keyframe 上就有,非內插假象),soft halo 亦有少量。
故**不存在**「所有藝術 mesh worst==0」的通用閘;評估器對「生成 mesh」的用法是:對照**同一部位**
的藝術 mesh 在同一動畫的乾淨率,而非絕對 0。此檔輸出各 mesh 可見乾淨率供後續(BBW 生成)對照。
"""
import json, sys, random
import numpy as np
import weighted_deform_eval as W


def run(path="assets/Award.json"):
    sk = json.load(open(path))
    bones = W.build_bones(sk)
    rep = W.benchmark_weighted(path)
    meshes = {k: v for k, v in rep.items() if not k.startswith("_")}

    print("== 各 weighted mesh:可見乾淨率(visible clean-rate) ==")
    for k, v in meshes.items():
        n = len(v["anims"]); c = sum(1 for a in v["anims"].values() if a["all_clean"])
        gated = sum(a.get("gated_invisible", 0) for a in v["anims"].values())
        dirty = {an: (a["max_self_intersections"], a["max_triangle_flips"])
                 for an, a in v["anims"].items() if not a["all_clean"]}
        tag = "clean" if not dirty else f"dirty{dirty}"
        print(f"  {k:22s} nv={v['nv']:3d} setup_SI={v['setup']['self_intersections']} "
              f"visible-clean={c}/{n} gated={gated} {tag}")

    # ---- AC1 ----
    ac1 = rep["_setup_all_valid"]
    print(f"\nAC1 skinning 正確性(setup 全有效幾何): {'PASS' if ac1 else 'FAIL'}")

    # ---- AC2 gating:找一個有 alpha fade-in 的動畫,證明 gating 排除髒幀 ----
    # superwin/Award_Super_In:alpha 00→ff@0.067;未 gating 時 t=0 應非常髒
    def get(slot):
        for _, s, n, a in W._iter_meshes(sk):
            if s == slot:
                return n, a
    name, att = get("superwin_角色")
    dec, _ = W.decode_weighted(att)
    chk = W.MeshChecker(att["triangles"]); tris = chk.tris
    sp = [{"x": b["x"], "y": b["y"], "rot": b["rot"], "sx": b["sx"], "sy": b["sy"]} for b in bones]
    sv = W.skin(dec, W.world_affines(bones, sp))
    signs = chk.setup_signs(sv); area = float(np.abs(chk._areas(sv, tris)).sum())
    r0 = chk.check(W.skin(dec, W.world_affines(bones, W.pose_at(sk, bones, "Award_Super_In", 0.0))),
                   signs, area)
    sa = W._slot_setup_alpha(sk, "superwin_角色")
    a0 = W.slot_alpha_at(sk, "superwin_角色", "Award_Super_In", 0.0, sa)
    gated_in_report = any(a.get("gated_invisible", 0) > 0 for a in meshes["superwin_角色/superwin_角色"]["anims"].values())
    ac2 = (a0 <= 1.0 / 255) and (r0["self_intersections"] > 0) and gated_in_report
    print(f"AC2 可見性 gating(alpha=0 髒幀被排除): {'PASS' if ac2 else 'FAIL'} "
          f"(t=0 alpha={a0:.2f} 髒幀SI={r0['self_intersections']} 已gate;報告有gated幀={gated_in_report})")

    # ---- AC3 負對照:身體(藝術乾淨)corrupt → 變髒 ----
    bname, batt = get("機器人拆件/身體")
    base = W.eval_weighted_mesh(sk, bones, batt, slot="機器人拆件/身體", name="機器人拆件/身體")
    base_clean = all(a["all_clean"] for a in base["anims"].values())

    def shift_bone(d):
        allb = sorted({t[0] for e in d for t in e})
        for e in d:
            for t in e:
                t[0] = allb[(allb.index(t[0]) + 2) % len(allb)]
        return d

    def jitter(d):
        random.seed(3)
        for e in d:
            for t in e:
                t[1] += random.uniform(-100, 100); t[2] += random.uniform(-100, 100)
        return d
    caught = []
    for lab, mut in [("shift-bone", shift_bone), ("jitter±100", jitter)]:
        rr = W.eval_weighted_mesh(sk, bones, batt, slot="機器人拆件/身體", name="機器人拆件/身體", mutate=mut)
        bad = rr["worst"]["self_intersections"] > 0 or rr["worst"]["triangle_flips"] > 0
        caught.append(bad)
        print(f"AC3 負對照 {lab}: {'CAUGHT' if bad else 'MISSED'} (worst={rr['worst']})")
    ac3 = base_clean and all(caught)
    print(f"AC3 鑑別力(乾淨基準+腐化被抓): {'PASS' if ac3 else 'FAIL'}")

    print("\n== 結論 ==")
    print(f"  評估器可信(AC1 skinning 正確 + AC3 鑑別力): {'YES' if (ac1 and ac3) else 'NO'}")
    print(f"  gating 語意正確(AC2): {'YES' if ac2 else 'NO'}")
    print(f"  藝術真值觀察:{rep['_artist_clean_visible']['clean']}/{rep['_artist_clean_visible']['total']} "
          f"weighted mesh 在可見幀全乾淨;複雜 hero/halo 非絕對乾淨(誠實界定,見檔頭)。")
    overall = ac1 and ac2 and ac3
    print(f"\nOVERALL(評估器就緒可作 weighted 變形閘): {'PASS' if overall else 'FAIL'}")
    return overall


if __name__ == "__main__":
    ok = run(sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json")
    sys.exit(0 if ok else 1)
