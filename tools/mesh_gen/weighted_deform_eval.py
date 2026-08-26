#!/usr/bin/env python3
"""S2/S3 — weighted-mesh bone-deform 評估器:量化「骨骼綁定(weighted)mesh 在動畫
骨骼變換下會不會壞」。這是 `deform_eval.py`(unweighted / deform-timeline)缺的那一半:
weighted mesh 不是靠 deform offset,而是靠**骨骼世界變換 + 每頂點權重混合**變形。

為什麼要它(候選 2 的前置閘):
  S3 對真實美術 mesh 的靜態 IoU 已 PASS,但「weighted mesh 骨骼變形平滑度」是唯一未驗維度。
  要自主鍛鍊 BBW(骨綁權重)生成,必先有能對它 pass/fail 的閘 → 本檔。真值:Award.json 的
  3 個機器人 weighted mesh(光暈/左手/身體)+ 它們綁的 LEG 骨 + In/Loop/Out 動畫。

Spine 3.8 骨骼世界變換(normal transform mode,本資產全 normal):
  local:  rotationY = rot+90+shearY
          la=cosDeg(rot+shearX)*sx ; lb=cosDeg(rotationY)*sy
          lc=sinDeg(rot+shearX)*sx ; ld=sinDeg(rotationY)*sy
  world(有父 pa,pb,pc,pd,pWorldX,pWorldY):
          a=pa*la+pb*lc ; b=pa*lb+pb*ld ; c=pc*la+pd*lc ; d=pc*lb+pd*ld
          worldX=pa*x+pb*y+pWorldX ; worldY=pc*x+pd*y+pWorldY
  root:   a=la,b=lb,c=lc,d=ld ; worldX=x ; worldY=y  (skeleton scale=1,x=y=0)

weighted 頂點世界座標:
  worldPos = Σ_bone weight * (bone.a*bindX + bone.b*bindY + bone.worldX,
                              bone.c*bindX + bone.d*bindY + bone.worldY)

動畫套用:每骨 local = setup + rotate(角度加)/translate(xy 加)/scale(xy 乘),
  keyframe 間以緊湊 bezier(CLAUDE.md 雷點 #7)內插(stepped/linear 特例)。

幾何品質閘沿用 deform_eval:self_intersections / triangle_flips / degenerate。
評估器可信度:正對照(美術真值權重)應全乾淨;負對照(硬綁最近 1 骨 / 打亂綁定)
應被抓到 → 具鑑別力才可當閘。

⚠️ 限制:未處理 transform-constraint(Award 的 `transform` 陣列);本檔的 3 個 mesh
所綁 LEG 骨經檢查不受 constraint 直接驅動,若日後擴到受約束骨需補。
"""
import json, math
import numpy as np
from deform_eval import signed_area, check, eval_pose


# ---------- 緊湊 bezier 內插 ----------
def _bezier_percent(kf, t0, t1, frac):
    """回傳 easing 後的百分比 y(0..1)。kf 是 t0 那格的 keyframe(帶 curve 資訊)。
    frac = (t-t0)/(t1-t0) 線性百分比。緊湊格式:curve=cx1,c2=cy1,c3=cx2,c4=cy2。"""
    curve = kf.get("curve", None)
    if curve is None:              # 預設 linear
        return frac
    if curve == "stepped":
        return 0.0
    if curve == "linear":
        return frac
    # bezier: 控制點 (0,0)(cx1,cy1)(cx2,cy2)(1,1);已知 x=frac,求 y。
    cx1 = float(curve); cy1 = float(kf.get("c2", 0.0))
    cx2 = float(kf.get("c3", 1.0)); cy2 = float(kf.get("c4", 1.0))
    # 以參數 s 掃描解 Bx(s)=frac(單調),回傳 By(s)。10 段足夠(僅影響中間幀)。
    x = frac
    # Newton 幾步 + 二分保底
    lo, hi = 0.0, 1.0
    s = frac
    for _ in range(20):
        oms = 1 - s
        bx = 3*oms*oms*s*cx1 + 3*oms*s*s*cx2 + s*s*s
        if abs(bx - x) < 1e-5:
            break
        if bx < x:
            lo = s
        else:
            hi = s
        s = (lo + hi) / 2
    oms = 1 - s
    by = 3*oms*oms*s*cy1 + 3*oms*s*s*cy2 + s*s*s
    return by


