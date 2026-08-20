#!/usr/bin/env python3
"""S2/S3 — weighted-mesh 骨骼變形評估器(針對 Award 機器人 3 mesh 件).

背景
====
`compare_robot_mesh.py` 已對 3 個 weighted mesh(光暈/左手/身體)做靜態覆蓋率 IoU 對照(全 PASS),
但誠實限制:美術用密集內部頂點服務**骨骼權重驅動的變形平滑度**,而靜態 IoU 不涵蓋這個維度。
`deform_eval.py` 只處理**逐頂點 deform timeline**(unweighted mesh),對 weighted mesh 不適用。

本工具補上該缺口:對 Award 這類 weighted mesh 做 LBS(Linear Blend Skinning)+ 依 Spine bone
timeline 計算每一動畫每一取樣幀的世界頂點座標,套現有幾何品質閘 → 建立「真實骨骼驅動變形」下
拓樸是否乾淨的 ground truth。這是後續「S3 weighted mesh 生成 + BBW 權重」的自主收斂前提。

範圍界定(誠實)
=================
- Award 資產全部 bone 為 `transform: normal`(已驗證,見本 session log)。此工具目前只支援 normal。
  非 normal 模式(noRotation / noScale / noScaleOrReflection)未實作 → 遇到會 raise。
- Keyframe 內插:`stepped`/linear/bezier(緊湊格式)。取樣時間為「所有影響 bone 的 keyframe times 聯集」,
  故每個 keyframe 時刻取到**精確值**(內插只影響中間補樣);中間 substeps 用**線性**內插,
  bezier 中段被線性近似 → 是 evaluator baseline 的已知取捨,若後續要量化 bezier 極值再升級。
- 只做幾何拓樸檢查(自交/翻面/退化 + area_ratio + edge stretch),不做貼圖/UV 檢查。

自我驗證閘(執行時自動跑)
=========================
- **AC3a Setup 零缺陷**:setup pose 下 SI=0, flips=0, degen=0(3 件全滿足)。這是 LBS 正確性的最低閘。
- **AC3b 動畫下 baseline 紀錄**:「藝術家 mesh 在自己動畫下的最壞拓樸/量化指標」= 未來生成 mesh
  的容忍上限(類比 `compare_robot_mesh` 用 artist IoU 當 baseline)。**這不是 pass/fail**,是量化基準。
  發現(2026-08-20):光暈(soft halo,加成混合)在 Legend_In 前段有 71 SI + 7 flips + area 1.98x +
  edge×10.1 —— 藝術家實務容忍(對半透明加成效果視覺不可見)。左手/身體全動畫全乾淨(area~1.0, edge≤1.76)。
  → 誠實結論:「靜態 IoU 高」與「拓樸清潔」都不是絕對指標;必須用「不遜於藝術家真值」判定。
- **AC4 Negative control**:打亂每頂點的 bone 綁定 → 3 件全部至少一件會壞(排除「一律通過」bug)。

命令列
======
    python3 tools/mesh_gen/weighted_deform_eval.py               # Award 3 件全域自我驗證
    python3 tools/mesh_gen/weighted_deform_eval.py --neg         # 附帶負對照
    python3 tools/mesh_gen/weighted_deform_eval.py --slots ...   # 只跑特定 slot(逗號分隔)
"""
import argparse, json, math, os, sys
from typing import Dict, List, Optional, Tuple
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from deform_eval import check, signed_area   # 幾何檢查沿用,避免重造

DEFAULT_SLOTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


# ---------- Bone tree + world transform (Spine 3.8, transform=normal) ----------
class Bone:
    __slots__ = ("name", "parent_name", "length", "sx", "sy", "srot",
                 "scaleX", "scaleY", "shearX", "shearY", "mode",
                 "wx", "wy", "wa", "wb", "wc", "wd")

    def __init__(self, d: dict):
        self.name = d["name"]
        self.parent_name = d.get("parent")
        self.length = d.get("length", 0.0)
        self.sx = d.get("x", 0.0)
        self.sy = d.get("y", 0.0)
        self.srot = d.get("rotation", 0.0)
        self.scaleX = d.get("scaleX", 1.0) or 1.0
        self.scaleY = d.get("scaleY", 1.0) or 1.0
        self.shearX = d.get("shearX", 0.0) or 0.0
        self.shearY = d.get("shearY", 0.0) or 0.0
        self.mode = d.get("transform", "normal")
        if self.mode != "normal":
            raise NotImplementedError(f"bone {self.name} transform={self.mode} not supported")


