#!/usr/bin/env python3
"""S3 — weighted-mesh deform 評估器:量化「骨骼權重驅動的 mesh」在真實 bone 動畫下的變形品質。

補上 `deform_eval.py` 的缺口:那支只處理 unweighted mesh(逐頂點 deform offset)。
真實美術對「會被骨骼拉扯的件」(機器人身體/左手/光暈)用 **weighted mesh**:每個頂點綁 1~3 根骨,
變形靠 LBS(linear blend skinning),不靠 deform timeline。要量化這種件的變形平滑度,必須:

  1) 由 skeleton bone 資料 + 動畫 timeline 做 **FK(前向運動學)** 算每根骨的世界仿射矩陣;
  2) 用 **Spine 加權 computeWorldVertices** 語意把 mesh 頂點推到世界座標;
  3) 對 pose 序列量化幾何品質(自交/翻面/退化)+ **變形平滑度**(邊長應變 edge-strain)。

⚠️ 只實作 transform mode = "normal"(Award 的 LEG 骨全 normal;非 normal 會 assert)。

自我品質閘(可信度):
  - 正對照:真實美術權重 + 真實 bone pose(Award_Legend_*) → 應乾淨 + 低應變。
  - 負對照:把權重退化成「硬指派最大權重骨」(無混合) → 骨界邊撕裂,max edge-strain 明顯升高。
  兩者在 SETUP pose 完全相同(bind 座標決定),差異只在動畫下 → 證明評估器能鑑別權重品質。
"""
import json, math
import numpy as np
from deform_eval import signed_area, check  # 幾何檢查沿用


# ---------- 解析 ----------
def load_skeleton(path):
    return json.load(open(path))


def bone_table(sk):
    """回傳 bones(list of dict,補上 parent index)與 name->index。"""
    bones = sk["bones"]
    idx = {b["name"]: i for i, b in enumerate(bones)}
    for b in bones:
        b["_pi"] = idx.get(b.get("parent"), -1)
        tm = b.get("transform", "normal")
        assert tm == "normal", f"bone {b['name']} transform={tm} 未支援(僅 normal)"
    return bones, idx


def parse_weighted_mesh(sk, slot, name):
    """回傳 (bindings, uvs Nx2, triangles Mx3, hull)。
    bindings[i] = [(boneIdx, bindX, bindY, weight), ...](和為 1)。"""
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    v = a["vertices"]; uv = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    assert len(v) != len(uv.reshape(-1)), "非 weighted mesh(vertices==uvs)"
    bindings = []
    i = 0
    while i < len(v):
        nb = int(v[i]); i += 1
        e = []
        for _ in range(nb):
            e.append((int(v[i]), v[i + 1], v[i + 2], v[i + 3])); i += 4
        bindings.append(e)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return bindings, uv, tris, a["hull"]


# ---------- 動畫 timeline 取值 ----------
def _val(frames, t, keys, defaults):
    """在 keyframe 序列 frames 上，於時間 t 線性內插取 keys 各值(缺鍵補 default)。
    忽略 bezier 曲線形狀(在 keyframe 時間點為精確值;之間為線性近似)。"""
    ts = [f.get("time", 0.0) for f in frames]
    if t <= ts[0]:
        f = frames[0]
        return [f.get(k, d) for k, d in zip(keys, defaults)]
    if t >= ts[-1]:
        f = frames[-1]
        return [f.get(k, d) for k, d in zip(keys, defaults)]
    for j in range(len(frames) - 1):
        if ts[j] <= t <= ts[j + 1]:
            f0, f1 = frames[j], frames[j + 1]
            span = ts[j + 1] - ts[j]
            a = 0.0 if span < 1e-9 else (t - ts[j]) / span
            out = []
            for k, d in zip(keys, defaults):
                v0 = f0.get(k, d); v1 = f1.get(k, d)
                out.append(v0 * (1 - a) + v1 * a)
            return out
    f = frames[-1]
    return [f.get(k, d) for k, d in zip(keys, defaults)]


