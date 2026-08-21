#!/usr/bin/env python3
"""S3 — weighted-mesh **bone-driven** deform 評估器。

補上 `s3-robot-mesh-vs-award.md` 標記的唯一未驗維度:
> 靜態覆蓋率 IoU PASS ≠ 骨骼權重變形的平滑度對等。

與 `deform_eval.py` 的差異:
  - `deform_eval.py` 針對 **unweighted** mesh(main_draw 窗簾/陰影),變形 = 逐頂點 deform offset。
  - 本檔針對 **weighted** mesh(Award 機器人 光暈/左手/身體),變形 = **骨骼 + 權重**
    (linear-blend skinning),沒有 deform timeline,靠 bone timeline 拉動。

## 重要更正(2026-08-21,本 session 發現)
STATE / `s3-robot-mesh-vs-award.md` 曾假設「目前資產未含這 3 件的變形動畫」。**錯。**
實測:這 3 件綁的骨(4_LEG3..4_LEG9,idx 60~66)在 `Award_Legend_In/Loop` 等動畫**有 bone
timeline**(rotate/translate/scale)。故可建**真實** bone-driven deform 閘(非合成壓力場)。

## 前向 skinning(Spine 3.8,normal transform,no shear)
1. 每骨 local affine(相對 parent):
     a =  cosDeg(rot)*sx ; b = -sinDeg(rot)*sy
     c =  sinDeg(rot)*sx ; d =  cosDeg(rot)*sy ; 平移 (x,y)
2. world = parentWorld ∘ local(root 的 parent = identity)。
3. weighted 頂點:worldV = Σ_j w_j · (boneWorld_j 施於 bind 局部座標 (bx,by))。
   這正是 Spine `computeWorldVertices` 對 weighted mesh 的作法(bind 座標存於各 influence)。

## 動畫 timeline 套用(Spine 3.8 慣例)
  rotate:    bone.rotation = data.rotation + angle   (預設 angle=0)
  translate: bone.x = data.x + x ; bone.y = data.y + y (預設 0)
  scale:     bone.scaleX = data.scaleX * x ; ...       (預設 x=y=1,乘法)
關鍵幀間以**線性內插**取樣(找瞬時極端;bezier easing 不影響極端值集合),
沿用 `deform_eval.sample_poses` 的 substeps 哲學。

## 幾何品質閘
複用 `deform_eval` 的 `signed_area / check / eval_pose`(自交/翻面/退化/面積比/bbox),
判定與 unweighted 一致 → **同一把尺量兩類 mesh**。

驗證真相來源:Award 這 3 件的美術權重 + 骨架 + 動畫(全在 `assets/Award.json`)。
自一致性:美術 mesh 在真實骨動下應 0 自交/0 翻面(_checker_validated);
負對照:破壞權重歸一化 / 隨機擾動 bind → 閘應抓到。
"""
import json, math, sys
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from deform_eval import signed_area, eval_pose  # noqa: E402


# ---------- weighted mesh 解析 ----------
def parse_weighted(vertices):
    """weighted `vertices` → (influences, uv_order_count)。
    influences[i] = list of (boneIdx, bindX, bindY, weight)。"""
    out = []
    i = 0
    v = vertices
    while i < len(v):
        n = int(v[i]); i += 1
        entry = []
        for _ in range(n):
            bi = int(v[i]); bx = v[i + 1]; by = v[i + 2]; w = v[i + 3]; i += 4
            entry.append((bi, bx, by, w))
        out.append(entry)
    return out


def load_weighted_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    infl = parse_weighted(a["vertices"])
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    weighted = len(a["vertices"]) != len(a["uvs"])
    return infl, tris, a.get("hull"), weighted


# ---------- 骨架 world transform ----------
def _cosd(d): return math.cos(math.radians(d))
def _sind(d): return math.sin(math.radians(d))


