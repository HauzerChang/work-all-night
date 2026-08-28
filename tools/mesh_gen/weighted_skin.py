#!/usr/bin/env python3
"""Spine 3.8 bone forward-kinematics + weighted-mesh linear-blend skinning (純 CPU)。

補上「S3 靜態 IoU PASS ≠ weighted mesh 骨骼變形品質對等」的缺口(見
knowledge/s3-robot-mesh-vs-award.md 誠實限制)。這 3 個 Award 機器人 mesh 件是
**weighted mesh**:沒有 deform timeline,而是被綁到 leg 骨鏈,靠骨骼的 rotate/scale/
translate 動畫變形。要量化其變形平滑度,必須先能在 Python 重現 Spine 的骨骼蒙皮。

實作範圍(對 Award 已足夠,見資產實測):
  - transform mode 只有 'normal'(Award 77 骨全 normal);無 shear。
  - 逐骨 world 矩陣沿階層 root→leaf 組合(標準 Spine Bone.updateWorldTransform)。
  - 動畫 timeline:rotate(角度 delta)/ translate(x,y offset)/ scale(乘數)。
    緊湊 bezier `{curve,c2,c3,c4}` / "stepped" / linear 三種內插都支援。
  - weighted skin:worldV = Σ_bone weight*(a*bindX + b*bindY + worldX, c*bindX + d*bindY + worldY)。

座標系:Spine y-up,直接沿用 JSON 數值(幾何檢查只需系統自洽)。

正確性錨點(見 weighted_deform_eval.py AC1):把 root 骨施加剛體 T(旋轉+平移),
則所有蒙皮頂點必**恰好**被 T 映射(∵ 權重和=1 的仿射再現性)。此測同時驗
FK 組合與權重正規化,非循環。
"""
import json
import math
import numpy as np

COS = lambda deg: math.cos(math.radians(deg))
SIN = lambda deg: math.sin(math.radians(deg))


# ---------- skeleton / bones ----------
def load_skeleton(path):
    return json.load(open(path))


def _skin_atts(sk):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)


def load_weighted_mesh(sk, slot, name=None):
    """回傳 dict:{n, bones:[[(boneIdx,bindX,bindY,weight),...] per vertex],
    uvs Nx2, triangles Mx3, hull, weighted:bool}。unweighted 也可載(bones=None)。"""
    name = name or slot
    a = _skin_atts(sk)[slot][name]
    V = a["vertices"]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    weighted = len(V) != len(uvs)
    if not weighted:
        setup = np.array(V, dtype=np.float64).reshape(-1, 2)
        return {"n": len(uvs), "bones": None, "setup_local": setup, "uvs": uvs,
                "triangles": tris, "hull": a["hull"], "weighted": False}
    verts = []
    i = 0
    while i < len(V):
        nb = int(V[i]); i += 1
        entry = []
        for _ in range(nb):
            bidx = int(V[i]); bx = V[i + 1]; by = V[i + 2]; w = V[i + 3]; i += 4
            entry.append((bidx, bx, by, w))
        verts.append(entry)
    return {"n": len(uvs), "bones": verts, "uvs": uvs, "triangles": tris,
            "hull": a["hull"], "weighted": True}


