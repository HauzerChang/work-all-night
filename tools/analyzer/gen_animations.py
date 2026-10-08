#!/usr/bin/env python3
"""candidate 0d — 分鏡(storyboard)→ Spine 3.8 `animations` keyframe(純 CPU,確定性)。

輸入:build_spine.py 產出的 skeleton.json(bones/slots/skin,animations 為空)
      + analyze_target 的 `3_motion_storyboard`(每檔位 beat × 每件 role/action 的**符號**描述)。
輸出:把三個 beat(In/Loop/Out)具體化為可載入的 Spine 3.8 timeline(bone rotate/translate/scale
      + slot color alpha),寫回 skeleton.json 的 `animations`。

設計原則(RULES:確定性演算法 + 評估器,不用 ML 學美術決定):
  role → 運動基元(motion primitive)的固定對映,幅度/相位為可調參數。
  - Loop:整體微呼吸;用**正弦取樣**關鍵幀(N/cycle),端點強制相等 → 無縫(AC2)。
    body=縮放呼吸、head=點頭、limb=末梢擺盪(**左右反相**)、特效=alpha 脈動+緩轉。
  - In  :scale 0→overshoot→1、alpha 0→1、limb 旋轉甩入、translate 由外側徑向歸位;**收在 setup identity**。
  - Out :由 identity → 收斂(scale/alpha→0)。
  三 beat 皆以 setup identity 為介面 → In 尾 == Loop 首/尾 == Out 首,可無縫串接(AC4)。

單位同 Spine runtime:rotate=角度增量(度)、translate=相對 setup local 位移(px)、
scale=乘在 setup(=1)的倍率、color=8-hex RGBA(alpha=末兩碼)。
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

# beat 類別 → 時長(秒)。beat 名為 genre 相依,先歸類再驅動基元(跨 genre 通用)。
DUR = {"intro": 0.6, "loop": 2.0, "outro": 0.4, "hold": 1.0, "pulse": 0.5}
LOOP_SAMPLES = 12  # loop 每 cycle 的正弦取樣數
EASE = 0.25        # intro/outro bezier 緩動控制(ease-out 近似)

# beat 名(小寫,含中英)→ 語意類別。未命中預設 loop(最安全:無縫、可 idle)。
_CAT_KEYWORDS = {
    "intro": ["in", "comeout", "come_out", "open", "appear", "enter", "start", "入場", "進場", "出現"],
    "outro": ["out", "close", "exit", "disappear", "leave", "end", "退場", "離場", "消失"],
    "loop": ["loop", "idle", "breath", "待機", "循環", "呼吸"],
    "hold": ["static", "hold", "base", "靜態", "定格"],
    # pulse = 泛用對稱脈衝(輕重音);主秀節拍 hit/reveal 由 beat_templates 提供更完整簽章
    # (見本檔尾端註冊),故 hit/burst 移出 pulse。
    "pulse": ["flash", "win", "閃"],
}


def beat_category(name):
    low = str(name).lower()
    # 精確 token 優先(避免子字串誤判,如 'legend' 含 'end')
    for cat, kws in _CAT_KEYWORDS.items():
        for kw in kws:
            if low == kw:
                return cat
    for cat, kws in _CAT_KEYWORDS.items():
        for kw in kws:
            if kw in low:
                return cat
    return "loop"


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _alpha_hex(a):
    v = max(0, min(255, int(round(a * 255))))
    return "ffffff{:02x}".format(v)


def _rot(frames):
    return [{"time": round(t, 4), "angle": round(a, 3)} for (t, a) in frames]


def _xy(frames):
    return [{"time": round(t, 4), "x": round(x, 3), "y": round(y, 3)} for (t, x, y) in frames]


def _color(frames):
    return [{"time": round(t, 4), "color": _alpha_hex(a)} for (t, a) in frames]


def _loop_sine(amp, phase=0.0, kind="sin"):
    """回傳 [(t, value)] 一個無縫循環(端點值相等)。
    kind: 'sin' → amp*sin(2πτ+phase);'ucos' → amp*(1-cos(2πτ))/2(0→peak→0)。"""
    T = DUR["loop"]
    pts = []
    for i in range(LOOP_SAMPLES + 1):
        tau = i / LOOP_SAMPLES
        if kind == "sin":
            v = amp * math.sin(2 * math.pi * tau + phase)
        else:  # ucos:0 在端點,peak 在中點
            v = amp * (1 - math.cos(2 * math.pi * tau)) / 2.0
        pts.append((tau * T, v))
    # 端點強制相等 → 無縫(消除浮點殘差)
    pts[-1] = (pts[-1][0], pts[0][1])
    return pts


def _bez(frames_with_curve):
    """給每筆(除最後)插入 ease-out bezier 緊湊鍵。"""
    for f in frames_with_curve[:-1]:
        f["curve"] = EASE
        f["c2"] = 0.0
        f["c3"] = EASE
        f["c4"] = 1.0
    return frames_with_curve


def gen_loop(role, side_sign, radial=None):
    """Loop:回傳 (bone_timelines, slot_timelines)。"""
    b, s = {}, {}
    if role == "body":
        sc = _loop_sine(0.02, kind="sin")   # ±2% 呼吸
        b["scale"] = [{"time": round(t, 4), "x": round(1 + v, 4), "y": round(1 + v, 4)} for (t, v) in sc]
        b["translate"] = _xy([(t, 0.0, v) for (t, v) in _loop_sine(4.0, kind="sin")])
    elif role == "head":
        b["rotate"] = _rot([(t, v) for (t, v) in _loop_sine(3.0, kind="sin")])
    elif role in ("limb",):
        # 末梢擺盪,左右**反相**(side_sign=±1)→ 明確錯開(AC3 相位)
        b["rotate"] = _rot([(t, side_sign * v) for (t, v) in _loop_sine(5.0, kind="sin")])
    elif role == "特效":
        # alpha 脈動 + scale 微脹 + 緩轉(皆無縫)
        s["color"] = _color([(t, 1.0 - v) for (t, v) in _loop_sine(0.22, kind="ucos")])
        sc = _loop_sine(0.03, kind="ucos")
        b["scale"] = [{"time": round(t, 4), "x": round(1 + v, 4), "y": round(1 + v, 4)} for (t, v) in sc]
        b["rotate"] = _rot([(t, v) for (t, v) in _loop_sine(4.0, kind="sin")])
    return b, s


def gen_in(role, side_sign, radial):
    """In:入場爆發,收在 identity。radial=(ux,uy) 徑向外側單位向量(件由外側歸位)。"""
    T = DUR["intro"]
    b, s = {}, {}
    ux, uy = radial
    if role == "特效":
        b["scale"] = _bez([{"time": 0.0, "x": 0.02, "y": 0.02},
                            {"time": round(0.5 * T, 4), "x": 1.25, "y": 1.25},
                            {"time": round(T, 4), "x": 1.0, "y": 1.0}])
        b["rotate"] = _bez(_rot([(0.0, -40.0), (T, 0.0)]))
        s["color"] = _color([(0.0, 0.0), (0.5 * T, 1.0), (T, 1.0)])
    else:
        # scale 0→overshoot→1
        b["scale"] = _bez([{"time": 0.0, "x": 0.02, "y": 0.02},
                            {"time": round(0.7 * T, 4), "x": 1.12, "y": 1.12},
                            {"time": round(T, 4), "x": 1.0, "y": 1.0}])
        # translate 由外側 40px 歸位
        b["translate"] = _bez(_xy([(0.0, ux * 40.0, uy * 40.0), (T, 0.0, 0.0)]))
        s["color"] = _color([(0.0, 0.0), (T, 1.0)])
        if role == "limb":
            b["rotate"] = _bez(_rot([(0.0, side_sign * 20.0), (T, 0.0)]))
        elif role == "head":
            b["rotate"] = _bez(_rot([(0.0, 8.0), (0.6 * T, -4.0), (T, 0.0)]))
    return b, s


def gen_out(role, side_sign, radial):
    """Out:由 identity 收斂(scale/alpha→0)。"""
    T = DUR["outro"]
    b, s = {}, {}
    ux, uy = radial
    b["scale"] = _bez([{"time": 0.0, "x": 1.0, "y": 1.0},
                       {"time": round(T, 4), "x": 0.02, "y": 0.02}])
    s["color"] = _color([(0.0, 1.0), (T, 0.0)])
    if role in ("limb", "特效"):
        b["translate"] = _bez(_xy([(0.0, 0.0, 0.0), (T, ux * 20.0, uy * 20.0)]))
    if role == "特效":
        b["rotate"] = _bez(_rot([(0.0, 0.0), (T, 25.0)]))
    return b, s


def gen_hold(role, side_sign, radial):
    """hold/static:定格於 identity(2 幀 identity,構成合法短動畫,首尾皆 identity)。"""
    T = DUR["hold"]
    b = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": round(T, 4), "x": 1.0, "y": 1.0}]}
    return b, {}


def gen_pulse(role, side_sign, radial):
    """pulse/hit:identity→peak→identity 的對稱脈衝(首尾皆 identity → 可無縫串接)。"""
    T = DUR["pulse"]
    b, s = {}, {}
    if role == "特效":
        b["scale"] = _bez([{"time": 0.0, "x": 1.0, "y": 1.0},
                            {"time": round(0.5 * T, 4), "x": 1.3, "y": 1.3},
                            {"time": round(T, 4), "x": 1.0, "y": 1.0}])
        s["color"] = _color([(0.0, 1.0), (0.5 * T, 0.6), (T, 1.0)])
    else:
        peak = 1.12 if role == "body" else 1.08
        b["scale"] = _bez([{"time": 0.0, "x": 1.0, "y": 1.0},
                            {"time": round(0.5 * T, 4), "x": peak, "y": peak},
                            {"time": round(T, 4), "x": 1.0, "y": 1.0}])
        if role == "limb":
            b["rotate"] = _bez(_rot([(0.0, 0.0), (0.5 * T, side_sign * 10.0), (T, 0.0)]))
    return b, s


_DISPATCH = {"intro": gen_in, "loop": gen_loop, "outro": gen_out, "hold": gen_hold, "pulse": gen_pulse}

# candidate 0f — 註冊 big-win 主秀 beat 模板(anticipation+settle)。放檔尾避免與 beat_templates
# 形成 import 迴圈:beat_templates 只需本檔上方已定義的 DUR/_rot/_xy/_color。
try:
    from beat_templates import gen_hit as _gen_hit, gen_reveal as _gen_reveal, \
        gen_combo as _gen_combo, gen_anticipate_hold as _gen_charge, gen_cascade as _gen_cascade, \
        gen_wobble as _gen_wobble, gen_squash as _gen_squash, gen_twist as _gen_twist, \
        HIT_KEYWORDS as _HIT_KW, REVEAL_KEYWORDS as _REVEAL_KW, \
        COMBO_KEYWORDS as _COMBO_KW, CHARGE_KEYWORDS as _CHARGE_KW, \
        CASCADE_KEYWORDS as _CASCADE_KW, WOBBLE_KEYWORDS as _WOBBLE_KW, \
        SQUASH_KEYWORDS as _SQUASH_KW, TWIST_KEYWORDS as _TWIST_KW, DUR as _DUR_EXT
    _DISPATCH["hit"] = _gen_hit
    _DISPATCH["reveal"] = _gen_reveal
    _DISPATCH["combo"] = _gen_combo
    _DISPATCH["charge"] = _gen_charge
    _DISPATCH["cascade"] = _gen_cascade
    _DISPATCH["wobble"] = _gen_wobble  # candidate G-4':產出 shear 通道的斜拉節拍
    _DISPATCH["squash"] = _gen_squash  # candidate G-4'''':shear + 耦合非均勻 scale 的體積守恆擠壓
    _DISPATCH["twist"] = _gen_twist    # candidate G-4'''''':反相雙軸 shear(首度驅動 shearY)
    DUR.update(_DUR_EXT)  # 讓 hit/reveal/combo/charge/cascade/wobble/squash/twist 時長對 spine_anim.duration 一致
    # 主秀類別置前:exact/substring 命中優先於泛用 pulse(squash/twist 亦置前;放 wobble 前避免關鍵字爭用)
    _CAT_KEYWORDS = {"cascade": _CASCADE_KW, "combo": _COMBO_KW, "charge": _CHARGE_KW,
                     "twist": _TWIST_KW, "squash": _SQUASH_KW, "wobble": _WOBBLE_KW, "hit": _HIT_KW,
                     "reveal": _REVEAL_KW, **_CAT_KEYWORDS}
except ImportError:
    pass

# cascade 是**跨件時序**類別:單件產生器需知道自己在件序中的相位(phase∈[0,1])。
# 只有這類別要吃 phase,故集中列名,build_animations 依此決定是否帶入(其餘類別簽章不變)。
_PHASE_AWARE = {"cascade"}

# candidate J — 檔位(tier)幅度差異化(主秀 beat 依檔位增益放大;純函式,無 import 迴圈)。
from tier_variants import MAIN_SHOW_CATS as _MAIN_SHOW_CATS, \
    COUNT_AWARE_CATS as _COUNT_AWARE_CATS, COUPLED_SCALE_CATS as _COUPLED_SCALE_CATS, \
    VOL_TWIST_CATS as _VOL_TWIST_CATS, amplify_anim as _amplify_anim


# candidate J-5:cascade 跨件波的**相位來源**。預設(None)= 件序(storyboard parts 列表順序,byte-identical)。
# 其餘值把相位改由**空間位置**決定(波的方向變成物理幾何而非作者排版順序):
#   "lr" 左→右(bd.x 升序,最左件先 pop)、"rl" 右→左、"co" 中心外擴(距畫布中心升序,最內件先)、
#   "oc" 外向內、"po" 件序(顯式控制組,逐位元同 None)。相位值仍 rank/(nvalid−1)∈[0,1],只是 rank 的**排序鍵**改變;
# 波形(SPAN/nrip/深度)完全不動 → 與 J/J-3/J-4 三軸正交(方向只決定「哪件何時 pop」,不決定「多開/幾道/多深」)。
#
# candidate J-6:把**方向軸**從 J-5 的 4 個具名(基數軸 lr/rl + radial co/oc)**一般化為連續**:
#   - 角度(數字,度):相位依件中心在單位向量 `(cosθ, sinθ)` 上的**投影** `x·cosθ + y·sinθ` 排序。
#   - 向量 `(ux, uy)`:同上,投影到該(正規化)向量;零向量 → ValueError。
#   lr == θ=0°(投影到 +x 軸,`k=x`)、rl == θ=180°(`k=−x`)→ 投影族的**基數軸特例**,逐位元相容。
#   co/oc 是 **radial**(距中心,非線性),**不是**投影,保留為各自特例(投影無法表達徑向序)。
#   J-6 不是「第四條正交軸」,而是把 J-5 的**方向軸由離散(4 向)補成連續(任意角 + 向量)**;機制仍是
#   「既有相位的重新指派(排列)」—— 只是**排序鍵**從 {基數軸, radial} 擴成 {任意投影角, radial}。
_CASCADE_DIRS = {"lr", "rl", "co", "oc", "po"}

# candidate J-7:把 cascade 方向軸的**取值來源**由「手感指定」下推一層成「由資產幾何導出」。
# J-5 把方向立為相位來源(4 具名)、J-6 把其值連續化(角 / 向量),但「用哪個方向」仍是 per-genre 手感常數
# (`tier_variants.TIER_CASCADE_DIR`,如 slot_bigwin→"co")。J-7 新增 sentinel `cascade_dir="geo"`:方向**向量**
# 由件實際幾何導出(質心→最遠件),隨資產自適應,不再寫死。導出後仍走 **J-6 的投影排序(同機制)**,故 J-7
# **不是新正交軸**,是**方向軸取值的來源**(provenance):J-5 空間化→J-6 連續化→J-7 自動化,三者逐步移除人手指定。
_CASCADE_GEO_SOURCES = {"centroid_farthest", "pca", "pca_minor", "farthest_pair", "hull_long_edge"}
_CASCADE_GEO_DEFAULT = "centroid_farthest"


def _pca_principal_axis_dir(centers, aniso_tol=1e-6, minor=False):
    """candidate (J-8/J-9) — 件中心的 **PCA 散佈軸**單位向量 `(ux, uy)`,**符號確定性地**解決。

    閉式 2×2 PCA(避免外部 `eig` 的特徵向量 ±符號不確定):共變異矩陣 `[[sxx,sxy],[sxy,syy]]` 的主軸角
      `θ = ½·atan2(2·sxy, sxx−syy)` → 主軸 `(cosθ, sinθ)`(對應較大特徵值 λ1,即「資料橢圓」長軸)。
    `minor=True`(J-9):取**次主軸**(最小變異方向,`θ+90°`,對應較小特徵值 λ2,「資料橢圓」短軸),
    與主軸正交 → 波沿件群的**短軸橫掃**而非沿長軸延掃(是**另一條確定性幾何方向**,非主軸的改版)。

    **crux — 符號(方向正負)確定性**:PCA 只給一條**線**(±v 皆為合法特徵向量),J-7 正因此避開 PCA 改用
    最遠件。本函式以**幾何規則**定號,保留 J-7「波朝最外延掃」的語意:所取軸指向**沿該軸投影絕對值最大的
    極端件**(其投影 ≥ 0)。tie(投影量並列,如左右對稱)時以**座標字典序最大件**定號(純幾何 →
    **與件輸入順序無關**;不像天真規則用 index tie-break 會因排序翻號)。較 `centroid_farthest` **更穩健**:
    方向取自整體散佈軸而非單一最遠件,單一離軸離群件不會甩動主軸(見閘 PA3)。

    守衛:件重合(λ1≈0,無散佈)或**近似各向同性**(λ1−λ2 ≤ `aniso_tol`·(λ1+λ2),主/次軸皆不唯一,如正方 /
    圓對稱佈局)→ `ValueError`(不捏造方向)。近似各向同性守衛**主軸與次軸共用**(λ1≈λ2 時兩軸皆退化,
    `minor` 無從區分主/次)。純函式、確定性。"""
    n = len(centers)
    mx = sum(c[0] for c in centers) / n
    my = sum(c[1] for c in centers) / n
    sxx = sum((x - mx) ** 2 for x, y in centers) / n
    syy = sum((y - my) ** 2 for x, y in centers) / n
    sxy = sum((x - mx) * (y - my) for x, y in centers) / n
    tr = sxx + syy
    D = math.hypot(sxx - syy, 2.0 * sxy)          # = λ1 − λ2(≥0),共變異特徵值差
    lam1 = (tr + D) / 2.0
    if lam1 <= 1e-12:
        raise ValueError("derive_cascade_dir(pca): degenerate geometry (parts coincide → no spread)")
    if D <= aniso_tol * tr:
        raise ValueError(
            "derive_cascade_dir(pca): near-isotropic spread (λ1≈λ2 → principal axis undefined; "
            "anisotropy {:.3e} ≤ tol {:.3e})".format(D / tr, aniso_tol))
    theta = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    if minor:
        theta += math.pi / 2.0                     # J-9:次主軸 = 主軸轉 90°(短軸)
    ux, uy = math.cos(theta), math.sin(theta)     # 單位向量(建構即正規化)
    # 確定性符號:指向沿該軸投影 |proj| 最大的極端件(其 proj ≥ 0);tie 以座標字典序(純幾何,件序無關)。
    projs = [((x - mx) * ux + (y - my) * uy, x, y) for x, y in centers]
    maxabs = max(abs(p) for p, _, _ in projs)
    ref = max((p for p in projs if abs(p[0]) >= maxabs - 1e-9), key=lambda p: (p[1], p[2]))
    if ref[0] < 0.0:
        ux, uy = -ux, -uy
    return (ux, uy)


def _farthest_pair_dir(centers, tol=1e-9):
    """candidate (J-10) — 件中心點集的 **diameter(最遠對)**方向單位向量 `(ux, uy)`,確定性、件序無關。

    diameter = 點集中**彼此距離最大的兩件**(凸包直徑)。方向沿這條最長連線掃 = 波從一側最外肢體
    橫越到**對側最外肢體**(兩件最遠分離者)。這是**另一條確定性幾何方向**,與既有三者的幾何基礎不同:
      - `centroid_farthest`(質心→最遠件):錨在**質心**、端點是單一件;移動內部件會移動質心 → 方向改變。
      - `pca` / `pca_minor`(二階矩散佈軸):用**所有件**的共變異;移動任一內部件 → 主/次軸轉動。
      - `farthest_pair`(本函式):**只由兩個極端件決定**;移動任何**非極端(內部)件不改變方向**
        (crux 鑑別子,見閘 FP3)。

    **crux — 符號 + 件序無關**:PCA 有 ±符號歧義,本量天然定出兩個端點,以**座標字典序**(非 index)
      定向——方向由字典序**較小**端點指向**較大**端點 → 純幾何、**與件輸入順序無關**。若多對並列最遠
      (如對稱佈局),以**端點對的字典序**取唯一代表(排序後 `(lo, hi)` 最小者),同樣件序無關。

    守衛:件數 < 2(無對可量)或所有件重合(diameter≈0)→ `ValueError`(不捏造方向)。
    **注意**:`farthest_pair` **無各向同性守衛**(它非變異軸、不靠特徵值分離);只需 diameter > 0。
    純函式、確定性、O(n²)(件數少,cascade 有效件通常個位數)。"""
    n = len(centers)
    if n < 2:
        raise ValueError("derive_cascade_dir(farthest_pair): need ≥2 parts (no pair to span)")
    best_d2 = -1.0
    for i in range(n):
        xi, yi = centers[i]
        for j in range(i + 1, n):
            xj, yj = centers[j]
            d2 = (xi - xj) ** 2 + (yi - yj) ** 2
            if d2 > best_d2:
                best_d2 = d2
    if best_d2 <= 1e-18:
        raise ValueError("derive_cascade_dir(farthest_pair): degenerate geometry (parts coincide → zero diameter)")
    best_d = math.sqrt(best_d2)
    # diameter 內並列(對稱佈局)→ 以端點對的座標字典序取唯一代表(件序無關)。端點各自先排成 (lo, hi)。
    best_pair = None
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(centers[i][0] - centers[j][0], centers[i][1] - centers[j][1])
            if d >= best_d - tol:
                a = (float(centers[i][0]), float(centers[i][1]))
                b = (float(centers[j][0]), float(centers[j][1]))
                cand = (a, b) if a <= b else (b, a)
                if best_pair is None or cand < best_pair:
                    best_pair = cand
    lo, hi = best_pair
    dx, dy = hi[0] - lo[0], hi[1] - lo[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        raise ValueError("derive_cascade_dir(farthest_pair): degenerate geometry (parts coincide → zero diameter)")
    return (dx / L, dy / L)


def _convex_hull(points):
    """2D 凸包頂點(Andrew monotone chain),**CCW 順序、確定性**。純函式、O(n log n)。

    先對點集**去重 + 座標字典序排序**(→ 件輸入順序無關);叉積 `<= 0` 判準**丟棄共線邊界點**
    (只留嚴格凸轉角,與 `scipy.spatial.ConvexHull` 的頂點集同義)。回傳 hull 頂點 `list[(x,y)]`:
      - 相異點 ≥ 3 且非全共線 → 完整多邊形頂點(CCW);
      - 全共線(或恰 2 相異點)→ **2 端點**(退化線段,其唯一「邊」= diameter);
      - 單一相異點 → `[p]`(無邊,由呼叫端守衛)。"""
    pts = sorted(set((float(x), float(y)) for x, y in points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0.0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0.0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _hull_long_edge_dir(centers, tol=1e-9):
    """candidate (J-11) — 件中心**凸包最長邊**方向單位向量 `(ux, uy)`,確定性、件序無關。

    hull long edge = 凸包**相鄰兩頂點間最長的那條邊**。方向沿這條最長邊界邊掃。這是**另一條確定性
    幾何方向**,與既有四者的幾何基礎不同,**關鍵對比在 `farthest_pair`**:
      - `farthest_pair`(diameter):點集中**彼此距離最大的兩件**(最長**弦**),兩端點在凸包上但**一般不相鄰**。
      - `hull_long_edge`(本函式):凸包上**相鄰**兩頂點間最長的**邊**。最長弦 ≠ 最長邊(除退化情形)→
        **一般給出不同方向**(crux,見閘 HE3:正方 diameter=對角、hull_long_edge=邊)。
    與 `farthest_pair` 同屬**凸包邊界決定量**(只看 hull 頂點)→ **移動嚴格內部(非 hull 頂點)件不改方向**
    (vs `pca`/`centroid_farthest` 用全體點,內部件會改;HE3 共同不變性 crux),但**取不同的邊界特徵**。

    **crux — 符號 + 件序無關**:凸包由**去重後字典序排序**建(件序無關);最長邊以**端點對字典序**取唯一
      代表(多邊並列最長,如正方四邊,取排序後 `(lo, hi)` 最小者),方向由字典序**較小**端點 → **較大**端點。

    守衛:凸包頂點 < 2(所有件重合 → 無邊)或最長邊長度≈0 → `ValueError`(不捏造方向)。
    **注意**:`hull_long_edge` **無各向同性守衛**(非變異軸);全共線時凸包退化成線段,其唯一邊 = diameter
      →此退化情形 `hull_long_edge` 與 `farthest_pair` 重合(誠實邊界,見閘 HE5)。純函式、確定性。"""
    hull = _convex_hull(centers)
    if len(hull) < 2:
        raise ValueError("derive_cascade_dir(hull_long_edge): degenerate geometry (parts coincide → no hull edge)")
    m = len(hull)
    edges = [(hull[0], hull[1])] if m == 2 else [(hull[k], hull[(k + 1) % m]) for k in range(m)]
    best_len = max(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in edges)
    if best_len < 1e-9:
        raise ValueError("derive_cascade_dir(hull_long_edge): degenerate geometry (zero-length edge)")
    # 最長邊並列(對稱佈局,如正方四邊)→ 以端點對座標字典序取唯一代表(件序無關)。
    best_pair = None
    for a, b in edges:
        if math.hypot(b[0] - a[0], b[1] - a[1]) >= best_len - tol:
            lo, hi = (a, b) if a <= b else (b, a)
            if best_pair is None or (lo, hi) < best_pair:
                best_pair = (lo, hi)
    lo, hi = best_pair
    dx, dy = hi[0] - lo[0], hi[1] - lo[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        raise ValueError("derive_cascade_dir(hull_long_edge): degenerate geometry (zero-length edge)")
    return (dx / L, dy / L)


def derive_cascade_dir(centers, source="centroid_farthest"):
    """J-7:由件幾何**導出** cascade 投影方向單位向量 `(ux, uy)`,取代手感指定的具名 / 角度 / 向量。

    `source`:
      "centroid_farthest"(預設):件質心 → 距質心**最遠件**的單位向量。**確定性、無 PCA ±符號歧義**
        (PCA 主軸只給一條線、方向正負須另定;最遠件天然定出一個明確指向)。語意 = 波沿「叢集中心 →
        最外側肢體」軸掃(投影最大的最遠件最後 pop)。
      "pca"(J-8):件中心的 **PCA 主軸**(最大變異方向),**符號確定性地**定(見 `_pca_principal_axis_dir`)。
        較 `centroid_farthest` 穩健 —— 方向取自整體散佈軸而非單一最遠件,離軸離群件不甩動主軸;保留
        「波朝最外延掃」語意。近似各向同性(主軸不唯一)→ ValueError(不捏造方向)。
      "pca_minor"(J-9):件中心的 **PCA 次主軸**(最小變異方向,與主軸正交),符號同樣確定性地定。
        語意 = 波沿件群**短軸橫掃**(vs pca 沿長軸延掃)—— 是**另一條確定性幾何方向**(與 pca 正交、
        產生不同的件 pop 序),非 pca 的改版。近似各向同性(主/次軸皆不唯一)→ ValueError。
      "farthest_pair"(J-10):件中心點集的 **diameter(最遠對)**方向 —— 由**彼此距離最大的兩件**定出
        (凸包直徑),字典序定號。語意 = 波橫越「兩件最遠分離的肢體」的最長連線。**幾何基礎與前三者不同**:
        只由兩個極端件決定 → **移動內部件不改方向**(centroid_farthest 與 pca 皆會改;見 `_farthest_pair_dir`)。
        **無各向同性守衛**(非變異軸);件數<2 / 件重合(diameter≈0)→ ValueError。
      "hull_long_edge"(J-11):件中心**凸包最長邊**方向 —— 由**凸包上相鄰兩頂點間最長的那條邊**定出,
        字典序定號。語意 = 波沿件群輪廓的最長一段邊界掃。**與 farthest_pair 同屬凸包邊界決定量**(移動
        嚴格內部件不改方向)**但取不同邊界特徵**:最長**邊**(相鄰頂點)≠ 最長**弦**(diameter,一般不相鄰)
        → 一般給不同方向(見 `_hull_long_edge_dir`)。**無各向同性守衛**;頂點<2 / 件重合→ ValueError。

    `centers`:list of `(x, y)` 件中心(呼叫端給**當前 beat 的有效件**→ 方向隨實際參與件自適應)。
    回傳**正規化**單位向量。輸入守衛:未知 source、無件、退化幾何(所有件重合 → 零方向 / 各向同性)→ `ValueError`。

    crux(為何導出的是**投影向量**而非 radial):導出的方向定出一條**有向軸**,相位沿該軸投影排序 → 落在
    J-6 的 `("proj", vec)` 機制,`_cascade_phase_of` 無須任何新排序邏輯;radial(co/oc)是另一族,J-7/J-8 不碰。"""
    if source not in _CASCADE_GEO_SOURCES:
        raise ValueError("unknown cascade geo source: {!r} (allowed {})".format(
            source, sorted(_CASCADE_GEO_SOURCES)))
    n = len(centers)
    if n == 0:
        raise ValueError("derive_cascade_dir: no part centers")
    if source == "pca":
        return _pca_principal_axis_dir(centers)
    if source == "pca_minor":
        return _pca_principal_axis_dir(centers, minor=True)
    if source == "farthest_pair":
        return _farthest_pair_dir(centers)
    if source == "hull_long_edge":
        return _hull_long_edge_dir(centers)
    mx = sum(c[0] for c in centers) / n
    my = sum(c[1] for c in centers) / n
    # 最遠件:距質心平方距離最大;相等時 tie-break 用件序 index(確定性,與 _cascade_phase_of 一致)
    best_i, best_d2 = 0, -1.0
    for i, (x, y) in enumerate(centers):
        d2 = (x - mx) ** 2 + (y - my) ** 2
        if d2 > best_d2:
            best_d2, best_i = d2, i
    dx, dy = centers[best_i][0] - mx, centers[best_i][1] - my
    L = math.hypot(dx, dy)
    if L < 1e-9:
        raise ValueError("derive_cascade_dir: degenerate geometry (parts coincide → zero direction)")
    return (dx / L, dy / L)


def _normalize_cascade_dir(cascade_dir):
    """把方向規格正規化為 `(kind, payload)`,供 `_cascade_phase_of` 統一取排序鍵。

    - `None` / `"po"`           → `("po", None)`     件序(byte-identical)
    - `"lr"`                     → `("proj", (1.0, 0.0))`   基數軸特例(投影,`k=x`)
    - `"rl"`                     → `("proj", (-1.0, 0.0))`  基數軸特例(投影,`k=−x`)
    - `"co"` / `"oc"`           → `("co"/"oc", None)`  radial(非投影)
    - 數字(角度,度)            → `("proj", (cosθ, sinθ))`  投影到任意角
    - 2-元素序列 `(ux, uy)`      → `("proj", 正規化單位向量)`  投影到任意向量
    - 其餘字串 / 型別 / 零向量    → `ValueError`(輸入守衛)

    crux:`"lr"`/`"rl"` 經投影路徑算出的 `k` 分別為 `x·1+y·0=x`、`x·(−1)+y·0=−x`,與 J-5 直接取 `k=±x`
    **逐位元相等**(排序→rank→相位值皆同)→ J-6 對 J-5 既有具名方向零回歸。"""
    if cascade_dir is None or cascade_dir == "po":
        return ("po", None)
    # bool 是 int 子類,排除以免 True/False 被誤當角度
    if isinstance(cascade_dir, bool):
        raise ValueError("cascade_dir may not be bool: {!r}".format(cascade_dir))
    # J-7:geo sentinel —— 方向向量由幾何導出,此處只確認 source、回 marker,實際向量留到
    # `_cascade_phase_of` 用當前 beat 的件中心算(須先置於下方通用 length-2 tuple 向量分支前,
    # 否則 ("geo", src) 會被誤當 (ux,uy) 向量而 float("geo") 爆 ValueError)。
    if cascade_dir == "geo":
        return ("geo", _CASCADE_GEO_DEFAULT)
    if isinstance(cascade_dir, (tuple, list)) and len(cascade_dir) == 2 and cascade_dir[0] == "geo":
        src = cascade_dir[1]
        if src not in _CASCADE_GEO_SOURCES:
            raise ValueError("unknown cascade geo source: {!r} (allowed {})".format(
                src, sorted(_CASCADE_GEO_SOURCES)))
        return ("geo", src)
    if isinstance(cascade_dir, (int, float)):
        th = math.radians(float(cascade_dir))
        return ("proj", (math.cos(th), math.sin(th)))
    if isinstance(cascade_dir, (tuple, list)):
        if len(cascade_dir) != 2:
            raise ValueError("cascade_dir vector must have length 2: {!r}".format(cascade_dir))
        ux, uy = float(cascade_dir[0]), float(cascade_dir[1])
        n = math.hypot(ux, uy)
        if n < 1e-12:
            raise ValueError("cascade_dir vector is (near-)zero: {!r}".format(cascade_dir))
        return ("proj", (ux / n, uy / n))
    if cascade_dir == "lr":
        return ("proj", (1.0, 0.0))
    if cascade_dir == "rl":
        return ("proj", (-1.0, 0.0))
    if cascade_dir in ("co", "oc"):
        return (cascade_dir, None)
    raise ValueError("unknown cascade_dir: {!r} (allowed {} | angle-deg number | (ux,uy) vector)".format(
        cascade_dir, sorted(_CASCADE_DIRS)))


def _cascade_phase_of(valid, bone_of, cx, cy, cascade_dir):
    """回傳每個 valid 件的相位 ∈[0,1](list,index 對齊 valid)。

    `cascade_dir is None` → 件序 `pi/(nvalid−1)`(第一件 0、最後一件 1 → 逐位元同 J-4 之前行為)。
    否則依**空間排序鍵**給 rank,相位 = `rank/(nvalid−1)`。排序鍵 tie-break 用件序 index(確定性)。
    J-6:排序鍵由 `cascade_dir` 決定 —— 投影(任意角/向量,含 lr/rl 基數軸特例)或 radial(co/oc)。"""
    nvalid = len(valid)
    if nvalid <= 1:
        return [0.0] * nvalid
    kind, vec = _normalize_cascade_dir(cascade_dir)
    if kind == "po":
        return [i / (nvalid - 1) for i in range(nvalid)]
    if kind == "geo":
        # J-7:由**當前 beat 的有效件中心**導出投影向量(方向隨實際參與件自適應),再走 J-6 投影排序。
        # `vec` 此處承載 source 字串(見 _normalize_cascade_dir 的 geo marker)。
        centers = []
        for pe in valid:
            bd = bone_of.get(safe(pe["part"])) or {}
            centers.append((bd.get("x", cx), bd.get("y", cy)))
        vec = derive_cascade_dir(centers, source=vec)
        kind = "proj"
    keys = []
    for i, pe in enumerate(valid):
        bd = bone_of.get(safe(pe["part"])) or {}
        x, y = bd.get("x", cx), bd.get("y", cy)
        if kind == "proj":
            k = x * vec[0] + y * vec[1]            # 投影到單位向量(lr/rl/任意角/向量)
        elif kind == "co":
            k = math.hypot(x - cx, y - cy)         # radial 中心外擴(非投影)
        else:  # "oc"
            k = -math.hypot(x - cx, y - cy)
        keys.append((k, i))                       # (空間鍵, 件序) → tie-break 用件序,確定性
    order = sorted(range(nvalid), key=lambda i: keys[i])
    rank = [0] * nvalid
    for r, i in enumerate(order):
        rank[i] = r
    return [rank[i] / (nvalid - 1) for i in range(nvalid)]


def _build_beat(beat, cat, bone_of, cx, cy, count=None, twist_vol=False, cascade_span=None, cascade_dir=None):
    """把單一 beat 的每件 role 具體化為 anim dict(bones/slots timelines)。

    cat 依語意分派運動基元;`count`(J-2 combo 峰數 / G-4''' wobble 振盪段數 / G-4'''''-c squash 擠壓段數 /
    G-4''''''-count twist 扭轉段數 / J-3 cascade 跨件波掃次數 nrip)只對 COUNT_AWARE / _PHASE_AWARE 類別生效。
    `count is None` → 呼叫生成器**自身預設**(combo=3 峰、wobble/squash/twist=4 段、cascade=1 道波 → golden
    byte-identical);給定值 → 帶入生成器決定段數 / 波掃次數。
    `twist_vol`(G-4''''''-vol):True 時只對 twist 掛體積守恆等向補償 scale(shear+scale+rotate 三通道同時且守恆)。
    `cascade_span`(J-4):只對 cascade(_PHASE_AWARE)生效 = 一道 sweep 內各件峰時刻的**散佈幅度**;None → 生成器
    預設 CASCADE_SPAN(0.54,byte-identical)。與 nrip **正交**(nrip 幾道波、span 一道多開),皆於 gen 當下重生成。
    `cascade_dir`(J-5 / J-6):只對 cascade(_PHASE_AWARE)生效 = 跨件波的**相位來源**;None → 件序(byte-identical);
    "lr"/"rl"/"co"/"oc"(J-5)→ 相位由**空間位置**決定(波方向變成幾何);**角度(度)或向量 (ux,uy)**(J-6)→
    相位由件中心在該方向的**投影**排序(lr/rl 為 θ=0°/180° 投影特例)。與 count/span/深度三軸正交(只重排哪件何時 pop)。
    cascade(_PHASE_AWARE)另依相位來源帶入相位。"""
    bones_tl, slots_tl = {}, {}
    limb_seen = 0
    # 跨件時序類別(cascade)需先知道**有效件**總數以配相位;先過濾出真正有 bone 的件。
    valid = [pe for pe in beat["parts"] if bone_of.get(safe(pe["part"])) is not None]
    nvalid = len(valid)
    # J-5:相位來源(件序 or 空間)。非 cascade 類別不讀此表(其 phase 分支根本不走到)。
    phase_of = _cascade_phase_of(valid, bone_of, cx, cy, cascade_dir) if cat in _PHASE_AWARE else None
    for pi, pe in enumerate(valid):
        part = pe["part"]; role = pe["role"]
        sname = safe(part)
        bname = "b_" + sname
        bd = bone_of.get(sname)
        # 左右反相:依遇到 limb 的順序交替 ±1(確定性)
        side_sign = 1.0
        if role == "limb":
            side_sign = 1.0 if limb_seen % 2 == 0 else -1.0
            limb_seen += 1
        # 徑向外側單位向量(件中心相對畫布中心)
        dx, dy = bd.get("x", cx) - cx, bd.get("y", cy) - cy
        n = math.hypot(dx, dy) or 1.0
        radial = (dx / n, dy / n)

        if cat in _PHASE_AWARE:
            # 相位來源:預設件序(第一件 0、最後一件 1);J-5 可改由空間位置(lr/rl/co/oc)決定波方向。
            # candidate J-3:cascade 另吃 `count`=nrip(跨件波掃過整體的次數,檔位相依)。
            # candidate J-4:cascade 另吃 `cascade_span`=一道 sweep 內各件峰時刻的散佈幅度(檔位相依)。
            # 兩者皆 None → 生成器自身預設(nrip=1、span=CASCADE_SPAN → golden 單 sweep byte-identical)。
            phase = phase_of[pi]
            if count is None and cascade_span is None:
                b, sdict = _DISPATCH[cat](role, side_sign, radial, phase)
            else:
                nrip = 1 if count is None else count      # span-only 變體 → nrip 回預設 1(單道波,散佈可變)
                b, sdict = _DISPATCH[cat](role, side_sign, radial, phase, nrip, cascade_span)
        elif cat in _COUNT_AWARE_CATS:
            # 段數(檔位相依):combo 峰數 / wobble 振盪段數。count is None → 生成器自身預設(golden)。
            # G-4''''''-vol:twist 專屬 vol_conserve(等向補償 scale → 體積守恆);其餘類別不吃此 kwarg。
            kw = {"vol_conserve": True} if (cat == "twist" and twist_vol) else {}
            if count is None:
                b, sdict = _DISPATCH[cat](role, side_sign, radial, **kw)
            else:
                b, sdict = _DISPATCH[cat](role, side_sign, radial, count, **kw)
        else:
            b, sdict = _DISPATCH[cat](role, side_sign, radial)
        if b:
            bones_tl[bname] = b
        if sdict:
            slots_tl[sname] = sdict
    anim = {}
    if bones_tl:
        anim["bones"] = bones_tl
    if slots_tl:
        anim["slots"] = slots_tl
    return anim


def build_animations(skeleton, storyboard, tier_gains=None, tier_combo_hits=None,
                     tier_wobble_cycles=None, tier_squash_cycles=None, tier_twist_cycles=None,
                     tier_charge_cycles=None, tier_cascade_ripples=None, tier_cascade_span=None,
                     twist_volume=False, cascade_dir=None):
    """回傳 animations dict(beat 名為 key)。

    tier_gains(candidate J):`{tier: gain}` 時,對**主秀** beat(cat∈MAIN_SHOW_CATS)
    額外產出 `{beat}__{tier}` 幅度差異化變體(檔位愈高愈爆);base beat 不變。
    tier_combo_hits(J-2):`{tier: nhits}` 時,對 combo 檔位變體以該檔位 nhits **重生成**(連擊數隨檔位遞增)。
    tier_wobble_cycles(G-4'''):`{tier: nosc}` 時,對 wobble 檔位變體以該檔位 nosc **重生成**(振盪段數隨檔位遞增)。
    tier_squash_cycles(G-4'''''-c):`{tier: nosc}` 時,對 squash 檔位變體以該檔位 nosc **重生成**(擠壓段數隨檔位遞增);
    因 squash∈COUPLED_SCALE_CATS,重生成後仍走**耦合** amplify → 段數×幅度×體積守恆三效正交可疊(每檔位每擠壓極值 scaleX·scaleY≡1)。
    tier_twist_cycles(G-4''''''-count):`{tier: nosc}` 時,對 twist 檔位變體以該檔位 nosc **重生成**(扭轉段數隨檔位遞增);
    twist∈SHEAR_CATS(兩條 shear 軸,非 COUPLED_SCALE_CATS),重生成後每個新極值仍 shearY=−TWIST_PHI·shearX(φ 由建構保證),
    再走單一-g 幅度增益(兩軸同比)→ 段數×幅度×φ 保形三效正交可疊(每檔位不論扭幾段,φ 恆定、反相不變)。
    tier_charge_cycles(G-4'''''-charge):`{tier: ncharge}` 時,對 charge 檔位變體以該檔位 ncharge **重生成**
    (蓄力充能階段數隨檔位遞增);charge∈COUNT_AWARE_CATS(純 scale,非 SHEAR/COUPLED),重生成後走逐軸 amplify。
    每階一段持續 hold(sustained run <0.97)+ 遞增 release → 與 combo 的「短 dip N 峰」鑑別(見 validate_charge_count.py)。
    段數(結構)先重生成、再套幅度增益 g —— 幅度與段數兩效**正交可疊**(各類別段數階梯獨立)。
    twist_volume(G-4''''''-vol / -vol-tier):True → twist 掛體積守恆等向補償 scale(擰而不變面積,
    shear+scale+rotate 三通道同時且 det≡1);False(預設)→ twist 逐位元同 shear-only(向後相容)。
    **base 與 tier 變體皆作用**(G-4''''''-vol-tier):tier 放大把兩軸 shear 同比拉大 → 補償 scale 依**放大後**
    的 shear **非線性重算** `s=1/√cos(g·Δ)`(`amplify_anim(twist_vol=True)`)→ det≡1 於任一檔位保持
    (crux:逐軸線性 `_amp_scale` 追不上非線性 cos 曲線 → 破守恆;比照 squash 的耦合 amplify,但 twist 走等向、
    值來自 shear 重算而非倒數耦合)。段數(tier_twist_cycles)重生成的變體亦掛 vol → 段數×幅度×守恆三效正交可疊。
    tier_cascade_ripples(J-3):`{tier: nrip}` 時,對 cascade 檔位變體以該檔位 nrip **重生成**(跨件波掃過整體的次數隨檔位遞增);
    cascade∈_PHASE_AWARE(非 COUNT_AWARE_CATS/單件段數)——nrip 是**跨件時序**通道的段數(整體 ripple 幾道),
    每件 pop nrip 次、每道 sweep 內各件峰時刻仍依件序遞增(跨件排序在每道波皆保住)。事後幅度 amplify 加不出第二道
    sweep(拓樸=gen 時決定的窗)→ 以該檔位 nrip 重生成再套單一-g 幅度增益(波掃道數×幅度兩效正交可疊)。
    tier_cascade_span(J-4):`{tier: span}` 時,對 cascade 檔位變體以該檔位 span **重生成**(一道 sweep 內各件峰時刻的
    **散佈幅度**隨檔位遞增,愈高檔位波掃愈開)。**crux**:span 語意屬「幅度」但因散佈活在關鍵幀**時間位置**(峰中心)非**值**,
    post-hoc 值增益 g 加不出來(g 只放大 pop 深度、峰時刻不動)→ 須重生成,與 nrip **正交**(nrip 幾道波、span 一道多開,
    兩軸皆重生成、可同時帶入 → nrip 道各以該檔位 span 散佈),再套單一-g 幅度增益(三效正交可疊)。
    cascade_dir(J-5 / J-6):cascade 跨件波的**相位來源**。None(預設)= 件序(byte-identical);"lr"/"rl"/"co"/"oc"(J-5)=
    由**空間位置**決定波方向(最左/最右/中心/最外件先 pop);**角度(度)或向量 (ux,uy)**(J-6)= 相位依件中心在該方向的
    **投影**排序(方向軸由 J-5 的 4 向離散補成連續;lr/rl 為 θ=0°/180° 投影特例,逐位元相容)。只重排「哪件何時 pop」,
    不動波形 → 與 count/span/深度正交,對所有 cascade clip(base 與檔位變體)一致套用;非 cascade 類別不受影響。

    皆 None/False(預設)→ 逐位元同舊行為(向後相容;base combo 恆 3 峰、base wobble/squash/twist 恆 4 段、base charge 恆 1 階、base cascade 恆 1 道波 span=0.54 相位件序、twist 無 scale)。"""
    # COUNT_AWARE(單件段數)+ cascade(跨件波掃次數,_PHASE_AWARE)→ 對應的 {tier: count} 映射
    # (依 cat 路由;None → 該類別 count 不隨檔位變)。cascade 的 count 語意=nrip(波掃道數),非單件段數。
    _count_maps = {"combo": tier_combo_hits, "wobble": tier_wobble_cycles,
                   "squash": tier_squash_cycles, "twist": tier_twist_cycles,
                   "charge": tier_charge_cycles, "cascade": tier_cascade_ripples}
    # J-4:cascade 跨件散佈幅度 {tier: span}(僅 cascade;_PHASE_AWARE,與 nrip 正交,可同時重生成)。
    _span_map = tier_cascade_span
    # 件名 → bone/slot / setup 位置
    bone_of = {b["name"].removeprefix("b_"): b for b in skeleton["bones"] if b["name"] != "root"}
    # 畫布中心(用於徑向)
    W = skeleton["skeleton"]["width"]
    H = skeleton["skeleton"]["height"]
    cx, cy = W / 2.0, H / 2.0

    anims = {}
    for beat in storyboard["beats"]:
        name = beat["beat"]
        cat = beat_category(name)
        anim = _build_beat(beat, cat, bone_of, cx, cy, twist_vol=twist_volume, cascade_dir=cascade_dir)
        anims[name] = anim
        # candidate J:主秀 beat 依檔位增益產幅度差異化變體(In/Loop/Out 檔位無關,不產)
        if tier_gains and cat in _MAIN_SHOW_CATS:
            # count 路由涵蓋單件段數(_COUNT_AWARE_CATS)與 cascade 跨件波掃次數(_PHASE_AWARE)。
            # 直接查 _count_maps:未列或對應 tier_*=None 的類別回 None(→ 不隨檔位重生成,向後相容)。
            cmap = _count_maps.get(cat)
            # (G-4''''')squash 等耦合 scale 類別 → amplify 走體積守恆耦合(scaleX·scaleY≡1);其餘逐軸。
            coupled = cat in _COUPLED_SCALE_CATS
            # (G-4''''''-vol-tier)twist 掛體積守恆 scale 時 → amplify 依放大後 shear **重算**等向補償 scale
            # (det≡1;s 對 g 非線性,見 tier_variants._recompute_twist_scale_iso)。twist_volume=False 時
            # twist 純 shear、tv=False → 走一般 shear 放大(向後相容)。
            tv = twist_volume and (cat in _VOL_TWIST_CATS)
            # J-4:cascade 跨件散佈幅度隨檔位(僅 cascade;None → 不隨檔位變,向後相容)。
            spmap = _span_map if (_span_map and cat == "cascade") else None
            for tier, g in tier_gains.items():
                cnt = cmap.get(tier) if cmap else None
                csp = spmap.get(tier) if spmap else None
                if cnt is not None or csp is not None:
                    # J-2/G-4''':段數隨檔位遞增 → 以該檔位段數重生成 beat,再套幅度增益 g(正交可疊)。
                    # J-3/J-4:cascade 以該檔位 nrip(波掃道數)/ span(跨件散佈)重生成(兩軸皆重生成、正交可疊)。
                    # twist 另帶 twist_vol → 重生成的變體也掛體積守恆 scale(段數×幅度×守恆三效正交)。
                    variant = _build_beat(beat, cat, bone_of, cx, cy, count=cnt,
                                          twist_vol=twist_volume, cascade_span=csp, cascade_dir=cascade_dir)
                    anims["{}__{}".format(name, tier)] = _amplify_anim(variant, g, coupled=coupled, twist_vol=tv)
                else:
                    anims["{}__{}".format(name, tier)] = _amplify_anim(anim, g, coupled=coupled, twist_vol=tv)
    return anims