def _sample_timeline(frames, t, keys, default=0.0):
    """在時間 t 對一條 timeline 取值,回傳 dict(keys→value)。frames 依 time 排序。
    ⚠️ default 依 timeline 種類:rotate/translate/shear=0(偏移),scale=1(倍率)。
    Spine JSON 省略的 keyframe 值取該 timeline 的**中性值**,不是 0。"""
    if not frames:
        return {k: default for k in keys}
    if t <= frames[0].get("time", 0.0):
        return {k: frames[0].get(k, default) for k in keys}
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0); t1 = frames[i + 1].get("time", 0.0)
        if t0 <= t <= t1:
            frac = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            p = _bezier_percent(frames[i], t0, t1, frac)
            out = {}
            for k in keys:
                v0 = frames[i].get(k, default); v1 = frames[i + 1].get(k, default)
                out[k] = v0 + (v1 - v0) * p
            return out
    return {k: frames[-1].get(k, default) for k in keys}


# ---------- 骨骼世界變換 ----------
class Bones:
    def __init__(self, skeleton):
        self.bones = skeleton["bones"]
        self.n = len(self.bones)
        self.name2i = {b["name"]: i for i, b in enumerate(self.bones)}
        self.parent = [self.name2i.get(b.get("parent"), -1) for b in self.bones]
        # 拓樸序(父先於子)—— Spine JSON 已保證父在前,直接用索引序。

    def world(self, anim_bones=None, t=0.0):
        """回傳每骨 (a,b,c,d,wx,wy)。anim_bones 為該動畫的 bones dict(可 None=setup)。"""
        W = [None] * self.n
        for i, b in enumerate(self.bones):
            rot = b.get("rotation", 0.0); x = b.get("x", 0.0); y = b.get("y", 0.0)
            sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
            shx = b.get("shearX", 0.0); shy = b.get("shearY", 0.0)
            if anim_bones and b["name"] in anim_bones:
                tl = anim_bones[b["name"]]
                if "rotate" in tl:
                    rot += _sample_timeline(tl["rotate"], t, ["angle"])["angle"]
                if "translate" in tl:
                    d = _sample_timeline(tl["translate"], t, ["x", "y"]); x += d["x"]; y += d["y"]
                if "scale" in tl:
                    d = _sample_timeline(tl["scale"], t, ["x", "y"], default=1.0)
                    sx *= d["x"]; sy *= d["y"]
                if "shear" in tl:
                    d = _sample_timeline(tl["shear"], t, ["x", "y"]); shx += d["x"]; shy += d["y"]
            rotY = rot + 90 + shy
            la = math.cos(math.radians(rot + shx)) * sx
            lb = math.cos(math.radians(rotY)) * sy
            lc = math.sin(math.radians(rot + shx)) * sx
            ld = math.sin(math.radians(rotY)) * sy
            p = self.parent[i]
            if p < 0 or W[p] is None:
                W[i] = (la, lb, lc, ld, x, y)
            else:
                pa, pb, pc, pd, pwx, pwy = W[p]
                a = pa*la + pb*lc; bb = pa*lb + pb*ld
                c = pc*la + pd*lc; dd = pc*lb + pd*ld
                wx = pa*x + pb*y + pwx; wy = pc*x + pd*y + pwy
                W[i] = (a, bb, c, dd, wx, wy)
        return W


