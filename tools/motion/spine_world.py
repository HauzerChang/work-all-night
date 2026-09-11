#!/usr/bin/env python3
"""Spine 3.8 **世界座標** 取樣器 — 軌跡分析工具的計算核心。

與 `tools/analyzer/spine_anim.py` 的分工:
  - `spine_anim.sample()` 只取 **local 通道值**(扁平骨架假設),用於 keyframe 生成的自我驗證。
  - 本模組沿骨骼父鏈算 **世界矩陣**,可回答「這根骨骼(或它上面某個點)在畫面上跑了什麼軌跡」,
    並支援 `zero=` 把指定骨骼的動畫通道歸零 → 取得「剛體跟隨」(主體帶給它的運動)。

spine-motion-skill 的第 3 步(分離剛體跟隨 vs 自身位移)就是靠這兩者相減:
    own(t) = actual(t) - rigid(t)

Bezier 內插直接重用 `spine_anim._interp`(緊湊 bezier / stepped / linear 三種曲線),
避免兩份取樣器對同一份 JSON 給出不同答案。
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# 本目錄先進 path(skill 套件內帶的 spine_anim 蒐錄版),analyzer 再插到最前面
# → 在 repo 裡用 tools/analyzer/spine_anim.py(唯一真相來源),打包成 skill 時用套件內的同一份程式碼。
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "analyzer"))
from spine_anim import _interp  # noqa: E402  (重用同一套曲線內插)

# Spine 3.8 支援但本取樣器只精確實作前兩種的 transform 繼承模式
SUPPORTED_TRANSFORM = ("normal", "onlyTranslation")
KNOWN_TRANSFORM = SUPPORTED_TRANSFORM + ("noRotationOrReflection", "noScale", "noScaleOrReflection")


class Skel:
    """骨架 + 動畫的世界座標取樣器。"""

    def __init__(self, data):
        self.data = data
        self.bone_list = data.get("bones", [])
        self.bones = {b["name"]: b for b in self.bone_list}
        self.warnings = []
        for b in self.bone_list:
            tm = b.get("transform", "normal")
            if tm not in SUPPORTED_TRANSFORM:
                self.warnings.append(
                    f"bone '{b['name']}' transform='{tm}' 未精確支援,以 normal 近似"
                    + ("" if tm in KNOWN_TRANSFORM else "(未知模式)")
                )

    # ---------- 父鏈 ----------
    def parent_chain(self, name):
        """回傳 [parent, grandparent, ..., root]。"""
        out, b = [], self.bones[name]
        while b.get("parent"):
            out.append(b["parent"])
            b = self.bones[b["parent"]]
        return out

    def children(self, name):
        return [b["name"] for b in self.bone_list if b.get("parent") == name]

    # ---------- local ----------
    ALL_CH = ("translate", "rotate", "scale", "shear")

    def zeroed_channels(self, name, zero):
        """`zero` 可以是骨骼名集合(該骨骼所有通道歸零),或 {骨骼名: (通道,...)}(只歸零指定通道)。
        分離『自身位移』時要能只歸零 translate 或只歸零 rotate,才能把兩者的貢獻拆乾淨。"""
        if isinstance(zero, dict):
            v = zero.get(name)
            if v is None:
                return ()
            if v is True or v == "all":
                return self.ALL_CH
            return tuple(v)
        return self.ALL_CH if name in zero else ()

    def local(self, name, anim, t, zero=()):
        """setup + 動畫通道 → (x, y, rotation, scaleX, scaleY, shearX, shearY)。
        `zero` 指定的通道視為未動(=該骨骼那個通道不出力,只被父體帶著走)。"""
        b = self.bones[name]
        x, y = b.get("x", 0.0), b.get("y", 0.0)
        rot = b.get("rotation", 0.0)
        sx, sy = b.get("scaleX", 1.0), b.get("scaleY", 1.0)
        shx, shy = b.get("shearX", 0.0), b.get("shearY", 0.0)
        tl = (anim.get("bones") or {}).get(name) if anim else None
        if not tl:
            return (x, y, rot, sx, sy, shx, shy)
        z = self.zeroed_channels(name, zero)
        if "translate" in tl and "translate" not in z:
            v = _interp(tl["translate"], t, ["x", "y"])
            x += v["x"]
            y += v["y"]
        if "rotate" in tl and "rotate" not in z:
            rot += _interp(tl["rotate"], t, ["angle"])["angle"]
        if "scale" in tl and "scale" not in z:
            v = _interp(tl["scale"], t, ["x", "y"])
            # scale timeline 缺省值為 1(不是 0),_interp 的 0 預設要補回來
            sx *= _dflt(v["x"], tl["scale"], "x")
            sy *= _dflt(v["y"], tl["scale"], "y")
        if "shear" in tl and "shear" not in z:
            v = _interp(tl["shear"], t, ["x", "y"])
            shx += v["x"]
            shy += v["y"]
        return (x, y, rot, sx, sy, shx, shy)

    # ---------- world ----------
    def world(self, name, anim, t, zero=()):
        """回傳世界矩陣 (a, b, c, d, wx, wy);點 (lx,ly) 的世界座標 = (a*lx+b*ly+wx, c*lx+d*ly+wy)。"""
        bone = self.bones[name]
        x, y, rot, sx, sy, shx, shy = self.local(name, anim, t, zero)
        ry = math.radians(rot + 90 + shy)
        rx = math.radians(rot + shx)
        la, lc = math.cos(rx) * sx, math.sin(rx) * sx
        lb, ld = math.cos(ry) * sy, math.sin(ry) * sy
        parent = bone.get("parent")
        if not parent:
            return (la, lb, lc, ld, x, y)
        pa, pb, pc, pd, px, py = self.world(parent, anim, t, zero)
        wx, wy = pa * x + pb * y + px, pc * x + pd * y + py
        mode = bone.get("transform", "normal")
        if mode == "onlyTranslation":
            return (la, lb, lc, ld, wx, wy)
        return (pa * la + pb * lc, pa * lb + pb * ld,
                pc * la + pd * lc, pc * lb + pd * ld, wx, wy)

    def world_pos(self, name, anim, t, zero=(), lx=0.0, ly=0.0):
        a, b, c, d, wx, wy = self.world(name, anim, t, zero)
        return (a * lx + b * ly + wx, c * lx + d * ly + wy)

    def world_to_local_delta(self, name, anim, t, dX, dY, zero=()):
        """世界座標位移 (dX,dY) → 該骨骼**父體空間**的 local 位移 (dx,dy)。
        用於「在世界座標設計自身位移,再換回 translate 關鍵值」。"""
        parent = self.bones[name].get("parent")
        if not parent:
            return (dX, dY)
        a, b, c, d, _, _ = self.world(parent, anim, t, zero)
        det = a * d - b * c
        if abs(det) < 1e-12:
            raise ValueError(f"parent '{parent}' 世界矩陣不可逆(det≈0)")
        return ((d * dX - b * dY) / det, (-c * dX + a * dY) / det)


    def own_split(self, name, anim, t, px=0.0, py=0.0):
        """把追蹤點的世界運動拆成三塊(精確可加,見 knowledge/s6):

            actual = rigid + rotOwn + transOwn

        · rigid    : 目標骨骼所有通道歸零 → 純粹被父體(主體)帶著走的運動
        · rotOwn   : 只留 rotate/scale/shear → 目標骨骼自轉帶動追蹤點的位移
        · transOwn : 只由 translate 通道造成的位移 = 父體世界矩陣 × local 位移
                     (**這是編輯器可直接編輯、且能無損寫回 translate 關鍵值的通道**)
        回傳 (rigid, rotOwn, transOwn, actual),每項為 (x, y)。
        """
        rigid = self.world_pos(name, anim, t, zero=(name,), lx=px, ly=py)
        norot = self.world_pos(name, anim, t, zero={name: ("rotate", "scale", "shear")}, lx=px, ly=py)
        notrans = self.world_pos(name, anim, t, zero={name: ("translate",)}, lx=px, ly=py)
        actual = self.world_pos(name, anim, t, lx=px, ly=py)
        rot_own = (notrans[0] - rigid[0], notrans[1] - rigid[1])
        trans_own = (norot[0] - rigid[0], norot[1] - rigid[1])
        return (rigid, rot_own, trans_own, actual)


def _dflt(v, frames, key):
    """scale timeline 的缺省值是 1;_interp 對缺鍵回 0,這裡補回。"""
    if not frames:
        return 1.0
    if any(key in f for f in frames):
        return v
    return 1.0


def duration(anim):
    """動畫總長(秒)= 所有 timeline 最大 time。"""
    m = 0.0

    def walk(o):
        nonlocal m
        if isinstance(o, dict):
            tv = o.get("time")
            if isinstance(tv, (int, float)):
                m = max(m, float(tv))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(anim)
    return m


def key_times(anim, bone):
    """某骨骼所有通道的 keyframe 時間(排序去重)。"""
    tl = (anim.get("bones") or {}).get(bone, {})
    ts = {round(float(k.get("time", 0.0)), 6) for ch in tl.values() for k in ch}
    return sorted(ts)


def extrema(frames, values, eps=1e-9):
    """回傳 [(frame, value, 'max'|'min')];以循環(首尾相接)判斷,適合 loop 動畫。"""
    n = len(values) - 1  # 最後一點 == 第一點(loop)
    if n < 3:
        return []
    out = []
    for i in range(n):
        p, q = values[i - 1], values[(i + 1) % n]
        v = values[i]
        if v > p + eps and v >= q - eps:
            out.append((frames[i], v, "max"))
        elif v < p - eps and v <= q + eps:
            out.append((frames[i], v, "min"))
    return out


def pearson(a, b):
    n = len(a)
    if n == 0:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((x - mb) ** 2 for x in b) ** 0.5
    if va < 1e-12 or vb < 1e-12:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb)


def best_lag(body, own, spf):
    """循環互相關:own 相對 body 延後幾幀時**負相關最強**(=最互補)、正相關最強(=最同步)。
    回傳 (lag_complementary_frames, r_at_that_lag, lag_sync_frames, r_sync)。"""
    n = len(own) - 1
    if n < 4:
        return (0.0, 0.0, 0.0, 0.0)
    best_c, best_s = (0, 2.0), (0, -2.0)
    for s in range(n):
        shifted = [own[(i - s) % n] for i in range(n)]
        r = pearson(body[:n], shifted)
        if r < best_c[1]:
            best_c = (s, r)
        if r > best_s[1]:
            best_s = (s, r)
    return (best_c[0] / spf, best_c[1], best_s[0] / spf, best_s[1])
