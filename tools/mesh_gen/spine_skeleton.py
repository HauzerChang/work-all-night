#!/usr/bin/env python3
"""Spine 3.8 骨架前向運動學 (FK) + weighted mesh 蒙皮 (skinning)。

用途:對 **weighted mesh**(靠骨骼+權重變形,非逐頂點 deform)重現變形後世界座標,
供 `weighted_deform_eval.py` 量化「骨骼驅動下的變形品質」(自交/翻面/平滑度)。
補上 `deform_eval.py`(只處理 unweighted 逐頂點 deform)的缺口。

只實作 transform mode = 'normal'(已確認 Award 機器人骨鏈全為 normal;見雷點)。
座標系:Spine 世界座標 y-up。

Spine 3.8 世界矩陣(normal 繼承,對照官方 Bone.updateWorldTransform):
    rotationY = rotation + 90 + shearY
    la = cos(rotation+shearX)*scaleX ; lb = cos(rotationY)*scaleY
    lc = sin(rotation+shearX)*scaleX ; ld = sin(rotationY)*scaleY
    a = pa*la + pb*lc ; b = pa*lb + pb*ld
    c = pc*la + pd*lc ; d = pc*lb + pd*ld
    worldX = pa*x + pb*y + parent.worldX
    worldY = pc*x + pd*y + parent.worldY

動畫(3.8):rotate=setup+angle;translate=setup+(x,y);scale=setup*(sx,sy)。
關鍵幀間用**緊湊 bezier**(單一曲線控制百分比;雷點 #7):
    {"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}  端點隱含 (0,0)、(1,1)
    "stepped" → 保持左值;缺省/"linear" → 線性。
"""
import json, math
import numpy as np

DEG = math.pi / 180.0


# ---------- 緊湊 bezier 求值 ----------
def _bezier_percent(cx1, cy1, cx2, cy2, t):
    """三次 bezier(P0=(0,0),P1=(cx1,cy1),P2=(cx2,cy2),P3=(1,1)):
    給正規化時間 t∈[0,1],解 X(s)=t 後回傳 Y(s)(= 值的內插百分比)。"""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    # X(s) 對 s 單調(合法 easing)→ 二分法
    lo, hi = 0.0, 1.0
    for _ in range(50):
        s = (lo + hi) * 0.5
        u = 1.0 - s
        x = 3 * u * u * s * cx1 + 3 * u * s * s * cx2 + s * s * s
        if x < t:
            lo = s
        else:
            hi = s
    s = (lo + hi) * 0.5
    u = 1.0 - s
    return 3 * u * u * s * cy1 + 3 * u * s * s * cy2 + s * s * s


def _interp(frames, time, keys, defaults):
    """通用關鍵幀取樣。frames:[{time,<keys>,curve...}];回傳 dict{key:value}。
    curve 存在 FROM 幀上。stepped → 保持左值。"""
    if not frames:
        return dict(zip(keys, defaults))
    # clamp
    if time <= frames[0].get("time", 0.0):
        return {k: frames[0].get(k, d) for k, d in zip(keys, defaults)}
    if time >= frames[-1].get("time", 0.0):
        return {k: frames[-1].get(k, d) for k, d in zip(keys, defaults)}
    # 找區間
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0)
        t1 = frames[i + 1].get("time", 0.0)
        if t0 <= time <= t1:
            f0, f1 = frames[i], frames[i + 1]
            span = t1 - t0
            lt = (time - t0) / span if span > 1e-12 else 0.0
            curve = f0.get("curve", None)
            if curve == "stepped":
                pct = 0.0
            elif curve is None or curve == "linear":
                pct = lt
            else:
                # 緊湊格式:curve=cx1, c2=cy1, c3=cx2, c4=cy2
                cx1 = float(curve)
                cy1 = float(f0.get("c2", 0.0))
                cx2 = float(f0.get("c3", 1.0))
                cy2 = float(f0.get("c4", 1.0))
                pct = _bezier_percent(cx1, cy1, cx2, cy2, lt)
            out = {}
            for k, d in zip(keys, defaults):
                v0 = f0.get(k, d)
                v1 = f1.get(k, d)
                out[k] = v0 + (v1 - v0) * pct
            return out
    return {k: frames[-1].get(k, d) for k, d in zip(keys, defaults)}


