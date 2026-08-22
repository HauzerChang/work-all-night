#!/usr/bin/env python3
"""S3/S2 — weighted-mesh 骨骼驅動變形器 + 真值變形場 (bone-driven LBS deformer).

補上 `compare_robot_mesh.py` 的唯一未驗維度:**weighted mesh 的骨骼變形品質**。
`deform_eval.py` 只處理 unweighted(逐頂點 deform offset);weighted mesh 靠
「骨骼世界變換 + 每頂點權重」做 Linear Blend Skinning(LBS),需要另一條路。

本模組重現 Spine 3.8 對 weighted mesh 的 `computeWorldVertices`:
  world[v] = Σ_j  w_vj · ( M_j · bind_vj + t_j )       (M_j,t_j = bone_j 世界變換)
其中骨骼世界變換由動畫的 rotate/translate/scale timeline(緊湊 bezier)驅動:
  local: rotation = setup + angle(t) ; x = setupX + tx(t) ; scaleX = setupSX · sx(t) ...
  world: 依 Spine 拓樸序 (parent 先於 child) 逐骨合成 (transform=normal)。

⚠️ 對照 CLAUDE.md 雷點:
  #4 取變形後世界座標要「同步 re-pose」→ 這裡就是 re-pose 的 CPU 版(bone→world→LBS)。
  #6 weighted 格式:vertices = [n, boneIdx,bindX,bindY,weight, ...],hull 頂點排最前,
     bind 為相對該骨 setup 座標,權重每頂點和=1。
  #7 緊湊 bezier:{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2} 散鍵;"stepped"/linear 特例。

真值 = Award 的 3 個機器人 weighted mesh(光暈/左手/身體),由真實動畫 Award_Legend_In/Loop
的 LEG 骨群驅動。此變形場作為 S3 weighted 生成器(BBW)的變形品質對照基準。
"""
import json
import math
import numpy as np

DEG = math.pi / 180.0