class Skeleton:
    """可套動畫、算 world transform、蒙皮的最小骨架。"""

    def __init__(self, sk):
        self.data = sk
        self.bones = sk["bones"]
        self.n = len(self.bones)
        self.name2idx = {b["name"]: i for i, b in enumerate(self.bones)}
        self.parent = [self.name2idx.get(b.get("parent")) if b.get("parent") else None
                       for b in self.bones]
        # 拓樸排序(parent 在前),Award 已是此序但不硬賴
        self.order = self._topo()
        self._reset_local()
        # world 矩陣 (a,b,c,d,wx,wy) per bone
        self.wa = np.zeros(self.n); self.wb = np.zeros(self.n)
        self.wc = np.zeros(self.n); self.wd = np.zeros(self.n)
        self.wx = np.zeros(self.n); self.wy = np.zeros(self.n)

    def _topo(self):
        order = []
        seen = [False] * self.n
        def visit(i):
            if seen[i]:
                return
            p = self.parent[i]
            if p is not None:
                visit(p)
            seen[i] = True
            order.append(i)
        for i in range(self.n):
            visit(i)
        return order

    def _reset_local(self):
        b = self.bones
        self.lx = np.array([bb.get("x", 0.0) for bb in b], dtype=np.float64)
        self.ly = np.array([bb.get("y", 0.0) for bb in b], dtype=np.float64)
        self.lrot = np.array([bb.get("rotation", 0.0) for bb in b], dtype=np.float64)
        self.lsx = np.array([bb.get("scaleX", 1.0) for bb in b], dtype=np.float64)
        self.lsy = np.array([bb.get("scaleY", 1.0) for bb in b], dtype=np.float64)

    def set_to_setup(self):
        self._reset_local()

    def update_world(self):
        for i in self.order:
            rot = self.lrot[i]
            la = COS(rot) * self.lsx[i]
            lb = COS(rot + 90.0) * self.lsy[i]
            lc = SIN(rot) * self.lsx[i]
            ld = SIN(rot + 90.0) * self.lsy[i]
            p = self.parent[i]
            if p is None:
                self.wa[i] = la; self.wb[i] = lb
                self.wc[i] = lc; self.wd[i] = ld
                self.wx[i] = self.lx[i]; self.wy[i] = self.ly[i]
            else:
                pa, pb, pc, pd = self.wa[p], self.wb[p], self.wc[p], self.wd[p]
                self.wx[i] = pa * self.lx[i] + pb * self.ly[i] + self.wx[p]
                self.wy[i] = pc * self.lx[i] + pd * self.ly[i] + self.wy[p]
                self.wa[i] = pa * la + pb * lc
                self.wb[i] = pa * lb + pb * ld
                self.wc[i] = pc * la + pd * lc
                self.wd[i] = pc * lb + pd * ld

    # ---------- world vertices ----------
    def skin(self, mesh):
        """回傳 mesh 逐頂點世界座標 Nx2(需先 update_world)。"""
        out = np.zeros((mesh["n"], 2))
        if not mesh["weighted"]:
            # unweighted:vertices 已是綁到單一 slot bone 的 local;此工具聚焦 weighted。
            raise ValueError("unweighted mesh: use deform_eval path")
        for vi, entry in enumerate(mesh["bones"]):
            x = y = 0.0
            for (bidx, bx, by, w) in entry:
                x += (self.wa[bidx] * bx + self.wb[bidx] * by + self.wx[bidx]) * w
                y += (self.wc[bidx] * bx + self.wd[bidx] * by + self.wy[bidx]) * w
            out[vi] = (x, y)
        return out


# ---------- animation ----------
def _bezier(cx1, cy1, cx2, cy2, t):
    """緊湊 bezier:給定線性 t∈[0,1](時間分數),解出對應曲線 value 分數。
    控制點在 [0,1]×[0,1](time,value)。以參數掃描近似解 x(s)=t。"""
    # Newton on cubic bezier x(s)=3(1-s)^2 s cx1 + 3(1-s)s^2 cx2 + s^3
    s = t
    for _ in range(8):
        u = 1 - s
        x = 3 * u * u * s * cx1 + 3 * u * s * s * cx2 + s * s * s
        dx = 3 * u * u * cx1 + 6 * u * s * (cx2 - cx1) + 3 * s * s * (1 - cx2)
        if dx < 1e-9:
            break
        s -= (x - t) / dx
        s = min(1.0, max(0.0, s))
    u = 1 - s
    return 3 * u * u * s * cy1 + 3 * u * s * s * cy2 + s * s * s


def _interp(frames, time, keys, defaults):
    """通用 timeline 取值。frames:排序 keyframe list;keys:欲取欄位;
    defaults:各欄位缺省。回傳 tuple(len(keys))。"""
    if not frames:
        return defaults
    if time <= frames[0].get("time", 0.0):
        f = frames[0]
        return tuple(f.get(k, d) for k, d in zip(keys, defaults))
    if time >= frames[-1].get("time", 0.0):
        f = frames[-1]
        return tuple(f.get(k, d) for k, d in zip(keys, defaults))
    # 找區間
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0)
        t1 = frames[i + 1].get("time", 0.0)
        if t0 <= time < t1:
            f0, f1 = frames[i], frames[i + 1]
            curve = f0.get("curve", None)
            span = t1 - t0
            lin = (time - t0) / span if span > 1e-12 else 0.0
            if curve == "stepped":
                frac = 0.0
            elif curve is None:
                frac = lin
            else:  # 緊湊 bezier(curve=cx1,c2=cy1,c3=cx2,c4=cy2)
                frac = _bezier(curve, f0.get("c2", 0.0), f0.get("c3", 1.0),
                               f0.get("c4", 1.0), lin)
            out = []
            for k, d in zip(keys, defaults):
                v0 = f0.get(k, d); v1 = f1.get(k, d)
                out.append(v0 + (v1 - v0) * frac)
            return tuple(out)
    f = frames[-1]
    return tuple(f.get(k, d) for k, d in zip(keys, defaults))