# ---------- 骨架 ----------
class Skeleton:
    def __init__(self, data):
        self.data = data
        self.bones = data["bones"]
        self.byname = {b["name"]: b for b in self.bones}
        # 依 JSON 順序即為 parent-before-child(Spine 慣例);建索引
        self.order = [b["name"] for b in self.bones]

    def _local(self, b, anim_bones, time):
        """回傳該骨在 time 的 local (x,y,rotation,scaleX,scaleY,shearX,shearY)。"""
        x = b.get("x", 0.0); y = b.get("y", 0.0)
        rot = b.get("rotation", 0.0)
        sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
        shx = b.get("shearX", 0.0); shy = b.get("shearY", 0.0)
        if anim_bones and b["name"] in anim_bones:
            ch = anim_bones[b["name"]]
            if "rotate" in ch:
                rot += _interp(ch["rotate"], time, ["angle"], [0.0])["angle"]
            if "translate" in ch:
                d = _interp(ch["translate"], time, ["x", "y"], [0.0, 0.0])
                x += d["x"]; y += d["y"]
            if "scale" in ch:
                d = _interp(ch["scale"], time, ["x", "y"], [1.0, 1.0])
                sx *= d["x"]; sy *= d["y"]
            if "shear" in ch:
                d = _interp(ch["shear"], time, ["x", "y"], [0.0, 0.0])
                shx += d["x"]; shy += d["y"]
        return x, y, rot, sx, sy, shx, shy

    def world_transforms(self, anim=None, time=0.0):
        """回傳 {bone_name: (a,b,c,d,worldX,worldY)}(normal 繼承)。"""
        anim_bones = None
        if anim is not None:
            anim_bones = self.data["animations"][anim].get("bones", {})
        W = {}
        for name in self.order:
            b = self.byname[name]
            x, y, rot, sx, sy, shx, shy = self._local(b, anim_bones, time)
            rotY = rot + 90 + shy
            la = math.cos((rot + shx) * DEG) * sx
            lb = math.cos(rotY * DEG) * sy
            lc = math.sin((rot + shx) * DEG) * sx
            ld = math.sin(rotY * DEG) * sy
            parent = b.get("parent")
            if parent is None:
                # root:父為 skeleton(scale 預設 1,無旋轉平移)
                W[name] = (la, lb, lc, ld, x, y)
            else:
                pa, pb, pc, pd, pwx, pwy = W[parent]
                a = pa * la + pb * lc
                bb = pa * lb + pb * ld
                c = pc * la + pd * lc
                d = pc * lb + pd * ld
                wx = pa * x + pb * y + pwx
                wy = pc * x + pd * y + pwy
                W[name] = (a, bb, c, d, wx, wy)
        return W


# ---------- weighted mesh 解碼 + 蒙皮 ----------
def decode_weighted(vertices):
    """Spine weighted 攤平格式 → [[(boneIdx,bx,by,w), ...] per vertex]。"""
    i = 0; out = []
    while i < len(vertices):
        n = int(vertices[i]); i += 1
        e = []
        for _ in range(n):
            bi = int(vertices[i]); bx = vertices[i + 1]; by = vertices[i + 2]; w = vertices[i + 3]
            i += 4
            e.append((bi, bx, by, w))
        out.append(e)
    return out


def is_weighted(att):
    return att.get("type") == "mesh" and len(att.get("vertices", [])) != len(att.get("uvs", []))


def skin_vertices(vw, bone_names, W):
    """vw:decode_weighted 結果;bone_names:JSON bones 順序(idx→name);
    W:world_transforms 輸出。回傳 Nx2 世界座標(y-up)。"""
    out = np.zeros((len(vw), 2), dtype=np.float64)
    for i, entries in enumerate(vw):
        wx = wy = 0.0
        for bi, bx, by, w in entries:
            a, b, c, d, tx, ty = W[bone_names[bi]]
            wx += (a * bx + b * by + tx) * w
            wy += (c * bx + d * by + ty) * w
        out[i, 0] = wx; out[i, 1] = wy
    return out


def load(path):
    return Skeleton(json.load(open(path)))


def get_attachment(data, slot, name=None):
    skin = data["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    entry = atts[slot]
    if name is None:
        name = list(entry.keys())[0]
    return entry[name], name


if __name__ == "__main__":
    import sys
    sk = load(sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json")
    bone_names = sk.order
    for slot in ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]:
        att, name = get_attachment(sk.data, slot)
        vw = decode_weighted(att["vertices"])
        W0 = sk.world_transforms()
        v0 = skin_vertices(vw, bone_names, W0)
        mn, mx = v0.min(0), v0.max(0)
        print(f"{slot}: setup world bbox = "
              f"[{mn[0]:.1f},{mn[1]:.1f}]..[{mx[0]:.1f},{mx[1]:.1f}] "
              f"size {mx[0]-mn[0]:.1f}x{mx[1]-mn[1]:.1f}")