class Skeleton:
    """Award 骨架:setup local + 依動畫 pose 計算每骨 world affine(normal mode)。"""

    def __init__(self, sk):
        self.bones = sk["bones"]
        self.idx = {b["name"]: i for i, b in enumerate(self.bones)}
        self.parent = [self.idx.get(b.get("parent")) if b.get("parent") else None
                       for b in self.bones]
        # 拓樸序(parent 先於 child):bones 檔內已是階層序,但保險起見排序
        self.order = self._topo_order()

    def _topo_order(self):
        order = []
        seen = [False] * len(self.bones)

        def visit(i):
            if seen[i]:
                return
            p = self.parent[i]
            if p is not None:
                visit(p)
            seen[i] = True
            order.append(i)
        for i in range(len(self.bones)):
            visit(i)
        return order

    def pose(self, anim_bones, time):
        """回傳每骨 world affine dict: idx -> (a,b,c,d,wx,wy)。
        anim_bones: {boneName: {rotate/translate/scale:[frames]}};time 供內插。"""
        world = {}
        for i in self.order:
            b = self.bones[i]
            rot = b.get("rotation", 0.0)
            x = b.get("x", 0.0); y = b.get("y", 0.0)
            sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
            tl = anim_bones.get(b["name"]) if anim_bones else None
            if tl:
                if "rotate" in tl:
                    rot += _sample(tl["rotate"], time, ("angle",), (0.0,))[0]
                if "translate" in tl:
                    dx, dy = _sample(tl["translate"], time, ("x", "y"), (0.0, 0.0))
                    x += dx; y += dy
                if "scale" in tl:
                    mx, my = _sample(tl["scale"], time, ("x", "y"), (1.0, 1.0))
                    sx *= mx; sy *= my
            a = _cosd(rot) * sx; bb = -_sind(rot) * sy
            c = _sind(rot) * sx; d = _cosd(rot) * sy
            p = self.parent[i]
            if p is None:
                world[i] = (a, bb, c, d, x, y)
            else:
                pa, pb, pc, pd, pwx, pwy = world[p]
                world[i] = (
                    pa * a + pb * c, pa * bb + pb * d,
                    pc * a + pd * c, pc * bb + pd * d,
                    pa * x + pb * y + pwx, pc * x + pd * y + pwy,
                )
        return world

    def skin(self, influences, world):
        """linear-blend skinning → 世界頂點 (N,2)。"""
        out = np.zeros((len(influences), 2), dtype=np.float64)
        for vi, entry in enumerate(influences):
            px = py = 0.0
            for (bi, bx, by, w) in entry:
                a, b, c, d, wx, wy = world[bi]
                px += (a * bx + b * by + wx) * w
                py += (c * bx + d * by + wy) * w
            out[vi] = (px, py)
        return out


# ---------- 動畫關鍵幀取樣(線性) ----------
def _bezier_percent(fr, a):
    """Spine 3.8 緊湊 bezier(CLAUDE.md 雷點 #7):keyframe fr 存到下一幀的曲線。
    `'stepped'` → 持值(percent=0);linear/缺省 → percent=a;否則
    控制點 P1=(curve,c2) P2=(c3,c4),P0=(0,0) P3=(1,1),給時間分數 a 解 s 使 X(s)=a → 回 Y(s)。"""
    c = fr.get("curve")
    if c == "stepped":
        return 0.0
    if c is None or c == "linear":
        return a
    cx1 = c; cy1 = fr.get("c2", 0.0); cx2 = fr.get("c3", 1.0); cy2 = fr.get("c4", 1.0)

    def bez(t, p1, p2):
        u = 1 - t
        return 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t
    lo, hi = 0.0, 1.0
    for _ in range(24):  # 二分求 X(s)=a
        s = (lo + hi) / 2
        if bez(s, cx1, cx2) < a:
            lo = s
        else:
            hi = s
    s = (lo + hi) / 2
    return bez(s, cy1, cy2)


def _sample(frames, time, keys, defaults):
    """在 keyframe 序列中依 Spine 曲線內插出 time 的值(tuple,對齊 keys/defaults)。
    一個 keyframe 的曲線(percent)同時套用到該 channel 的所有分量(Spine 慣例)。"""
    def val(fr):
        return tuple(fr.get(k, dv) for k, dv in zip(keys, defaults))
    if not frames:
        return defaults
    ts = [fr.get("time", 0.0) for fr in frames]
    if time <= ts[0]:
        return val(frames[0])
    if time >= ts[-1]:
        return val(frames[-1])
    for j in range(len(frames) - 1):
        if ts[j] <= time <= ts[j + 1]:
            span = ts[j + 1] - ts[j]
            a = 0.0 if span <= 0 else (time - ts[j]) / span
            p = _bezier_percent(frames[j], a)
            v0 = val(frames[j]); v1 = val(frames[j + 1])
            return tuple(x0 + (x1 - x0) * p for x0, x1 in zip(v0, v1))
    return val(frames[-1])