def apply_animation(skel: Skeleton, anim_name, time):
    """把某動畫在 time 的 bone timeline 套到 skel(setup + delta),再 update_world。"""
    skel.set_to_setup()
    anim = skel.data["animations"][anim_name]
    for bname, tl in anim.get("bones", {}).items():
        bi = skel.name2idx.get(bname)
        if bi is None:
            continue
        if "rotate" in tl:
            (ang,) = _interp(tl["rotate"], time, ["angle"], [0.0])
            skel.lrot[bi] += ang
        if "translate" in tl:
            dx, dy = _interp(tl["translate"], time, ["x", "y"], [0.0, 0.0])
            skel.lx[bi] += dx; skel.ly[bi] += dy
        if "scale" in tl:
            sx, sy = _interp(tl["scale"], time, ["x", "y"], [1.0, 1.0])
            skel.lsx[bi] *= sx; skel.lsy[bi] *= sy
    skel.update_world()


def slot_setup(sk, slot):
    """回傳 (setup_attachment_name, setup_alpha)。"""
    for s in sk["slots"]:
        if s["name"] == slot:
            att = s.get("attachment")
            col = s.get("color", "ffffffff")
            alpha = int(col[6:8], 16) / 255.0 if len(col) >= 8 else 1.0
            return att, alpha
    return None, 1.0


def visible_at(sk, anim_name, slot, name, time, alpha_thresh=0.02):
    """該 attachment 在 anim 的 time 是否**實際可見**(attachment == name 且 alpha > 門檻)。
    對映 CLAUDE.md 雷點 #2/#3:attachment 受 slot timeline gating;再加 alpha gating
    (透明幀不算變形壞掉)。attachment timeline 為 step;color(alpha)可內插。"""
    setup_att, setup_alpha = slot_setup(sk, slot)
    anim = sk["animations"].get(anim_name, {})
    st = anim.get("slots", {}).get(slot, {})
    # attachment gating(step:取最後一個 time<=t 的 name)
    cur_att = setup_att
    for kf in st.get("attachment", []):
        if kf.get("time", 0.0) <= time:
            cur_att = kf.get("name")
        else:
            break
    if cur_att != name:
        return False
    # alpha gating
    cf = st.get("color", [])
    if cf:
        alphas = [(k.get("time", 0.0), int(k.get("color", "ffffffff")[6:8], 16) / 255.0,
                   k.get("curve", None)) for k in cf]
        if time <= alphas[0][0]:
            a = alphas[0][1]
        elif time >= alphas[-1][0]:
            a = alphas[-1][1]
        else:
            a = alphas[-1][1]
            for i in range(len(alphas) - 1):
                t0, a0, c0 = alphas[i]; t1, a1, _ = alphas[i + 1]
                if t0 <= time < t1:
                    if c0 == "stepped":
                        a = a0
                    elif c0 is None:
                        span = t1 - t0
                        a = a0 + (a1 - a0) * ((time - t0) / span if span > 1e-12 else 0)
                    else:  # bezier:保守取兩端最大(避免誤判可見)
                        a = max(a0, a1)
                    break
    else:
        a = setup_alpha
    return a > alpha_thresh


def anim_duration(sk, anim_name):
    dur = 0.0
    anim = sk["animations"][anim_name]
    for section in anim.values():
        if not isinstance(section, dict):
            continue
        for tl in section.values():
            if isinstance(tl, dict):
                for frames in tl.values():
                    if isinstance(frames, list):
                        for f in frames:
                            dur = max(dur, f.get("time", 0.0))
            elif isinstance(tl, list):
                for f in tl:
                    if isinstance(f, dict):
                        dur = max(dur, f.get("time", 0.0))
    return dur