def bone_local_at(sk, bone, anim, t):
    """回傳該骨在時間 t 的 local (x,y,rotation,scaleX,scaleY,shearX,shearY)。
    Spine 語意:rotate/shear/translate 為相對 setup 的『加』;scale 為『乘』。"""
    x = bone.get("x", 0.0); y = bone.get("y", 0.0)
    rot = bone.get("rotation", 0.0)
    sx = bone.get("scaleX", 1.0); sy = bone.get("scaleY", 1.0)
    shx = bone.get("shearX", 0.0); shy = bone.get("shearY", 0.0)
    if anim is None:
        return x, y, rot, sx, sy, shx, shy
    tl = sk["animations"][anim].get("bones", {}).get(bone["name"], {})
    if "translate" in tl:
        dx, dy = _val(tl["translate"], t, ["x", "y"], [0.0, 0.0]); x += dx; y += dy
    if "rotate" in tl:
        (da,) = _val(tl["rotate"], t, ["angle"], [0.0]); rot += da
    if "scale" in tl:
        mx, my = _val(tl["scale"], t, ["x", "y"], [1.0, 1.0]); sx *= mx; sy *= my
    if "shear" in tl:
        ex, ey = _val(tl["shear"], t, ["x", "y"], [0.0, 0.0]); shx += ex; shy += ey
    return x, y, rot, sx, sy, shx, shy


def _cosd(d): return math.cos(math.radians(d))
def _sind(d): return math.sin(math.radians(d))


def fk_world(sk, bones, anim, t):
    """FK:回傳每根骨的世界仿射 (a,b,c,d,wx,wy)。normal transform mode。
    world point = (a*lx + b*ly + wx, c*lx + d*ly + wy)。"""
    world = [None] * len(bones)
    order = []  # 拓樸序(parent 先)
    seen = [False] * len(bones)
    def visit(i):
        if seen[i]:
            return
        p = bones[i]["_pi"]
        if p >= 0:
            visit(p)
        seen[i] = True; order.append(i)
    for i in range(len(bones)):
        visit(i)
    for i in order:
        b = bones[i]
        x, y, rot, sx, sy, shx, shy = bone_local_at(sk, b, anim, t)
        rotY = rot + 90 + shy
        la = _cosd(rot + shx) * sx
        lb = _cosd(rotY) * sy
        lc = _sind(rot + shx) * sx
        ld = _sind(rotY) * sy
        p = b["_pi"]
        if p < 0:
            world[i] = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, pwx, pwy = world[p]
            world[i] = (
                pa * la + pb * lc,
                pa * lb + pb * ld,
                pc * la + pd * lc,
                pc * lb + pd * ld,
                pa * x + pb * y + pwx,
                pc * x + pd * y + pwy,
            )
    return world


# ---------- LBS ----------
def skin_vertices(bindings, world):
    """加權 computeWorldVertices:回傳 Nx2 世界座標。"""
    out = np.zeros((len(bindings), 2), dtype=np.float64)
    for i, e in enumerate(bindings):
        wx = wy = 0.0
        for bi, bx, by, w in e:
            a, b, c, d, tx, ty = world[bi]
            wx += (a * bx + b * by + tx) * w
            wy += (c * bx + d * by + ty) * w
        out[i] = (wx, wy)
    return out


# ---------- 變形平滑度指標 ----------
def edge_list(tris):
    es = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            es.add((min(int(a), int(b)), max(int(a), int(b))))
    return sorted(es)