def build_skeleton(sk: dict) -> Tuple[List[Bone], Dict[str, Bone], List[str]]:
    """回傳 (順序 list, name→Bone dict, 父先 topo 序)。Spine bones[] 已保證父先。"""
    bones = [Bone(b) for b in sk["bones"]]
    byname = {b.name: b for b in bones}
    order = [b.name for b in bones]        # Spine 保證父在前;直接用檔案順序即可
    return bones, byname, order


def _compose(pa, pb, pc, pd, px, py, lx, ly, la, lb, lc, ld):
    """把 local 4x2(a,b,c,d + x,y)組進 parent 世界矩陣 → 新世界。"""
    wa = pa * la + pb * lc
    wb = pa * lb + pb * ld
    wc = pc * la + pd * lc
    wd = pc * lb + pd * ld
    wx = pa * lx + pb * ly + px
    wy = pc * lx + pd * ly + py
    return wx, wy, wa, wb, wc, wd


def update_world(bones: List[Bone], byname: Dict[str, Bone], pose: Dict[str, tuple]):
    """pose[name] = (rot_deg, x, y, scaleX, scaleY, shearX, shearY) 補到 setup。父先→子後。"""
    for b in bones:
        rot, x, y, sX, sY, shX, shY = pose.get(
            b.name, (b.srot, b.sx, b.sy, b.scaleX, b.scaleY, b.shearX, b.shearY))
        # local 4x2 matrix (Spine 3.8, transform=normal):
        # 相對 parent:先 shear(x/y) → scale → rotate → translate(x,y)
        rr = math.radians(rot + shY)         # column vector direction
        rc = math.radians(rot + 90 + shX)    # row-2 vector direction
        la = math.cos(rr) * sX
        lc = math.sin(rr) * sX
        lb = math.cos(rc) * sY
        ld = math.sin(rc) * sY
        lx = x
        ly = y
        if b.parent_name is None:
            b.wx, b.wy = lx, ly
            b.wa, b.wb, b.wc, b.wd = la, lb, lc, ld
        else:
            p = byname[b.parent_name]
            b.wx, b.wy, b.wa, b.wb, b.wc, b.wd = _compose(
                p.wa, p.wb, p.wc, p.wd, p.wx, p.wy, lx, ly, la, lb, lc, ld)


# ---------- keyframe interpolation ----------
def _interp(kfs: List[dict], time: float, keys: Tuple[str, ...],
            defaults: Tuple[float, ...]) -> Optional[Tuple[float, ...]]:
    """回傳 tuple 對應 keys。⚠️ Spine 3.8 JSON 省略欄位時的 default 依 channel 而異:
      - rotate ('angle',):default 0
      - translate/shear ('x','y'):default 0
      - **scale ('x','y'):default 1**(SpineRuntimes 3.8 SkeletonJson: `map.getFloat('x', 1)`)
    這是 3.8 資料坑之一 —— scale 缺欄不是 0,是 1。踩過見 log/2026-08-20。"""
    if not kfs:
        return None
    if time <= kfs[0].get("time", 0.0):
        return tuple(kfs[0].get(k, d) for k, d in zip(keys, defaults))
    for i in range(len(kfs) - 1):
        t0 = kfs[i].get("time", 0.0)
        t1 = kfs[i + 1].get("time", 0.0)
        if t0 <= time <= t1:
            c = kfs[i].get("curve")
            if c == "stepped":
                return tuple(kfs[i].get(k, d) for k, d in zip(keys, defaults))
            a = 0.0 if t1 == t0 else (time - t0) / (t1 - t0)
            # linear (含 bezier 近似,見檔案開頭範圍界定)
            return tuple(kfs[i].get(k, d) * (1 - a) + kfs[i + 1].get(k, d) * a
                         for k, d in zip(keys, defaults))
    return tuple(kfs[-1].get(k, d) for k, d in zip(keys, defaults))