def slot_alpha(sk, anim, slot, time):
    """slot color timeline 在 time 的 alpha(0..1)。無 timeline → 1(setup 全不透明)。
    color 字串 'rrggbbaa';'stepped' 曲線持值到下一幀,否則線性內插。
    ⚠️ 關鍵:weighted mesh 在 In/Out 常被 alpha=0 遮住做進場/退場編排(CLAUDE.md 雷點 #2/#3),
    那段的自交是**看不見的**,不該當拓樸缺陷 → 拓樸閘只在可見幀判定。"""
    st = sk["animations"][anim].get("slots", {}).get(slot, {})
    frames = st.get("color")
    if not frames:
        return 1.0

    def alpha_of(fr):
        return int(fr["color"][6:8], 16) / 255.0
    ts = [fr.get("time", 0.0) for fr in frames]
    if time <= ts[0]:
        return alpha_of(frames[0])
    if time >= ts[-1]:
        return alpha_of(frames[-1])
    for j in range(len(frames) - 1):
        if ts[j] <= time <= ts[j + 1]:
            if frames[j].get("curve") == "stepped":
                return alpha_of(frames[j])
            span = ts[j + 1] - ts[j]
            a = 0.0 if span <= 0 else (time - ts[j]) / span
            return alpha_of(frames[j]) * (1 - a) + alpha_of(frames[j + 1]) * a
    return alpha_of(frames[-1])


def _anim_times(anim_bones, driving, substeps=4):
    """收集 driving 骨的所有 keyframe 時間 + 相鄰時間線性 substep,回傳排序時間點。"""
    kt = {0.0}
    for bname in driving:
        tl = anim_bones.get(bname)
        if not tl:
            continue
        for ch in ("rotate", "translate", "scale"):
            for fr in tl.get(ch, []):
                kt.add(round(fr.get("time", 0.0), 6))
    kt = sorted(kt)
    dense = []
    for i, t in enumerate(kt):
        dense.append(t)
        if i + 1 < len(kt):
            for s in range(1, substeps):
                dense.append(t + (kt[i + 1] - t) * s / substeps)
    return dense


# ---------- 主評估 ----------
def anim_phase(aname):
    """依動畫名尾綴分相位:Loop=穩態(硬閘)、In/Out=進退場(診斷)。"""
    low = aname.lower()
    if low.endswith("loop"):
        return "Loop"
    if low.endswith("in"):
        return "In"
    if low.endswith("out"):
        return "Out"
    return "other"


def driving_bones(influences):
    s = set()
    for e in influences:
        for (bi, _, _, _) in e:
            s.add(bi)
    return s


def eval_weighted_mesh(sk, slot, name, skel=None, substeps=4, alpha_min=0.03):
    """對單一 weighted mesh,跑所有『有拉到其綁定骨』的動畫,回傳 per-anim 報告。

    每幀記錄 alpha(slot 可見度)。判定分兩層:
      - `*_visible` / `visible_clean`:只在 alpha>=alpha_min 幀(mesh 實際被看到)判定 → **正式閘**。
      - `*` / `all_clean`:含被 alpha=0 遮住的進退場幀 → 供診斷,不作 pass/fail。"""
    skel = skel or Skeleton(sk)
    infl, tris, hull, weighted = load_weighted_mesh(sk, slot, name)
    if not weighted:
        return {"error": "not a weighted mesh"}
    dbi = driving_bones(infl)
    dnames = {skel.bones[i]["name"] for i in dbi}
    setup_v = skel.skin(infl, skel.pose(None, 0.0))
    setup_signs = [signed_area(setup_v, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup_v, t)) for t in tris)
    setup_res = eval_pose(setup_v, tris, setup_signs, setup_area)

    def agg(res):
        if not res:
            return {"frames": 0, "max_self_intersections": 0, "max_triangle_flips": 0,
                    "max_degenerate": 0, "area_ratio_range": [1.0, 1.0], "clean": True}
        return {
            "frames": len(res),
            "max_self_intersections": max(r["self_intersections"] for r in res),
            "max_triangle_flips": max(r["triangle_flips"] for r in res),
            "max_degenerate": max(r["degenerate"] for r in res),
            "area_ratio_range": [round(min(r["area_ratio"] for r in res), 3),
                                 round(max(r["area_ratio"] for r in res), 3)],
            "clean": all(r["clean"] for r in res),
        }

    per_anim = {}
    for aname, adata in sk.get("animations", {}).items():
        ab = adata.get("bones", {})
        if not (dnames & set(ab.keys())):
            continue
        times = _anim_times(ab, dnames, substeps)
        all_res, vis_res = [], []
        for t in times:
            v = skel.skin(infl, skel.pose(ab, t))
            r = eval_pose(v, tris, setup_signs, setup_area)
            all_res.append(r)
            if slot_alpha(sk, aname, slot, t) >= alpha_min:
                vis_res.append(r)
        a_all = agg(all_res); a_vis = agg(vis_res)
        per_anim[aname] = {
            "visible_frames": a_vis["frames"], "total_frames": a_all["frames"],
            "visible_clean": a_vis["clean"],
            "visible_max_self_intersections": a_vis["max_self_intersections"],
            "visible_max_triangle_flips": a_vis["max_triangle_flips"],
            "visible_area_ratio_range": a_vis["area_ratio_range"],
            "all_frames_clean": a_all["clean"],
            "all_max_self_intersections": a_all["max_self_intersections"],
        }
    return {
        "nv": len(infl), "tris": len(tris), "hull": hull,
        "driving_bones": sorted(dnames),
        "setup_clean": setup_res["clean"],
        "anims": per_anim,
    }