def edge_strain(setup_w, posed_w, edges):
    """每邊 |len_posed/len_setup - 1|;回傳 (max, p95, median)。
    max_strain 量『整體變形幅度』(注意:幅度大不等於壞 —— 手隨動畫大幅擺動是對的);
    要當品質閘須『對照藝術家基準』相對比較,不是設絕對門檻(見 gate_candidate)。"""
    strains = []
    for a, b in edges:
        l0 = math.hypot(*(setup_w[a] - setup_w[b]))
        l1 = math.hypot(*(posed_w[a] - posed_w[b]))
        if l0 < 1e-6:
            continue
        strains.append(abs(l1 / l0 - 1.0))
    s = np.array(strains)
    return float(s.max()), float(np.percentile(s, 95)), float(np.median(s))


def degrade_hard(bindings):
    """負對照:每頂點只保留最大權重骨(權重=1),bind 座標不變 → 無混合、骨界撕裂。"""
    out = []
    for e in bindings:
        bi, bx, by, w = max(e, key=lambda z: z[3])
        out.append([(bi, bx, by, 1.0)])
    return out


# ---------- runner ----------
def anim_keytimes(sk, anim, bones_used):
    """該動畫中,用到的骨的所有 keyframe 時間(union),含 0 與 duration。"""
    ts = {0.0}
    b = sk["animations"][anim].get("bones", {})
    for bn, tl in b.items():
        for typ, frames in tl.items():
            for f in frames:
                ts.add(f.get("time", 0.0))
    return sorted(ts)


def deform_field(sk, bones, binds, tris, setup_w, setup_signs, edges, anim, substeps=4):
    """對單一動畫掃全時間軸,回傳該件在此動畫下的最壞幾何量化(topology + strain)。"""
    used = sorted({bi for e in binds for bi, *_ in e})
    kts = anim_keytimes(sk, anim, used)
    times = []
    for j in range(len(kts)):
        times.append(kts[j])
        if j + 1 < len(kts):
            for s in range(1, substeps):
                times.append(kts[j] + (kts[j + 1] - kts[j]) * s / substeps)
    agg = {"max_self_intersections": 0, "max_triangle_flips": 0, "max_degenerate": 0,
           "max_edge_strain": 0.0, "p95_edge_strain": 0.0, "frames": len(times)}
    for t in times:
        pw = skin_vertices(binds, fk_world(sk, bones, anim, t))
        r = check(pw, tris, setup_signs)
        ms, p95, _ = edge_strain(setup_w, pw, edges)
        agg["max_self_intersections"] = max(agg["max_self_intersections"], r["self_intersections"])
        agg["max_triangle_flips"] = max(agg["max_triangle_flips"], r["triangle_flips"])
        agg["max_degenerate"] = max(agg["max_degenerate"], r["degenerate"])
        agg["max_edge_strain"] = max(agg["max_edge_strain"], ms)
        agg["p95_edge_strain"] = max(agg["p95_edge_strain"], p95)
    agg["topology_clean"] = (agg["max_self_intersections"] == 0 and agg["max_triangle_flips"] == 0
                             and agg["max_degenerate"] == 0)
    return agg


def eval_weighted(sk, bones, slot, name, anim="Award_Legend_Loop"):
    """對一件 weighted mesh 在指定動畫(預設 Loop = 穩態可見)跑藝術家 vs 硬指派負對照。

    ⚠️ 動畫選擇:預設 **Loop**(角色穩定可見的狀態)。In/Out 為進出場轉場,含
       (a) 全域縮放(整體均勻應變,非撕裂;max≈p95、topology clean)與
       (b) attachment gating 下的隱藏極端 pose(CLAUDE.md 雷點 #2/#3)→ 不宜當品質基準。
    """
    bindings, uv, tris, hull = parse_weighted_mesh(sk, slot, name)
    edges = edge_list(tris)
    setup_w = skin_vertices(bindings, fk_world(sk, bones, None, 0.0))
    setup_signs = [signed_area(setup_w, t) > 0 for t in tris]

    art = deform_field(sk, bones, bindings, tris, setup_w, setup_signs, edges, anim)
    hard = deform_field(sk, bones, degrade_hard(bindings), tris, setup_w, setup_signs, edges, anim)
    ratio = round(hard["max_edge_strain"] / max(art["max_edge_strain"], 1e-6), 3)
    return {
        "slot": slot, "nverts": len(bindings), "tris": len(tris), "hull": hull,
        "bones_used": sorted({bi for e in bindings for bi, *_ in e}), "anim": anim,
        "artist": art, "hard_negctrl": hard,
        # 鑑別力:硬指派的 max edge-strain / 藝術家。>1 = 硬指派更撕裂(混合為必要);
        # ≈1 或 <1 = 該件混合非承重(綁定骨僅共同平移,無相對旋轉)→ 誠實回報「此件不需軟權重」。
        "strain_ratio_hard_over_artist": ratio,
        "blend_load_bearing": ratio > 1.5,
    }