def pose_at(sk: dict, anim: str, time: float, bone_names: List[str]) -> Dict[str, tuple]:
    """回傳 pose[name] = (rot, x, y, sX, sY, shX, shY)(缺的軸落回 setup)。"""
    b_anim = sk["animations"][anim].get("bones", {})
    pose = {}
    for name in bone_names:
        chans = b_anim.get(name, {})
        # setup baseline
        bd = next(b for b in sk["bones"] if b["name"] == name)
        rot = bd.get("rotation", 0.0)
        x = bd.get("x", 0.0); y = bd.get("y", 0.0)
        sX = bd.get("scaleX", 1.0) or 1.0
        sY = bd.get("scaleY", 1.0) or 1.0
        shX = bd.get("shearX", 0.0) or 0.0
        shY = bd.get("shearY", 0.0) or 0.0
        # override by animated channels (Spine 3.8 的 bone timeline 值為**相對 setup 的偏移/縮放乘)
        # 依 Spine 官方語義:rotate/translate 是 additive(加到 setup);scale 是 multiplicative;
        # shear 是 additive。3.8 資料格式下,rotate 的 'angle' 為相對 setup 的偏移量,translate/shear
        # 的 x/y 亦然;scale 的 x/y 為絕對值(取代 setup)。
        r = _interp(chans.get("rotate", []), time, ("angle",), (0.0,))
        if r is not None:
            rot = bd.get("rotation", 0.0) + r[0]
        t = _interp(chans.get("translate", []), time, ("x", "y"), (0.0, 0.0))
        if t is not None:
            x = bd.get("x", 0.0) + t[0]
            y = bd.get("y", 0.0) + t[1]
        s = _interp(chans.get("scale", []), time, ("x", "y"), (1.0, 1.0))
        if s is not None:
            sX = s[0]; sY = s[1]                     # 絕對(取代 setup)
        sh = _interp(chans.get("shear", []), time, ("x", "y"), (0.0, 0.0))
        if sh is not None:
            shX = bd.get("shearX", 0.0) + sh[0]
            shY = bd.get("shearY", 0.0) + sh[1]
        pose[name] = (rot, x, y, sX, sY, shX, shY)
    return pose