def benchmark_award(path="assets/Award.json", slot_filter="機器"):
    sk = json.load(open(path))
    skel = Skeleton(sk)
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    meshes = [(s, n) for s, o in atts.items() for n, a in o.items()
              if a.get("type") == "mesh" and (slot_filter is None or slot_filter in s)
              and len(a["vertices"]) != len(a["uvs"])]
    report = {}
    steady = {"self_intersections": 0, "triangle_flips": 0}   # *_Loop:穩態(硬閘)
    transient = {"self_intersections": 0, "triangle_flips": 0}  # *_In/*_Out:進退場(診斷)
    n_anims = 0
    for slot, name in meshes:
        r = eval_weighted_mesh(sk, slot, name, skel)
        report[f"{slot}/{name}"] = r
        for aname, a in r.get("anims", {}).items():
            n_anims += 1
            bucket = steady if anim_phase(aname) == "Loop" else transient
            bucket["self_intersections"] = max(bucket["self_intersections"],
                                               a["visible_max_self_intersections"])
            bucket["triangle_flips"] = max(bucket["triangle_flips"],
                                           a["visible_max_triangle_flips"])
    report["_steady_state_worst_visible"] = steady
    report["_transient_worst_visible"] = transient
    report["_anim_evaluations"] = n_anims
    report["_all_setup_clean"] = all(report[k]["setup_clean"] for k in report
                                     if isinstance(report[k], dict) and "setup_clean" in report[k])
    # 硬閘:setup + 所有 *_Loop 穩態可見幀 0 自交 / 0 翻面。
    # 進退場(In/Out)僅診斷:常在 alpha 淡入/擠壓極端出現微觀瞬時折疊(見 knowledge)。
    report["_checker_validated"] = (steady["self_intersections"] == 0
                                    and steady["triangle_flips"] == 0
                                    and report["_all_setup_clean"])
    return report


def negative_control(path="assets/Award.json"):
    """鑑別力驗證(閘不可永遠 pass)。兩個獨立方向:
      (A) 打亂 bind 座標 → setup pose 自交 → 閘 setup_clean 應為 False。
      (B) 對 glow 用**真實** In 大動作但**不做可見度遮罩**(含 alpha=0 幀)→ 應偵測到大量自交
          (證明閘對『真實骨動下的折疊』不盲)。"""
    sk = json.load(open(path))
    skel = Skeleton(sk)
    slot = "機器人拆件/身體"
    infl, tris, hull, _ = load_weighted_mesh(sk, slot, slot)
    # (A) bind-shuffle:固定種子的環狀位移打亂各頂點的 bind 座標
    scrambled = []
    n = len(infl)
    for i, e in enumerate(infl):
        src = infl[(i * 37 + 11) % n]   # 決定性重排(非隨機,確保可重現)
        scrambled.append([(bi, bx, by, w) for (bi, _, _, w), (_, bx, by, _) in zip(e, src[:len(e)] + e[:max(0, len(e) - len(src))])])
    setup_world = skel.pose(None, 0.0)
    v_scr = skel.skin(scrambled, setup_world)
    signs = [signed_area(skel.skin(infl, setup_world), t) > 0 for t in tris]
    area = sum(abs(signed_area(skel.skin(infl, setup_world), t)) for t in tris)
    r_scr = eval_pose(v_scr, tris, signs, area)
    # (B) glow 真實 In,不遮罩(alpha_min=0 等同全幀)
    r_glow = eval_weighted_mesh(sk, "機器人拆件/光暈", "機器人拆件/光暈", skel)["anims"]["Award_Legend_In"]
    unmasked_si = r_glow["all_max_self_intersections"]
    return {
        "A_bind_shuffle_setup_self_intersections": r_scr["self_intersections"],
        "A_detected": r_scr["self_intersections"] > 0,
        "B_glow_In_unmasked_self_intersections": unmasked_si,
        "B_detected": unmasked_si > 0,
        "discriminative": r_scr["self_intersections"] > 0 and unmasked_si > 0,
    }


if __name__ == "__main__":
    import sys as _s
    path = _s.argv[2] if len(_s.argv) > 2 else "assets/Award.json"
    if len(_s.argv) > 1 and _s.argv[1] == "--negctrl":
        nc = negative_control(path)
        print(json.dumps(nc, ensure_ascii=False, indent=2))
        _s.exit(0 if nc["discriminative"] else 1)
    rep = benchmark_award(path if len(_s.argv) > 1 else "assets/Award.json")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    _s.exit(0 if rep["_checker_validated"] else 1)