def gate_candidate(sk, bones, slot, name, candidate_bindings, anim="Award_Legend_Loop", margin=0.15):
    """品質閘:給一組『生成的權重』(candidate_bindings,拓樸/bind 需與該件一致),
    判定其變形是否達藝術家基準。回傳 (pass, detail)。

    兩層判定(對照 repo 既有『對藝術家基準 + margin』範式):
      1) 拓樸硬閘:self-intersections / flips / degenerate 必為 0(絕對,無門檻爭議)。
      2) 平滑度相對閘:max_edge_strain ≤ 藝術家基準 ×(1+margin)
         (相對比較,避免『幅度大即壞』的誤判 —— 幅度基準取自同動畫的藝術家權重)。
    """
    bindings, uv, tris, hull = parse_weighted_mesh(sk, slot, name)
    edges = edge_list(tris)
    setup_w = skin_vertices(bindings, fk_world(sk, bones, None, 0.0))
    signs = [signed_area(setup_w, t) > 0 for t in tris]
    base = deform_field(sk, bones, bindings, tris, setup_w, signs, edges, anim)
    cand = deform_field(sk, bones, candidate_bindings, tris, setup_w, signs, edges, anim)
    topo_ok = cand["topology_clean"]
    strain_ok = cand["max_edge_strain"] <= base["max_edge_strain"] * (1 + margin)
    return (topo_ok and strain_ok), {
        "topology_clean": topo_ok,
        "strain_ok": strain_ok,
        "candidate_max_strain": round(cand["max_edge_strain"], 3),
        "artist_baseline_max_strain": round(base["max_edge_strain"], 3),
        "allowed": round(base["max_edge_strain"] * (1 + margin), 3),
    }


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    sk = load_skeleton(path)
    bones, idx = bone_table(sk)
    targets = [
        ("機器人拆件/身體", "機器人拆件/身體"),
        ("機器人拆件/左手", "機器人拆件/左手"),
        ("機器人拆件/光暈", "機器人拆件/光暈"),
    ]
    out = {}
    for slot, name in targets:
        r = eval_weighted(sk, bones, slot, name)
        out[slot] = r
        # 自驗:藝術家權重在 Loop 必須拓樸乾淨(正對照)
        assert r["artist"]["topology_clean"], f"{slot} 藝術家權重在 Loop 竟不乾淨(FK/LBS 疑有 bug)"
    # 鑑別力自驗:至少一件(混合承重的光暈)硬指派 strain 明顯高於藝術家
    disc = any(v["strain_ratio_hard_over_artist"] > 1.5 for v in out.values())
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("\n_checker_validated (藝術家全乾淨 + 至少一件負對照可鑑別):", disc)
    # 示範 gate_candidate:對『身體』用硬指派當 candidate,看閘怎麼判
    body = "機器人拆件/身體"
    bd, *_ = parse_weighted_mesh(sk, body, body)
    p, det = gate_candidate(sk, bones, body, body, degrade_hard(bd))
    print(f"gate_candidate(身體, 硬指派權重) → pass={p} {det}")