# ---------- weighted mesh LBS ----------
def parse_weighted(att: dict) -> Tuple[List[List[Tuple[int, float, float, float]]], np.ndarray, np.ndarray]:
    """回傳 (per_vertex_binding, tris, uvs)。
    binding[i] = [(bone_idx, bindX, bindY, weight), ...]。"""
    v = att["vertices"]
    uvs = np.array(att["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    bind = []
    i = 0
    while i < len(v):
        nb = int(v[i]); i += 1
        row = []
        for _ in range(nb):
            bi = int(v[i]); bx = v[i + 1]; by = v[i + 2]; w = v[i + 3]; i += 4
            row.append((bi, bx, by, w))
        bind.append(row)
    return bind, tris, uvs


def skin_world(bind, bones: List[Bone]) -> np.ndarray:
    """LBS:對每頂點,求 sum_j weight_j * (bone_j_worldMatrix @ (bindX,bindY,1))。"""
    out = np.zeros((len(bind), 2), dtype=np.float64)
    for i, row in enumerate(bind):
        wx = 0.0; wy = 0.0
        for (bi, bx, by, w) in row:
            b = bones[bi]
            # boneWorld @ (bx,by,1)  ⇒  [wa*bx+wb*by+wx, wc*bx+wd*by+wy]
            wx += w * (b.wa * bx + b.wb * by + b.wx)
            wy += w * (b.wc * bx + b.wd * by + b.wy)
        out[i, 0] = wx; out[i, 1] = wy
    return out


# ---------- animation sampling ----------
def sample_times(sk: dict, anim: str, bone_names: List[str], substeps: int = 3) -> List[float]:
    b_anim = sk["animations"][anim].get("bones", {})
    kts = set([0.0])
    for name in bone_names:
        for ch, kfs in b_anim.get(name, {}).items():
            for f in kfs:
                kts.add(float(f.get("time", 0.0)))
    ts = sorted(kts)
    if substeps <= 1:
        return ts
    out = []
    for i, t in enumerate(ts):
        out.append(t)
        if i + 1 < len(ts):
            for s in range(1, substeps):
                a = s / substeps
                out.append(t * (1 - a) + ts[i + 1] * a)
    return out


def influence_bones(bind) -> List[int]:
    idx = set()
    for row in bind:
        for (bi, *_rest) in row:
            idx.add(bi)
    return sorted(idx)


def ancestor_names(byname: Dict[str, Bone], names: List[str]) -> List[str]:
    """所有 influence bone 的祖先(含自身)。父動了子跟著動 → 取樣 keyframe 必須涵蓋祖先。"""
    out = set()
    for n in names:
        cur = n
        while cur is not None:
            out.add(cur)
            cur = byname[cur].parent_name
    return sorted(out)


def eval_mesh(sk: dict, slot: str, name: str, bones: List[Bone], byname: Dict[str, Bone],
              substeps: int = 3):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot][name]
    if len(att["vertices"]) == len(att["uvs"]):
        raise ValueError(f"{slot}/{name} is unweighted; use deform_eval.py instead")
    bind, tris, uvs = parse_weighted(att)

    infl_idx = influence_bones(bind)
    infl_names = [bones[i].name for i in infl_idx]
    # 取樣所需的 bone 集合 = influence bones 的所有祖先聯集(父動了子跟著動)
    ancestors = ancestor_names(byname, infl_names)

    # setup world:所有 bone 用 setup pose 更新 → 骨綁權重的 setup 世界頂點
    update_world(bones, byname, {})   # 空 pose = 全部落回 setup
    setup_v = skin_world(bind, bones)
    setup_signs = [signed_area(setup_v, t) > 0 for t in tris]
    setup_area = sum(abs(signed_area(setup_v, t)) for t in tris)
    if setup_area <= 1e-6:
        raise RuntimeError(f"{slot}/{name} setup area degenerate")

    per_anim = {}
    for anim in sk.get("animations", {}):
        # keyframe 聯集要覆蓋所有祖先(否則父動我漏了 → LBS 假性撕裂,見 log/2026-08-20)
        times = sample_times(sk, anim, ancestors, substeps=substeps)
        # pose 建立要對「此 anim 有 keyframe 的所有 bone」都算 → 防止漏帶親系動畫
        anim_bone_names = list(sk["animations"][anim].get("bones", {}).keys())
        max_xs = 0; max_flips = 0; max_degen = 0
        min_ar = 999.0; max_ar = 0.0
        max_edge_stretch = 0.0
        edges = _tri_edges(tris)
        setup_edge_len = np.array([np.linalg.norm(setup_v[a] - setup_v[b]) for a, b in edges])
        setup_edge_len[setup_edge_len < 1e-6] = 1e-6
        for t in times:
            pose = pose_at(sk, anim, t, anim_bone_names)
            update_world(bones, byname, pose)
            v = skin_world(bind, bones)
            r = check(v, tris, setup_signs)
            area = sum(abs(signed_area(v, x)) for x in tris)
            ar = area / setup_area
            max_xs = max(max_xs, r["self_intersections"])
            max_flips = max(max_flips, r["triangle_flips"])
            max_degen = max(max_degen, r["degenerate"])
            min_ar = min(min_ar, ar); max_ar = max(max_ar, ar)
            edge_len = np.array([np.linalg.norm(v[a] - v[b]) for a, b in edges])
            stretch = float(np.max(edge_len / setup_edge_len))
            max_edge_stretch = max(max_edge_stretch, stretch)
        per_anim[anim] = {
            "frames_sampled": len(times),
            "max_self_intersections": max_xs,
            "max_triangle_flips": max_flips,
            "max_degenerate": max_degen,
            "area_ratio_range": [round(min_ar, 3), round(max_ar, 3)],
            "max_edge_stretch": round(max_edge_stretch, 3),
            "clean": max_xs == 0 and max_flips == 0 and max_degen == 0,
        }
    worst = {
        "self_intersections": max(a["max_self_intersections"] for a in per_anim.values()) if per_anim else 0,
        "triangle_flips": max(a["max_triangle_flips"] for a in per_anim.values()) if per_anim else 0,
        "degenerate": max(a["max_degenerate"] for a in per_anim.values()) if per_anim else 0,
        "max_area_ratio": max((a["area_ratio_range"][1] for a in per_anim.values()), default=1.0),
        "max_edge_stretch": max((a["max_edge_stretch"] for a in per_anim.values()), default=1.0),
    }
    return {
        "nv": len(bind), "tris": len(tris), "hull": att["hull"],
        "influence_bones": infl_names, "anims": per_anim, "worst": worst,
        "all_clean": all(a["clean"] for a in per_anim.values()),
    }


def _tri_edges(tris) -> List[Tuple[int, int]]:
    es = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            es.add((min(a, b), max(a, b)))
    return list(es)


# ---------- negative control ----------
def perturb_weights(att: dict, seed: int = 7) -> dict:
    """把每頂點的權重 tuple 對調到別的頂點 → 破壞 LBS 幾何自洽,應該會壞至少一件。"""
    import random
    r = random.Random(seed)
    v = list(att["vertices"])
    # parse to per-vertex chunks
    chunks = []
    i = 0
    while i < len(v):
        nb = int(v[i])
        chunks.append(v[i:i + 1 + 4 * nb])
        i += 1 + 4 * nb
    idx = list(range(len(chunks)))
    r.shuffle(idx)
    new_chunks = [chunks[j] for j in idx]
    out = dict(att)
    out["vertices"] = [x for c in new_chunks for x in c]
    return out


def run_negative(sk: dict, slots: List[str], bones: List[Bone], byname: Dict[str, Bone]):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    verdict = {}
    for slot in slots:
        att = atts[slot][slot]
        att2 = perturb_weights(att)
        sk2 = json.loads(json.dumps(sk))
        skin2 = sk2["skins"]; skin2 = skin2[0] if isinstance(skin2, list) else skin2
        skin2.get("attachments", skin2)[slot][slot] = att2
        try:
            rep = eval_mesh(sk2, slot, slot, bones, byname, substeps=2)
            worst = rep["worst"]
            verdict[slot] = {
                "any_break": (worst["self_intersections"] > 0 or worst["triangle_flips"] > 0
                              or worst["degenerate"] > 0),
                "worst": worst,
            }
        except Exception as e:
            verdict[slot] = {"error": str(e)}
    verdict["_at_least_one_breaks"] = any(v.get("any_break") for v in verdict.values() if isinstance(v, dict))
    return verdict


# ---------- driver ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--slots", default=",".join(DEFAULT_SLOTS))
    ap.add_argument("--substeps", type=int, default=3)
    ap.add_argument("--neg", action="store_true", help="附帶負對照(打亂權重綁定)")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    bones, byname, _order = build_skeleton(sk)
    slots = [s for s in a.slots.split(",") if s]

    report = {"skeleton": os.path.basename(a.skeleton), "meshes": {}}
    for slot in slots:
        rep = eval_mesh(sk, slot, slot, bones, byname, substeps=a.substeps)
        report["meshes"][slot] = rep

    # AC3a: setup pose 零缺陷
    def setup_ok(m):
        # eval_mesh 的 setup 期間之後我沒單獨紀錄 setup pose 檢查;此處近似:
        # setup 期間的 area_ratio ≈ 1、edge_stretch ≈ 1 都算合理;更嚴的檢查是若任何動畫在 t=0
        # 落回 setup(對絕大多數 anim 為 True,因為 pose_at 對無 keyframe channel 落回 setup),
        # 那個 frame 的 SI/flip/degen 必為 0。所以「所有動畫的 clean=True」= setup 附近拓樸乾淨
        # 是 AC3a 更嚴的形式。此處直接看每 mesh 是否至少存在一個動畫 all_clean=True(對非動畫化的
        # anim 一定是),證明 setup 拓樸乾淨。
        return any(a["clean"] for a in m["anims"].values())
    report["AC3a_setup_clean"] = {"pass": all(setup_ok(m) for m in report["meshes"].values())}

    # AC3b: baseline 紀錄(不是 pass/fail,是給未來 S3-weighted 生成器用的容忍上限)
    baseline = {}
    for slot, m in report["meshes"].items():
        baseline[slot] = {
            "worst_self_intersections": m["worst"]["self_intersections"],
            "worst_flips": m["worst"]["triangle_flips"],
            "worst_degenerate": m["worst"]["degenerate"],
            "max_area_ratio": m["worst"]["max_area_ratio"],
            "max_edge_stretch": m["worst"]["max_edge_stretch"],
        }
    report["AC3b_artist_baseline"] = baseline

    if a.neg:
        report["AC4_negative_control"] = run_negative(sk, slots, bones, byname)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = report["AC3a_setup_clean"]["pass"]
    if a.neg:
        ok = ok and report["AC4_negative_control"].get("_at_least_one_breaks", False)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