def _clip_duration(clip):
    """單一 beat clip 的時長 = 所有 timeline 最後一幀時間的最大值(同 spine_anim.duration)。"""
    d = 0.0
    for chans in clip.get("bones", {}).values():
        for tl in chans.values():
            if tl:
                d = max(d, tl[-1]["time"])
    for chans in clip.get("slots", {}).values():
        for tl in chans.values():
            if tl:
                d = max(d, tl[-1]["time"])
    return d


def _shift_frames(frames, dt):
    """把一條 timeline 的每一幀時間平移 dt(值不動;確定性,round 到 6 位對齊既有產檔精度)。"""
    out = []
    for f in frames:
        g = dict(f)
        g["time"] = round(g.get("time", 0.0) + dt, 6)
        out.append(g)
    return out


def compose_sequence(anims, order, gap=0.0, merge_tol=1e-6):
    """candidate (L) — 把多個 beat clip 依 `order` 串接成**單一**可載入 animation(確定性,純時間平移)。

    `build_animations` 產出的是**各自獨立**的 beat clip(In/Loop/Out + 主秀 beat + `{beat}__{tier}`),
    每支 timeline 時間都由 0 起;遊戲端靠「各 beat 首尾皆 setup identity」在 runtime 依序播放達成無縫。
    本函式把這個**跨 beat 串接**顯式做出來:第 i 個 beat 的所有關鍵幀時間平移
    `offset_i = Σ_{j<i}(dur_j + gap)`,合併成一支連續 timeline,得到一段真正可播放的大獎序列
    (In → 主秀節拍… → Loop → Out)。

    介面契約(genre_priors):hit/combo/charge/cascade/wobble/squash/twist/Loop 首尾皆 setup identity,
    In 為 collapsed→identity、burst 為 collapsed→identity、Out 為 identity→collapsed。故**相鄰 beat 在接點**
    (前一 beat 尾幀 == 後一 beat 首幀)值相等時為 **C0 無縫**;此時接點時間重合,本函式**去重**接點幀
    (保留前者)以維持 Spine「同通道時間嚴格遞增」要求 —— 對無縫序列為**無損**(值相等)。
    接點**不相等**(如把 burst 放序列中段:identity→collapsed)則為真不連續,應由上游排序避免;本函式不做
    值檢查(排序正確性由 `validate_sequence_compose` 的接點殘差閘把關),純做時間平移與重合去重。

    純平移 + 接點去重 **不改任何 beat 的值** → 回切任一段(時間減去該段 offset)逐幀還原原 clip
    (見閘 L3 faithfulness)。`gap>0` 時接點間留空窗(不去重),用於顯式製造不連續的負對照。

    回傳 `(composed, segments)`:
      composed = {"bones":{...},"slots":{...}} 可直接塞進 skeleton["animations"][序列名]。
      segments = [{"beat":name,"start":offset,"dur":dur}, ...] 供回切各段做 in-context 量測。
    """
    composed = {"bones": {}, "slots": {}}
    segments = []
    offset = 0.0
    for name in order:
        if name not in anims:
            raise KeyError("compose_sequence: beat '{}' 不在 anims(可用:{})".format(
                name, sorted(anims.keys())))
        clip = anims[name]
        dur = _clip_duration(clip)
        for group in ("bones", "slots"):
            for part, chans in clip.get(group, {}).items():
                dst = composed[group].setdefault(part, {})
                for ch, frames in chans.items():
                    sh = _shift_frames(frames, offset)
                    cur = dst.setdefault(ch, [])
                    # 接點時間重合 → 去重:**丟前者尾幀、保留後者首幀**。兩幀值相等(無縫序列),但
                    # 後者首幀帶的是**往下一幀的緩動 curve**(Spine 緩動掛在「起點幀」),是進入後段
                    # 該有的曲線;若反而留前者尾幀,其 curve 屬前段、會讓後段首段內插用錯緩動 → 非無損。
                    # 前段尾幀的 outgoing curve 無意義(clip 之末,無後續內插),故丟之無損。
                    if cur and sh and gap == 0.0 and abs(cur[-1]["time"] - sh[0]["time"]) <= merge_tol:
                        cur.pop()
                    cur.extend(sh)
        segments.append({"beat": name, "start": round(offset, 6), "dur": round(dur, 6)})
        offset += dur + gap
    for group in ("bones", "slots"):
        if not composed[group]:
            composed.pop(group)
    return composed, segments