# ---------------------------------------------------------------- skeleton IO
def load_skeleton(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_mesh_attachment(skel, slot, name=None):
    """回傳 (attachment, name)。weighted mesh 的 vertices 為攤平變長格式。"""
    skins = skel["skins"]
    entries = skins if isinstance(skins, list) else [
        {"name": k, "attachments": v} for k, v in skins.items()]
    for e in entries:
        atts = e.get("attachments", {})
        if slot in atts:
            for an, a in atts[slot].items():
                if a.get("type") == "mesh" and (name is None or an == name):
                    return a, an
    raise KeyError(f"mesh not found: slot={slot} name={name}")


def parse_weighted(att):
    """→ (bind, tris, hull, nv)  bind[v] = list of (boneIdx, bx, by, w)。
    若為 unweighted(vertices 長度==uvs 長度)則丟出,不在本模組範疇。"""
    verts = att["vertices"]
    uvs = att["uvs"]
    nv = len(uvs) // 2
    if len(verts) == len(uvs):
        raise ValueError("unweighted mesh — 用 deform_eval.py")
    bind = []
    i = 0
    while i < len(verts):
        n = int(verts[i]); i += 1
        entry = []
        for _ in range(n):
            bi = int(verts[i]); bx = verts[i + 1]; by = verts[i + 2]; w = verts[i + 3]
            entry.append((bi, bx, by, w)); i += 4
        bind.append(entry)
    assert len(bind) == nv, f"{len(bind)} != {nv}"
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    return bind, tris, att.get("hull", 0), nv


# ------------------------------------------------------------ bone transforms
class BonePose:
    """一次姿勢下所有骨骼的世界變換 (a,b,c,d, worldX, worldY)。transform=normal。"""

    def __init__(self, skel):
        self.bones = skel["bones"]
        self.n = len(self.bones)
        self.order = {b["name"]: i for i, b in enumerate(self.bones)}
        # setup local
        self.sx = [b.get("x", 0.0) for b in self.bones]
        self.sy = [b.get("y", 0.0) for b in self.bones]
        self.srot = [b.get("rotation", 0.0) for b in self.bones]
        self.sscx = [b.get("scaleX", 1.0) for b in self.bones]
        self.sscy = [b.get("scaleY", 1.0) for b in self.bones]
        self.sshx = [b.get("shearX", 0.0) for b in self.bones]
        self.sshy = [b.get("shearY", 0.0) for b in self.bones]
        self.parent = [self.order.get(b.get("parent")) if b.get("parent") else None
                       for b in self.bones]
        # world storage
        self.a = [1.0] * self.n; self.b = [0.0] * self.n
        self.c = [0.0] * self.n; self.d = [1.0] * self.n
        self.wx = [0.0] * self.n; self.wy = [0.0] * self.n

    def _world_from_local(self, i, rot, x, y, scx, scy, shx, shy):
        rotX = (rot + shx) * DEG
        rotY = (rot + 90.0 + shy) * DEG
        la = math.cos(rotX) * scx
        lc = math.sin(rotX) * scx
        lb = math.cos(rotY) * scy
        ld = math.sin(rotY) * scy
        p = self.parent[i]
        if p is None:
            self.a[i] = la; self.b[i] = lb; self.c[i] = lc; self.d[i] = ld
            self.wx[i] = x; self.wy[i] = y
        else:
            pa, pb, pc, pd = self.a[p], self.b[p], self.c[p], self.d[p]
            self.a[i] = pa * la + pb * lc
            self.b[i] = pa * lb + pb * ld
            self.c[i] = pc * la + pd * lc
            self.d[i] = pc * lb + pd * ld
            self.wx[i] = pa * x + pb * y + self.wx[p]
            self.wy[i] = pc * x + pd * y + self.wy[p]

    def pose(self, deltas=None):
        """deltas[i] = dict(rot,x,y,scx,scy,shx,shy) 相對 setup 的變化;None=setup。
        rot/x/y/shx 為加法偏移,scx/scy 為乘法。依 list 序(parent 先)更新。"""
        deltas = deltas or {}
        for i in range(self.n):
            dl = deltas.get(i, {})
            rot = self.srot[i] + dl.get("rot", 0.0)
            x = self.sx[i] + dl.get("x", 0.0)
            y = self.sy[i] + dl.get("y", 0.0)
            scx = self.sscx[i] * dl.get("scx", 1.0)
            scy = self.sscy[i] * dl.get("scy", 1.0)
            shx = self.sshx[i] + dl.get("shx", 0.0)
            shy = self.sshy[i] + dl.get("shy", 0.0)
            self._world_from_local(i, rot, x, y, scx, scy, shx, shy)
        return self

    def apply_to(self, bi, bx, by):
        return (self.a[bi] * bx + self.b[bi] * by + self.wx[bi],
                self.c[bi] * bx + self.d[bi] * by + self.wy[bi])


# ------------------------------------------------------------------- LBS
def world_vertices(bind, bonepose):
    out = np.zeros((len(bind), 2), dtype=np.float64)
    for v, entry in enumerate(bind):
        px = py = 0.0
        for (bi, bx, by, w) in entry:
            wxy = bonepose.apply_to(bi, bx, by)
            px += wxy[0] * w; py += wxy[1] * w
        out[v] = (px, py)
    return out


# --------------------------------------------------------- compact bezier
def _bezier_y_at_x(x, cx1, cy1, cx2, cy2):
    """P0(0,0) P1(cx1,cy1) P2(cx2,cy2) P3(1,1);給 x∈[0,1] 解 s 使 Bx(s)=x,回 By(s)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        s = 0.5 * (lo + hi)
        mt = 1.0 - s
        bx = 3 * mt * mt * s * cx1 + 3 * mt * s * s * cx2 + s * s * s
        if bx < x:
            lo = s
        else:
            hi = s
    s = 0.5 * (lo + hi)
    mt = 1.0 - s
    return 3 * mt * mt * s * cy1 + 3 * mt * s * s * cy2 + s * s * s


def _interp(keys, t, defaults):
    """keys = timeline frame list;回傳 dict(field→value) 在時間 t。
    defaults 給每個 field 的預設(rotate angle 缺=0,translate x/y 缺=0,scale x/y 缺=1)。
    加法欄位(angle→rot,x,y,shearX→shx...)缺省 0;scale 缺省 1(乘法)。"""
    fields = list(defaults.keys())
    if not keys:
        return {}
    times = [k.get("time", 0.0) for k in keys]

    def val(k, f):
        return k.get(f, defaults[f])

    if t <= times[0]:
        return {f: val(keys[0], f) for f in fields}
    if t >= times[-1]:
        return {f: val(keys[-1], f) for f in fields}
    # find segment
    for i in range(len(keys) - 1):
        if times[i] <= t <= times[i + 1]:
            k0, k1 = keys[i], keys[i + 1]
            span = times[i + 1] - times[i]
            p = (t - times[i]) / span if span > 0 else 0.0
            curve = k0.get("curve")
            if curve is None:            # linear
                factor = p
            elif curve == "stepped":
                factor = 0.0
            else:                        # compact bezier
                cx1 = curve
                cy1 = k0.get("c2", 0.0)
                cx2 = k0.get("c3", 0.0)
                cy2 = k0.get("c4", 0.0)
                factor = _bezier_y_at_x(p, cx1, cy1, cx2, cy2)
            out = {}
            for f in fields:
                v0 = val(k0, f); v1 = val(k1, f)
                out[f] = v0 + (v1 - v0) * factor
            return out
    return {f: val(keys[-1], f) for f in fields}


def bone_deltas_at(skel, anim_name, time):
    """回傳 {boneIdx: dict(rot,x,y,scx,scy,shx,shy)} 相對 setup 的偏移。"""
    anim = skel["animations"][anim_name]
    bones_tl = anim.get("bones", {})
    order = {b["name"]: i for i, b in enumerate(skel["bones"])}
    deltas = {}
    for bname, tls in bones_tl.items():
        bi = order.get(bname)
        if bi is None:
            continue
        d = {}
        if "rotate" in tls:
            d["rot"] = _interp(tls["rotate"], time, {"angle": 0.0})["angle"]
        if "translate" in tls:
            r = _interp(tls["translate"], time, {"x": 0.0, "y": 0.0})
            d["x"] = r["x"]; d["y"] = r["y"]
        if "scale" in tls:
            r = _interp(tls["scale"], time, {"x": 1.0, "y": 1.0})
            d["scx"] = r["x"]; d["scy"] = r["y"]
        if "shear" in tls:
            r = _interp(tls["shear"], time, {"x": 0.0, "y": 0.0})
            d["shx"] = r["x"]; d["shy"] = r["y"]
        if d:
            deltas[bi] = d
    return deltas


def anim_duration(skel, anim_name):
    anim = skel["animations"][anim_name]
    dur = 0.0
    for group in anim.values():
        if not isinstance(group, dict):
            continue
        for tls in group.values():
            if isinstance(tls, dict):
                for frames in tls.values():
                    if isinstance(frames, list):
                        for fr in frames:
                            dur = max(dur, fr.get("time", 0.0))
            elif isinstance(tls, list):
                for fr in tls:
                    dur = max(dur, fr.get("time", 0.0))
    return dur


def deform_field(skel, slot, name, anim_name, n_samples=17):
    """對一件 weighted mesh,回傳 (times, frames[nv,2] list, setup[nv,2], tris, hull)。
    frames[k] = 第 k 個取樣時間的世界座標。第 0 幀為 setup(deltas=None)。"""
    att, an = get_mesh_attachment(skel, slot, name)
    bind, tris, hull, nv = parse_weighted(att)
    bp = BonePose(skel)
    setup = world_vertices(bind, bp.pose(None))
    dur = anim_duration(skel, anim_name)
    times = [dur * k / (n_samples - 1) for k in range(n_samples)]
    frames = []
    for t in times:
        deltas = bone_deltas_at(skel, anim_name, t)
        frames.append(world_vertices(bind, bp.pose(deltas)))
    return times, frames, setup, tris, hull