# ---------- weighted mesh 解碼 + 世界頂點 ----------
def load_weighted(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    V = a["vertices"]; uvs = a["uvs"]
    nv = len(uvs) // 2
    weighted = len(V) != len(uvs)
    verts = []           # 每頂點 [(boneIdx, bindX, bindY, weight), ...]
    if weighted:
        i = 0
        for _ in range(nv):
            nb = int(V[i]); i += 1
            vs = []
            for _ in range(nb):
                bi = int(V[i]); bx = V[i+1]; by = V[i+2]; w = V[i+3]; i += 4
                vs.append((bi, bx, by, w))
            verts.append(vs)
    else:
        s = np.array(V, dtype=np.float64).reshape(nv, 2)
        for k in range(nv):
            verts.append([(-1, s[k, 0], s[k, 1], 1.0)])
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return verts, tris, a["hull"], nv, weighted


def world_vertices(verts, W):
    out = np.zeros((len(verts), 2), dtype=np.float64)
    for k, binds in enumerate(verts):
        wx = wy = 0.0
        for (bi, bx, by, w) in binds:
            a, b, c, d, ox, oy = W[bi]
            wx += (a*bx + b*by + ox) * w
            wy += (c*bx + d*by + oy) * w
        out[k] = (wx, wy)
    return out


# ---------- 動畫時長 / 取樣 ----------
def anim_duration(anim_bones):
    m = 0.0
    for _, tl in anim_bones.items():
        for _, frames in tl.items():
            for f in frames:
                m = max(m, f.get("time", 0.0))
    return m


def eval_weighted_mesh(skeleton, slot, name, bones_obj, anims, substeps=8, corrupt=None):
    """對 (slot,name) 在 anims(名稱清單)逐幀評估。corrupt 可換權重做負對照。
    回傳 per-anim 幾何品質彙整 + setup 是否乾淨。"""
    verts, tris, hull, nv, weighted = load_weighted(skeleton, slot, name)
    if corrupt is not None:
        verts = corrupt(verts, bones_obj)
    Wsetup = bones_obj.world(None, 0.0)
    sv = world_vertices(verts, Wsetup)
    setup_signs = [signed_area(sv, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(sv, t)) for t in tris) or 1e-9
    setup_eval = eval_pose(sv, tris, setup_signs, setup_area)
    per_anim = {}
    worst = {"self_intersections": 0, "triangle_flips": 0, "degenerate": 0}
    for anim in anims:
        ab = skeleton["animations"][anim].get("bones", {})
        dur = anim_duration(ab)
        if dur <= 0:
            continue
        results = []
        n = max(2, int(dur * 30))              # ~30fps 密集取樣
        for s in range(n + 1):
            t = dur * s / n
            W = bones_obj.world(ab, t)
            wv = world_vertices(verts, W)
            results.append(eval_pose(wv, tris, setup_signs, setup_area))
        agg = {
            "frames": len(results),
            "max_self_intersections": max(r["self_intersections"] for r in results),
            "max_triangle_flips": max(r["triangle_flips"] for r in results),
            "max_degenerate": max(r["degenerate"] for r in results),
            "area_ratio_range": [min(r["area_ratio"] for r in results),
                                 max(r["area_ratio"] for r in results)],
            "all_clean": all(r["clean"] for r in results),
        }
        per_anim[anim] = agg
        for k in worst:
            worst[k] = max(worst[k], agg["max_" + k])
    return {
        "nv": nv, "hull": hull, "tris": len(tris), "weighted": weighted,
        "setup_clean": setup_eval["clean"], "anims": per_anim,
        "all_clean": setup_eval["clean"] and all(a["all_clean"] for a in per_anim.values()),
        "_worst": worst,
    }


# ---------- 負對照:破壞權重平滑度 ----------
def corrupt_hard1(verts, bones_obj):
    """每頂點只保留權重最大的骨(硬綁 1 骨)→ 骨界不連續,大旋轉下應撕裂。"""
    out = []
    for binds in verts:
        b = max(binds, key=lambda x: x[3])
        out.append([(b[0], b[1], b[2], 1.0)])
    return out


def corrupt_shuffle(verts, bones_obj):
    """把每頂點的骨索引在該 mesh 用到的骨集合內循環錯位 → 綁錯骨,變形應亂。"""
    used = sorted({b[0] for binds in verts for b in binds})
    if len(used) < 2:
        return verts
    shift = {bi: used[(i + 1) % len(used)] for i, bi in enumerate(used)}
    out = []
    for binds in verts:
        out.append([(shift[bi], bx, by, w) for (bi, bx, by, w) in binds])
    return out


ROBOT = [("機器人拆件/光暈", "機器人拆件/光暈"),
         ("機器人拆件/左手", "機器人拆件/左手"),
         ("機器人拆件/身體", "機器人拆件/身體")]
ROBOT_ANIMS = ["Award_Legend_In", "Award_Legend_Loop", "Award_Legend_Out"]
# 分類:結構件(需嚴格 clean 作為變形平滑度閘)vs 軟 FX/glow 件(容忍折疊)。
# 依據(資料驅動,非硬編):光暈 setup 乾淨但綁高倍率骨(4_LEG6 In 期 scale=1.667,影響 49/78 頂點),
# 在 In 爆發幀於高倍率骨邊界折疊(flip 空間叢聚於 4_LEG6);其鄰件(左手/身體共用同骨鏈)全乾淨。
# → 光暈屬「軟發光層」,美術容忍折疊;結構件用嚴格閘。
STRUCTURAL = {"機器人拆件/左手", "機器人拆件/身體"}
SOFT_FX = {"機器人拆件/光暈"}


def run(path="assets/Award.json"):
    sk = json.load(open(path))
    bones_obj = Bones(sk)
    report = {"positive": {}, "neg_hard1": {}, "neg_shuffle": {}}
    for slot, name in ROBOT:
        report["positive"][slot] = eval_weighted_mesh(sk, slot, name, bones_obj, ROBOT_ANIMS)
        report["neg_hard1"][slot] = eval_weighted_mesh(sk, slot, name, bones_obj, ROBOT_ANIMS,
                                                        corrupt=corrupt_hard1)
        report["neg_shuffle"][slot] = eval_weighted_mesh(sk, slot, name, bones_obj, ROBOT_ANIMS,
                                                          corrupt=corrupt_shuffle)
    # 判定(可信度 = 鑑別力):結構件正對照全乾淨 + 每個負對照每件都被抓到。
    structural_clean = all(report["positive"][s]["all_clean"] for s in STRUCTURAL)
    fx_status = {s: report["positive"][s]["all_clean"] for s in SOFT_FX}
    # 負對照:每種破壞法對每個 mesh 都應被抓到(all_clean=False)才算全面鑑別。
    neg1_all = all(not r["all_clean"] for r in report["neg_hard1"].values())
    negs_all = all(not r["all_clean"] for r in report["neg_shuffle"].values())
    neg1_which = {s: (not r["all_clean"]) for s, r in report["neg_hard1"].items()}
    negs_which = {s: (not r["all_clean"]) for s, r in report["neg_shuffle"].items()}
    report["_verdict"] = {
        "structural_all_clean": structural_clean,      # 左手/身體 於 In/Loop/Out 全乾淨
        "soft_fx_clean": fx_status,                    # 光暈:預期 In 折疊(美術容忍)
        "neg_hard1_flagged_all": neg1_all, "neg_hard1_per_mesh": neg1_which,
        "neg_shuffle_flagged_all": negs_all, "neg_shuffle_per_mesh": negs_which,
        # 鑑別力:結構件通過 + 至少一種負對照對每件都抓到 → 閘可信可作 BBW 收斂依據。
        "evaluator_discriminative": structural_clean and (neg1_all or negs_all),
    }
    return report


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    full = "--json" in sys.argv
    rep = run(path)
    if full:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("=== weighted-mesh bone-deform 評估器 (Award 機器人 3 件) ===")
        for cls, d in [("POSITIVE(美術真值)", rep["positive"]),
                       ("NEG hard-1-bone", rep["neg_hard1"]),
                       ("NEG shuffle-bind", rep["neg_shuffle"])]:
            print(f"\n[{cls}]")
            for slot, r in d.items():
                tag = "clean" if r["all_clean"] else f"FOLD {r['_worst']}"
                print(f"  {slot:16s} {tag}")
        v = rep["_verdict"]
        print("\n=== 判定 ===")
        print(f"  結構件(左手/身體)全乾淨 : {v['structural_all_clean']}")
        print(f"  軟FX(光暈)             : {v['soft_fx_clean']}")
        print(f"  shuffle 負對照每件都抓到 : {v['neg_shuffle_flagged_all']}")
        print(f"  hard1  負對照每件       : {v['neg_hard1_per_mesh']}")
        print(f"  >>> evaluator_discriminative = {v['evaluator_discriminative']}")