_LOOP_IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0,
               "shearX": 0.0, "shearY": 0.0}


def _state_max_diff(s1, s2):
    """兩個 `spine_anim.sample()` 狀態的跨 bone/slot 最大絕對差(缺席通道視為 setup identity;含 shear)。"""
    m = 0.0
    for b in set(s1["bones"]) | set(s2["bones"]):
        d1 = s1["bones"].get(b, _LOOP_IDENT)
        d2 = s2["bones"].get(b, _LOOP_IDENT)
        for k in _LOOP_IDENT:
            m = max(m, abs(d1.get(k, _LOOP_IDENT[k]) - d2.get(k, _LOOP_IDENT[k])))
    for s in set(s1["slots"]) | set(s2["slots"]):
        a1 = s1["slots"].get(s, {"alpha": 1.0})["alpha"]
        a2 = s2["slots"].get(s, {"alpha": 1.0})["alpha"]
        m = max(m, abs(a1 - a2))
    return m


def is_loopable(clip, tol=1e-6):
    """candidate (L-3) — 判斷一支 beat clip 是否可**安全重複/平鋪**(loopable)。

    一支 clip 若「首幀狀態 == 尾幀狀態」(所有通道 C0 相等,含 shear),把它接在自己後面(重複 N 次)時
    **自接點**(前一份的尾 → 後一份的首)值連續、無 C0「跳變 / pop」—— 這正是遊戲 idle / Loop 動畫可
    無限重播的前提。`compose_sequence` 的 `order` 本就可重複同一 beat 名(如 `In→Loop×N→Out`)把「Loop
    重播」顯式串出,但**唯有 loopable 的 beat 重複才無縫**;本判準把這個不變量顯式化(供閘與產線判斷)。

    介面契約下:Loop / 主秀 beat(hit/combo/wobble…)首尾皆 setup identity → loopable;
    In(collapsed→identity)、Out(identity→collapsed)首≠尾 → **非** loopable(重複會在自接點 pop)。
    注意:loopable 只保證 **C0**(值連續、不跳變);它**不**保證「有運動」或「速度連續(C1)」——
    一支恆 identity 的靜止 clip 也 loopable 但平鋪後毫無意義(見閘 LP4 的非靜止+週期驗證)。
    回傳 bool。純判斷、不改任何值(additive;不依賴任何既有索引)。
    """
    import spine_anim as _SA
    dur = _SA.duration(clip)
    if dur <= 0:
        return True  # 空 / 無時間跨度的 clip 平鋪退化為恆值,自接點天然連續
    start = _SA.sample(clip, 0.0)
    end = _SA.sample(clip, dur)
    return _state_max_diff(start, end) <= tol


def _state_velocity(clip, at_start, h):
    """單側有限差分的「狀態速度」(每通道 d(值)/dt),在 clip 端點取。
    at_start=True → `(sample(h)-sample(0))/h`(進入 t=0⁺ 的外向速度);
    at_start=False → `(sample(dur)-sample(dur-h))/h`(逼近 t=dur⁻ 的內向速度)。
    回傳與 `sample()` 同形狀的 state,但每個數值欄位是**速度**(scale/alpha 的 setup 基準在相減時抵消,
    故此處所有欄位基準皆取 0 —— 單純對 `sample()` 兩次取值相減再除 h,與基準無關)。純函式、不改值。"""
    import spine_anim as _SA
    dur = _SA.duration(clip)
    t0, t1 = (0.0, h) if at_start else (dur - h, dur)
    s0, s1 = _SA.sample(clip, t0), _SA.sample(clip, t1)
    vb = {}
    for b in set(s0["bones"]) | set(s1["bones"]):
        d0 = s0["bones"].get(b, _LOOP_IDENT)
        d1 = s1["bones"].get(b, _LOOP_IDENT)
        vb[b] = {k: (d1.get(k, _LOOP_IDENT[k]) - d0.get(k, _LOOP_IDENT[k])) / h for k in _LOOP_IDENT}
    vs = {}
    for s in set(s0["slots"]) | set(s1["slots"]):
        a0 = s0["slots"].get(s, {"alpha": 1.0})["alpha"]
        a1 = s1["slots"].get(s, {"alpha": 1.0})["alpha"]
        vs[s] = {"alpha": (a1 - a0) / h}
    return {"bones": vb, "slots": vs}


def seam_velocity_gap(clip_before, clip_after, h=1e-3):
    """candidate (L-5) — 兩支 beat clip 在**相異接點**(前 beat 尾 → 後 beat 首)的 **C1(速度)不連續量**。

    一般化 (L-4) 的 `loop_seam_velocity_gap`:後者是本函式 `clip_before is clip_after`(自接點)的特例。
    回傳 `max |v_end(clip_before) − v_start(clip_after)|`(跨所有 bone 通道 rotate/x/y/scale/shear + 每個
    slot 的 alpha,單側有限差分;單位同 `_state_max_diff` 混合單位每秒):前一 beat 逼近 `t=dur⁻` 的內向速度
    與後一 beat 進入 `t=0⁺` 的外向速度之差。

    `compose_sequence` 的 **C0 無縫**(`validate_sequence_compose` L2 的接點殘差閘)只保證接點**值連續**,
    即 `state_end(before) == state_start(after)`;即使如此,若兩 beat 在接點的**切線速度不同**,串接後
    在接點仍有**速度突變(velocity kink)**。本函式把這個序列**全程 C1**(相異接點版)的不變量顯式量化,
    是 (L-4) 自接點 C1 的互補:L-4 驗「同一支 clip 重播 N 次」的自接點,本函式驗「相異 beat 接起來」的接點。

    ⚠️ **必須在 clip 端點層量,不能從 composed 時間軸量**(同 L-4):`compose_sequence` 的接點去重使 composed
    取樣的接點速度是 sampling/dedup 相依的 artifact(見閘 S2:對部分接點 composed 會**低報**真 kick);真 C1
    判準只在孤立 clip 的端點切線(本函式所做)。對分段線性 / 端點附近近線性 timeline,單側差分即端點切線,
    對 h 穩定(見閘 S2)。純函式、additive、不依賴任何既有索引。"""
    ve = _state_velocity(clip_before, False, h)   # 前 beat 逼近 t=dur⁻ 的內向速度
    vs = _state_velocity(clip_after, True, h)      # 後 beat 進入 t=0⁺ 的外向速度
    m = 0.0
    for b in set(vs["bones"]) | set(ve["bones"]):
        d0 = ve["bones"].get(b, {k: 0.0 for k in _LOOP_IDENT})
        d1 = vs["bones"].get(b, {k: 0.0 for k in _LOOP_IDENT})
        for k in _LOOP_IDENT:
            m = max(m, abs(d0.get(k, 0.0) - d1.get(k, 0.0)))
    for s in set(vs["slots"]) | set(ve["slots"]):
        a0 = ve["slots"].get(s, {"alpha": 0.0})["alpha"]
        a1 = vs["slots"].get(s, {"alpha": 0.0})["alpha"]
        m = max(m, abs(a0 - a1))
    return m


def loop_seam_velocity_gap(clip, h=1e-3):
    """candidate (L-4) — 一支 loopable clip 在**自接點**(重複/平鋪時 前份尾→後份首)的 **C1(速度)不連續量**。

    `is_loopable`(L-3)只保證自接點 **C0**(值連續、不跳變);但把一支 clip 平鋪重播時,即使端點值相等,
    若**進入 t=0⁺ 的外向速度 ≠ 逼近 t=dur⁻ 的內向速度**,自接點就有**速度突變(velocity kink / 頓挫)**——
    這正是 L-3 誠實列為未驗的 honest boundary(「loop 重啟頓挫」)。本函式把這個 C1 不變量**顯式量化**:
    回傳 `max |v_end − v_start|`(跨所有 bone 通道 rotate/x/y/scale/shear + 每個 slot 的 alpha,
    單側有限差分),單位為「state-diff 每秒」(沿用 `_state_max_diff` 的混合單位慣例,只是多除一個時間)。

    ⚠️ **必須在 clip 端點層量,不能從 composed 時間軸量**:L-3 已發現 `compose_sequence` 的時間去重會把
    接點抹成陡坡,composed 取樣恆 C0 → 跨 composed 接點的速度是**量測 artifact**;真 C1 判準只在孤立 clip
    的端點切線(本函式所做)。對分段線性 / 端點附近近線性的 timeline,單側差分即端點切線,對 h 穩定(見閘 C1b)。
    純函式、additive、不依賴任何既有索引。自 (L-5) 起委派 `seam_velocity_gap(clip, clip, h)`(自接點 =
    `clip_before is clip_after` 的特例;逐位元等價,零回歸)。"""
    return seam_velocity_gap(clip, clip, h)


def is_c1_loopable(clip, tol=1e-6, vel_tol=1.0, h=1e-3):
    """candidate (L-4) — 一支 clip 是否可**無頓挫地**重複/平鋪(C1-loopable)。

    `= is_loopable(clip, tol)` (自接點 C0 值連續) **AND** `loop_seam_velocity_gap(clip, h) <= vel_tol`
    (自接點 C1 速度連續)。C1-loopable ⇒ C0-loopable(嚴格更強)。

    **為何需要**(crux,見閘 C1d):真實產線的一次性主秀 beat(hit/combo/charge/cascade)首尾皆 setup
    identity → `is_loopable`(C0)**一律 True**,看似「可安全重播」;但它們是單發節拍,自接點速度突變達數十~上百
    deg/s(符號翻轉)→ 平鋪會每份頓挫一次。唯有 **C1** 能把真正的 idle-**Loop**(速度亦連續)與這些一次性 beat
    區分開。`vel_tol` 預設 1.0(真實 Loop 自接點 gap 實測 ≈0.19,來自光暈呼吸式 scale/alpha 的小殘差 kink;
    主秀 beat ≥64)。純函式、additive。"""
    return is_loopable(clip, tol) and loop_seam_velocity_gap(clip, h) <= vel_tol


def sequence_seam_gaps(anims, order, h=1e-3):
    """candidate (L-5) — 一條播放序列 `order` 的**每個相鄰接點**的 C0(值)與 C1(速度)不連續量。

    對 `order` 裡每一對相鄰 beat `(order[i], order[i+1])` 量:
      - `c0_gap` = `_state_max_diff(sample(before, dur_before), sample(after, 0))`(接點值不連續;L 的 C0 判準)。
      - `c1_gap` = `seam_velocity_gap(before, after, h)`(接點速度不連續;本 candidate 的 C1 判準)。
    相鄰同名(如 `Loop, Loop`)自然退化為**自接點**(`seam_velocity_gap(X, X)` = L-4 的 `loop_seam_velocity_gap`)。

    回傳 `[{"i":i,"seam":"A->B","c0_gap":..,"c1_gap":..}, ...]`(長度 = `len(order)-1`)。這是序列**全程**
    連續性的逐接點報告:C0 全 ≤ tol ⇒ 可無跳變串接播放(L);但 C1 未必 ⇒ 接點仍可能頓挫(本 candidate)。
    純函式、additive、不依賴任何既有索引、不改任何值。"""
    import spine_anim as _SA
    out = []
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        if a not in anims:
            raise KeyError("sequence_seam_gaps: beat '{}' 不在 anims".format(a))
        if b not in anims:
            raise KeyError("sequence_seam_gaps: beat '{}' 不在 anims".format(b))
        ca, cb = anims[a], anims[b]
        da = _SA.duration(ca)
        c0 = _state_max_diff(_SA.sample(ca, da), _SA.sample(cb, 0.0))
        c1 = seam_velocity_gap(ca, cb, h)
        out.append({"i": i, "seam": "{}->{}".format(a, b), "c0_gap": c0, "c1_gap": c1})
    return out


def is_c1_continuous_sequence(anims, order, tol=1e-6, vel_tol=1.0, h=1e-3):
    """candidate (L-5) — 一條序列 `order` 串接後是否**全程 C1 連續**(每個接點值且速度皆連續)。

    `= 每個相鄰接點 c0_gap ≤ tol`(C0 無縫,L)**AND** `c1_gap ≤ vel_tol`(C1 無頓挫,本 candidate)。
    C1-continuous ⇒ C0-continuous(嚴格更強)。

    **與 `is_c1_loopable`(L-4)互補且獨立**:L-4 驗**自接點**(同一 Loop 重播 N 次是否無縫無頓挫);本函式驗
    **相異接點**(不同 beat 串成序列是否無縫無頓挫)。兩者互不蘊含 —— 一支 Loop 可以**自接點 C1**(可安全重播)
    卻在**與鄰 beat 的接點 C1 失敗**(Loop 端點正在擺動、鄰 beat 卻近靜止 → 接點速度突變),見閘 S4。
    純函式、additive。"""
    for g in sequence_seam_gaps(anims, order, h):
        if g["c0_gap"] > tol or g["c1_gap"] > vel_tol:
            return False
    return True


# ===================== candidate (L-6):跨 beat crossfade / mix 序列組合 =====================
#
# 動機(承 L-5):`compose_sequence`(L)只做**純時間平移 + 接點去重**,相鄰 beat 在接點**瞬間**切換
# (前 beat 尾 → 後 beat 首)。L-5 證實正向大獎序列每個相異接點雖 **C0 無縫**(值連續、可串接播放),
# 卻 **C1 不連續**(接點速度突變 15~114):各 beat 是離散節拍,端點切線互不相同。純平移去重**做不到**
# 平滑接點 —— 需真正的 **mix 機制**:讓相鄰 beat 在接點**時間重疊** `xf` 秒,重疊區以權重斜坡 `w(s)`
# (s∈[0,1])混合兩 beat 的姿勢。本段把這個組合層機制顯式做出來(STATE/L-5「下一步」的 crossfade 軸)。
#
# 關鍵不變量(為何 crossfade 能把 C1 kink 消掉,且為何**斜坡本身必須 C1**):
#   重疊區 composed 姿勢 P(T) = (1−w(s))·A(ta) + w(s)·B(tb),s=(T−T0)/xf,ta/tb 為兩 clip 的 local 時間
#   (dta/dT=dtb/dT=1)。微分 →
#     P'(T) = (w'(s)/xf)·(B(tb)−A(ta)) + (1−w)·A'(ta) + w·B'(tb)。
#   在重疊**左界** T0(s=0):P'(T0⁺) = (w'(0)/xf)·(B_start−A(d_before−xf)) + A'(d_before−xf);
#   左界之外(純 A)P'(T0⁻) = A'(d_before−xf)。相減 → **接點引入的速度不連續** = (w'(0)/xf)·(B_start−A(d−xf))。
#   同理**右界** T0+xf(s=1):= (w'(1)/xf)·(B(xf)−A_end)。
#   ⇒ 斜坡 w'(0)=w'(1)=0(smoothstep/smootherstep)時**接點引入的 kink 恆為 0(閉式精確)**,把離散切換換成
#     xf 秒的平滑過渡(過渡內速度為 A'/B' 的平滑混合,無新 kink);線性斜坡 w'≡1 則兩端 kink≠0 → crossfade
#     本身**不足以** C1,**C1 的斜坡**才是關鍵(見閘 X4 負對照)。此 kink 是**閉式**(乘 w'(0)/w'(1)),與有限差分
#     取樣步長、與 clip 內部關鍵幀位置皆無關 —— 不會把 beat 自身的內部節拍 kink 誤計為接點 artifact。

def crossfade_ramp(name):
    """權重斜坡 `w(s)` 與其導數 `w'(s)`(s∈[0,1],w(0)=0 全取前 beat、w(1)=1 全取後 beat)。回傳 `(w, wprime)`。
      - "smoothstep"   : w=3s²−2s³,w'(0)=w'(1)=0 → **C1**(接點速度連續)。
      - "smootherstep" : w=6s⁵−15s⁴+10s³,w'(0)=w'(1)=w''(0)=w''(1)=0 → **C2**(更高階,兩端 w'仍=0)。
      - "linear"       : w=s,w'≡1 → 兩端 w'≠0(負對照:crossfade 仍在重疊兩界頓挫)。
    純函式、additive。未知名稱 → ValueError。"""
    if name == "smoothstep":
        return (lambda s: 3.0 * s * s - 2.0 * s * s * s, lambda s: 6.0 * s - 6.0 * s * s)
    if name == "smootherstep":
        return (lambda s: 6.0 * s ** 5 - 15.0 * s ** 4 + 10.0 * s ** 3,
                lambda s: 30.0 * s ** 4 - 60.0 * s ** 3 + 30.0 * s ** 2)
    if name == "linear":
        return (lambda s: s, lambda s: 1.0)
    raise ValueError("crossfade_ramp: 未知 ramp '{}'(可用 smoothstep/smootherstep/linear)".format(name))


def _blend_state(sa, sb, w):
    """兩個 `spine_anim.sample()` 狀態的線性混合 `(1−w)·sa + w·sb`(缺席通道視為 setup identity;含 shear)。
    回傳同 `sample()` 形狀。純函式。"""
    rb = {}
    for b in set(sa["bones"]) | set(sb["bones"]):
        da = sa["bones"].get(b, _LOOP_IDENT)
        db = sb["bones"].get(b, _LOOP_IDENT)
        rb[b] = {k: (1.0 - w) * da.get(k, _LOOP_IDENT[k]) + w * db.get(k, _LOOP_IDENT[k]) for k in _LOOP_IDENT}
    rs = {}
    for s in set(sa["slots"]) | set(sb["slots"]):
        aa = sa["slots"].get(s, {"alpha": 1.0})["alpha"]
        ab = sb["slots"].get(s, {"alpha": 1.0})["alpha"]
        rs[s] = {"alpha": (1.0 - w) * aa + w * ab}
    return {"bones": rb, "slots": rs}


def _normalize_xf(order, xf):
    """candidate (L-7) — 把 crossfade 的 `xf` 規格正規化成 **per-junction**(逐接點)列表。

    `xf` 可為:
      - **scalar**(int/float):所有接點共用同一重疊秒數(= L-6 的行為;回 `(xf,)·(n-1)`,`was_scalar=True`)。
      - **list/tuple**(長度 = `len(order)-1`):逐接點各自的重疊秒數(L-7 的**選擇性/非對稱** crossfade;
        某接點給 `0` = 該接點**不混場**、保留瞬切撞擊感;`was_scalar=False`)。
    回傳 `(xf_list, was_scalar)`。每個值須 ≥0,否則 ValueError;長度不符 → ValueError。純函式、additive。
    **honest boundary**:哪些接點要混、各給多長 xf 屬**美術手感(A 類)** —— 本函式只把**機制**一般化成可逐接點指定,
    不替使用者決定取值(同 L-6:只客觀化機制,不決定套哪些接點)。"""
    njunc = max(0, len(order) - 1)
    if isinstance(xf, (list, tuple)):
        if len(xf) != njunc:
            raise ValueError("crossfade: per-junction xf 長度 {} != 接點數 {}(order 長度 {})".format(
                len(xf), njunc, len(order)))
        xs = [float(v) for v in xf]
        for v in xs:
            if v < 0:
                raise ValueError("crossfade: per-junction xf 不可為負(得 {})".format(xs))
        return xs, False
    x = float(xf)
    if x < 0:
        raise ValueError("crossfade: xf 不可為負(xf={})".format(xf))
    return [x] * njunc, True


def _crossfade_layout(anims, order, xf):
    """計算 crossfade 序列的時間佈局(確定性)。相鄰 beat 重疊 `xf` 秒 → 每個接點總時長縮該接點的 xf。
    回傳 `(offsets, durs, total)`:offsets[i]=第 i beat 在 composed 的起點,beat i 佔 [offsets[i], offsets[i]+durs[i]]。

    `xf` 可為 scalar 或 **per-junction 列表**(L-7,見 `_normalize_xf`)。
    守衛:
      - **scalar 路徑(零回歸)**:沿用 L-6 的「xf 超過**最短 beat 時長的一半**」判準(逐位元相容)。
      - **per-junction 路徑**:對每個 beat,其**左右重疊和**(左接點 + 右接點 xf)不得超過該 beat 時長
        (避免三方重疊);此判準在均勻 xf 時退化為 scalar 判準(2·xf ≤ min_dur ⟺ xf ≤ min_dur/2)。
    xf<0 → ValueError;beat 不存在 → KeyError。"""
    import spine_anim as _SA
    durs = []
    for name in order:
        if name not in anims:
            raise KeyError("crossfade: beat '{}' 不在 anims(可用:{})".format(name, sorted(anims.keys())))
        durs.append(_SA.duration(anims[name]))
    xfs, was_scalar = _normalize_xf(order, xf)
    last = len(order) - 1
    if len(order) >= 2:
        if was_scalar:
            s = xfs[0]
            if s > 0:
                min_d = min(durs)
                if s > min_d / 2.0 + 1e-12:
                    raise ValueError("crossfade: xf={} 超過最短 beat 時長的一半 {}(會造成三方重疊)".format(
                        s, min_d / 2.0))
        else:
            for i in range(len(order)):
                leftx = xfs[i - 1] if i > 0 else 0.0
                rightx = xfs[i] if i < last else 0.0
                if leftx + rightx > durs[i] + 1e-12:
                    raise ValueError(
                        "crossfade: beat '{}' 左右重疊 {}+{}={} 超過時長 {}(會造成三方重疊)".format(
                            order[i], leftx, rightx, leftx + rightx, durs[i]))
    offsets = []
    o = 0.0
    for i, name in enumerate(order):
        offsets.append(round(o, 6))
        o += durs[i] - (xfs[i] if i < last else 0.0)
    total = round(o, 6)
    return offsets, durs, total


def crossfade_pose_at(anims, order, xf, T, ramp="smoothstep"):
    """candidate (L-6) — crossfade 序列在 composed 時間 `T` 的**解析混合姿勢**(真正的 mix,非純平移)。

    相鄰 beat 重疊 `xf` 秒;重疊區 `P(T)=(1−w(s))·A(ta)+w(s)·B(tb)`(見本段頂部推導),body 區為該 beat 原姿勢。
    `ramp` 決定權重斜坡(見 `crossfade_ramp`)。`xf=0` 退化為純接續(= `compose_sequence` 的姿勢,接點瞬間切換)。
    回傳同 `spine_anim.sample()` 形狀的 state。**這是 `compose_sequence`(純平移+去重)做不到的組合層能力**:
    在接點**混合**而非瞬切。純函式、additive、不改任何值。"""
    import spine_anim as _SA
    wfun, _ = crossfade_ramp(ramp)
    offsets, durs, total = _crossfade_layout(anims, order, xf)
    xfs, _ = _normalize_xf(order, xf)
    T = min(total, max(0.0, T))
    last = len(order) - 1
    for i, name in enumerate(order):
        start = offsets[i]
        end = start + durs[i]
        xr = xfs[i] if i < last else 0.0   # 與後一 beat 的右重疊秒數(per-junction)
        xl = xfs[i - 1] if i > 0 else 0.0  # 與前一 beat 的左重疊秒數
        # 與後一 beat 的重疊區 [end−xr, end](= [offsets[i+1], offsets[i+1]+xr]);xr=0 → 該接點瞬切,不混場
        if i < last and xr > 0 and (end - xr) - 1e-9 <= T <= end + 1e-9:
            nb = order[i + 1]
            s = (T - (end - xr)) / xr
            s = min(1.0, max(0.0, s))
            return _blend_state(_SA.sample(anims[name], T - start),
                                _SA.sample(anims[nb], T - offsets[i + 1]), wfun(s))
        # body 區 [start + 左重疊, end − 右重疊]
        lo = start + xl
        hi = end - xr
        if lo - 1e-9 <= T <= hi + 1e-9:
            return _SA.sample(anims[name], T - start)
    return _SA.sample(anims[order[last]], T - offsets[last])


def _state_scaled_diff(s1, s2, scale):
    """`max |scale·(s1−s2)|` 跨所有 bone 通道 + slot alpha(缺席視為 setup identity)。純函式。"""
    m = 0.0
    for b in set(s1["bones"]) | set(s2["bones"]):
        d1 = s1["bones"].get(b, _LOOP_IDENT)
        d2 = s2["bones"].get(b, _LOOP_IDENT)
        for k in _LOOP_IDENT:
            m = max(m, abs(scale * (d1.get(k, _LOOP_IDENT[k]) - d2.get(k, _LOOP_IDENT[k]))))
    for s in set(s1["slots"]) | set(s2["slots"]):
        a1 = s1["slots"].get(s, {"alpha": 1.0})["alpha"]
        a2 = s2["slots"].get(s, {"alpha": 1.0})["alpha"]
        m = max(m, abs(scale * (a1 - a2)))
    return m


def crossfade_seam_kink(clip_before, clip_after, xf, ramp="smoothstep"):
    """candidate (L-6) — crossfade 接點(前 beat 尾 ⨯ 後 beat 首,重疊 `xf` 秒)**接點引入的 C1 速度不連續量(閉式)**。

    依本段頂部推導,crossfade 重疊區只在**兩界**可能引入接點速度不連續(過渡內部為平滑混合,無新 kink):
      - 左界(重疊起點,s=0):`|w'(0)/xf · (B_start − A(d_before−xf))|`
      - 右界(重疊終點,s=1):`|w'(1)/xf · (B(xf) − A_end)|`
    (A=clip_before,B=clip_after;各通道取 max,單位同 `seam_velocity_gap`。)回傳 `{"left","right","max"}`。

    **閉式、精確**:乘上斜坡導數 `w'(0)/w'(1)`,**與有限差分步長、與 clip 內部關鍵幀位置皆無關** —— 不會把
    beat 自身的內部節拍速度 kink 誤計為接點 artifact(L-5 的 `seam_velocity_gap` 量**純接續**瞬切的 kink,
    是 `xf→0` 的極限;本函式量**crossfade 後**殘餘的接點 kink)。`w'(0)=w'(1)=0` 的斜坡(smoothstep/
    smootherstep)→ 兩界皆 **0**(接點 kink 被 crossfade 消掉);線性斜坡 `w'≡1` → 兩界 = 兩 clip 在重疊界的
    值差 / xf(kink 猶存,見閘 X4)。守衛:xf≤0 → ValueError(xf=0 非 crossfade,應走 compose_sequence)。
    純函式、additive。"""
    import spine_anim as _SA
    if xf <= 0:
        raise ValueError("crossfade_seam_kink: xf 必須 > 0(xf={};xf=0 為純接續,見 seam_velocity_gap)".format(xf))
    _, wp = crossfade_ramp(ramp)
    da = _SA.duration(clip_before)
    b_start = _SA.sample(clip_after, 0.0)
    a_mid = _SA.sample(clip_before, da - xf)          # 前 beat 尾前 xf 秒的姿勢
    b_mid = _SA.sample(clip_after, xf)                # 後 beat 首後 xf 秒的姿勢
    a_end = _SA.sample(clip_before, da)
    left = _state_scaled_diff(b_start, a_mid, wp(0.0) / xf)
    right = _state_scaled_diff(b_mid, a_end, wp(1.0) / xf)
    return {"left": left, "right": right, "max": max(left, right)}


def crossfade_junction_kinks(anims, order, xf, ramp="smoothstep", h=1e-3):
    """candidate (L-6 / L-7) — crossfade 序列 `order` 每個相鄰接點的 crossfade 後 C1 kink(閉式,見 `crossfade_seam_kink`)。

    `xf` 可為 scalar(全接點同重疊)或 **per-junction 列表**(L-7,見 `_normalize_xf`)。
    - 接點 xf>0 → crossfade 後殘餘 C1 kink(閉式 `crossfade_seam_kink`;smoothstep/smootherstep → 0)。
    - 接點 **xf=0 → 該接點不混場、退化為瞬切** → 回報其 **L-5 `seam_velocity_gap`**(瞬切極限的接點 kink,
      kink 重現)—— 這是**選擇性平滑**的 crux:只混部分接點,未混的接點保留撞擊頓挫。
    回傳 `[{"i","seam","xf","left","right","max"}, ...]`(長度 len(order)-1)。純函式、additive。"""
    _crossfade_layout(anims, order, xf)   # 觸發守衛(xf 範圍 / beat 存在)
    xfs, _ = _normalize_xf(order, xf)
    out = []
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        if xfs[i] > 0:
            k = crossfade_seam_kink(anims[a], anims[b], xfs[i], ramp)
            out.append({"i": i, "seam": "{}->{}".format(a, b), "xf": xfs[i],
                        "left": k["left"], "right": k["right"], "max": k["max"]})
        else:
            g = seam_velocity_gap(anims[a], anims[b], h)   # xf=0:瞬切,接點 kink = L-5 速度 gap
            out.append({"i": i, "seam": "{}->{}".format(a, b), "xf": 0.0,
                        "left": g, "right": g, "max": g})
    return out


def is_c1_crossfade_sequence(anims, order, xf, ramp="smoothstep", vel_tol=1.0):
    """candidate (L-6) — crossfade 序列 `order`(重疊 xf、斜坡 ramp)串接後是否**全程 C1 連續**(每接點 kink ≤ vel_tol)。

    與 `is_c1_continuous_sequence`(L-5,純接續)對照:後者對真實大獎序列恆 False(接點速度突變 15~114);
    本函式以 crossfade **修正**接點 —— `ramp="smoothstep"`(w'兩端=0)時每接點 kink 閉式=0 → **True**,證
    crossfade+C1 斜坡把「可播放(C0)」提升到「播得平順(C1)」。`ramp="linear"` → 仍 False(kink 猶存)。
    純函式、additive。"""
    return all(j["max"] <= vel_tol for j in crossfade_junction_kinks(anims, order, xf, ramp))


def _encode_alpha(a):
    """alpha 0..1 → Spine 8-hex 色(白 RGB + alpha 末兩碼),夾到 [0,1]。"""
    v = int(round(min(1.0, max(0.0, a)) * 255))
    return "ffffff{:02x}".format(v)


_BONE_CH_KEYS = {"rotate": (["angle"], ["rotate"]),
                 "translate": (["x", "y"], ["x", "y"]),
                 "scale": (["x", "y"], ["scaleX", "scaleY"]),
                 "shear": (["x", "y"], ["shearX", "shearY"])}


def crossfade_sequence(anims, order, xf, nsamp=16, ramp="smoothstep", merge_tol=1e-6):
    """candidate (L-6) — 把多個 beat 依 `order` 以 **crossfade(時間重疊 `xf` 秒 + 權重混合)** 串成**單一可載入**
    animation,回傳 `(composed, segments)`。每個出現過的通道(bone rotate/translate/scale/shear + slot color alpha)
    逐一重取樣**解析混合姿勢** `crossfade_pose_at` 成線性關鍵幀:取樣時刻 = 該通道所屬 beat 的**原關鍵幀**平移後時刻
    (角點精確命中)∪ 每段 body 的 `nsamp` 等分細分(捕捉 bezier 弧)∪ 每個接點重疊區的 `nsamp` 等分。
    body 區 `crossfade_pose_at` 回純 clip 姿勢(忠實),重疊區回混合姿勢。

    與 `compose_sequence`(L,純平移+去重,接點瞬切 → C0 但 C1 kink)對照:本函式在接點**混合**而非瞬切,
    `ramp="smoothstep"` 時接點 C1 連續(見 `crossfade_seam_kink` / 閘)。**`xf=0` 委派 `compose_sequence`
    (逐位元相容零回歸)** —— 無重疊即純接續。`segments` 回報各 beat 在 composed 的 `[start, start+dur]`
    (**重疊 → 相鄰段區間相交 xf**,與 compose 的無交疊不同)。確定性、additive、不改任何輸入 clip 的值。

    **L-7 per-junction**:`xf` 可為 scalar 或**逐接點列表**(見 `_normalize_xf`)。某接點 xf=0 → 該接點**不混場**
    (退化為瞬切,body 區相接、無重疊細分);其餘接點照常混場。**全接點 xf=0(含 scalar 0)→ 委派
    `compose_sequence`(逐位元相容零回歸)**。body 細分的統一時間解析度 `dt` 取**最短非零接點** xf / nsamp。"""
    xfs, _ = _normalize_xf(order, xf)
    if all(x == 0 for x in xfs):
        return compose_sequence(anims, order)
    offsets, durs, total = _crossfade_layout(anims, order, xf)
    last = len(order) - 1
    pos_xf = [x for x in xfs if x > 0]
    min_xf = min(pos_xf)   # 統一時間解析度基準(最短非零接點)

    # 收集每個 (group, part, ch) 的取樣時刻集合(composed 時間軸)。
    times = {}   # (group, part, ch) -> set[float]

    def _add(group, part, ch, t):
        times.setdefault((group, part, ch), set()).add(round(min(total, max(0.0, t)), 6))

    def _subdiv(group, part, ch, lo, hi, n):
        if hi <= lo:
            return
        for j in range(n + 1):
            _add(group, part, ch, lo + (hi - lo) * j / n)

    dt = min_xf / nsamp   # 統一時間解析度:body 與重疊同步距 → body 忠實度隨 nsamp 收斂(同重疊)
    for i, name in enumerate(order):
        clip = anims[name]
        start = offsets[i]
        body_lo = start + (xfs[i - 1] if i > 0 else 0.0)
        body_hi = start + durs[i] - (xfs[i] if i < last else 0.0)
        nbody = max(1, int(round((body_hi - body_lo) / dt)))
        for group in ("bones", "slots"):
            for p, chans in clip.get(group, {}).items():
                for ch, frames in chans.items():
                    # body 的原關鍵幀(平移後)精確命中角點 + body 等步細分(dt)捕捉 bezier 弧
                    for f in frames:
                        t = f["time"] + start
                        if body_lo - merge_tol <= t <= body_hi + merge_tol:
                            _add(group, p, ch, t)
                    _subdiv(group, p, ch, body_lo, body_hi, nbody)
    # 重疊區:每個 xf>0 接點重取樣,涵蓋前後 beat 在重疊出現的所有通道(xf=0 接點瞬切、無重疊細分)
    for i in range(last):
        if xfs[i] <= 0:
            continue
        ov_start = offsets[i + 1]
        chset = set()
        for src in (anims[order[i]], anims[order[i + 1]]):
            for group in ("bones", "slots"):
                for p, chans in src.get(group, {}).items():
                    for ch in chans:
                        chset.add((group, p, ch))
        for (group, p, ch) in chset:
            _subdiv(group, p, ch, ov_start, ov_start + xfs[i], nsamp)

    composed = {"bones": {}, "slots": {}}
    for (group, p, ch), tset in times.items():
        frames = []
        for t in sorted(tset):
            st = crossfade_pose_at(anims, order, xf, t, ramp)
            fr = {"time": round(t, 6)}
            if group == "slots":
                a = st["slots"].get(p, {"alpha": 1.0})["alpha"]
                fr["color"] = _encode_alpha(a)
            else:
                d = st["bones"].get(p, _LOOP_IDENT)
                keys, srckeys = _BONE_CH_KEYS[ch]
                for k, sk in zip(keys, srckeys):
                    fr[k] = round(d[sk], 6)
            if frames and abs(frames[-1]["time"] - fr["time"]) <= merge_tol:
                continue   # 時間重合去重(維持 Spine 時間嚴格遞增)
            frames.append(fr)
        composed[group].setdefault(p, {})[ch] = frames
    for group in ("bones", "slots"):
        if not composed[group]:
            composed.pop(group)
    segments = [{"beat": order[i], "start": offsets[i], "dur": round(durs[i], 6)} for i in range(len(order))]
    return composed, segments


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json", help="build_spine 產出的 skeleton.json")
    ap.add_argument("--psd", default="assets/robot_parts.psd", help="用於取 storyboard 的來源 PSD")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--inplace", action="store_true", help="寫回 skeleton.json")
    a = ap.parse_args()
    from analyze_target import analyze
    sk = json.load(open(a.skeleton_json, encoding="utf-8"))
    spec = analyze(a.psd, a.genre)
    anims = build_animations(sk, spec["3_motion_storyboard"])
    sk["animations"] = anims
    if a.inplace:
        json.dump(sk, open(a.skeleton_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"animations": list(anims.keys()),
                      "beats": {k: {"bones": len(v.get("bones", {})), "slots": len(v.get("slots", {}))}
                                for k, v in anims.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
