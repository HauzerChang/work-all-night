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
_CASCADE_GEO_SOURCES = {"centroid_farthest"}
_CASCADE_GEO_DEFAULT = "centroid_farthest"


def derive_cascade_dir(centers, source="centroid_farthest"):
    """J-7:由件幾何**導出** cascade 投影方向單位向量 `(ux, uy)`,取代手感指定的具名 / 角度 / 向量。

    `source`:
      "centroid_farthest"(預設):件質心 → 距質心**最遠件**的單位向量。**確定性、無 PCA ±符號歧義**
        (PCA 主軸只給一條線、方向正負須另定;最遠件天然定出一個明確指向)。語意 = 波沿「叢集中心 →
        最外側肢體」軸掃(投影最大的最遠件最後 pop)。

    `centers`:list of `(x, y)` 件中心(呼叫端給**當前 beat 的有效件**→ 方向隨實際參與件自適應)。
    回傳**正規化**單位向量。輸入守衛:未知 source、無件、退化幾何(所有件重合 → 零方向)→ `ValueError`。

    crux(為何導出的是**投影向量**而非 radial):最遠件定出一條**有向軸**,相位沿該軸投影排序 → 落在
    J-6 的 `("proj", vec)` 機制,`_cascade_phase_of` 無須任何新排序邏輯;radial(co/oc)是另一族,J-7 不碰。"""
    if source not in _CASCADE_GEO_SOURCES:
        raise ValueError("unknown cascade geo source: {!r} (allowed {})".format(
            source, sorted(_CASCADE_GEO_SOURCES)))
    n = len(centers)
    if n == 0:
        raise ValueError("derive_cascade_dir: no part centers")
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
    純函式、additive、不依賴任何既有索引。"""
    vs = _state_velocity(clip, True, h)
    ve = _state_velocity(clip, False, h)
    m = 0.0
    for b in set(vs["bones"]) | set(ve["bones"]):
        d0 = vs["bones"].get(b, {k: 0.0 for k in _LOOP_IDENT})
        d1 = ve["bones"].get(b, {k: 0.0 for k in _LOOP_IDENT})
        for k in _LOOP_IDENT:
            m = max(m, abs(d0.get(k, 0.0) - d1.get(k, 0.0)))
    for s in set(vs["slots"]) | set(ve["slots"]):
        a0 = vs["slots"].get(s, {"alpha": 0.0})["alpha"]
        a1 = ve["slots"].get(s, {"alpha": 0.0})["alpha"]
        m = max(m, abs(a0 - a1))
    return m


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


# ============================================================================
# candidate (L-5) — 跨 beat 混場 crossfade / mix(序列組合的下一個組合層軸)
# ============================================================================
# L / L-2 / L-3 / L-4 都圍繞 `compose_sequence`,而它是**純時間平移 + 接點去重**
# = **C0 拼接**:任一瞬間**恰好一支 beat 在作用**(前 beat 尾==後 beat 首時無縫銜接)。
# 真實大獎序列常用**混場 / 溶接(crossfade / dissolve)**:在一段**重疊窗**內前 beat
# **淡出**、後 beat **淡入**,兩者**同時貢獻**(疊加 superposition / 加權混合)。
# 純平移 + 去重**在結構上做不到疊加**(它只能把時間錯開,不能讓兩 beat 在同一瞬間並存)。
# 這正是 L 系列一路誠實列出的 honest boundary(「crossfade 需真正的 mix 機制」)。本段把
# 這個**組合層新軸**補上:烘焙式 crossfade —— 在重疊窗內同步取樣兩 clip、加權線性混合、
# 以 dt 網格發出混合關鍵幀;窗外維持純 A / 純 B(原關鍵幀不動,保真)。
#
# 契約與不變量:
#   · partition of unity:A 權重 = 1-w、B 權重 = w、w∈[0,1] ⇒ 兩恆等 clip 混合仍恆等(無 bump)。
#   · 退化:overlap==0 ⇒ **逐位元等同** compose_sequence 的 C0 拼接(strict generalization 負對照)。
#   · 冪等:crossfade(A, A, ov) ⇒ 重疊窗內逐幀還原 A((1-w)A + wA = A)。
#   · C0 邊界:重疊窗兩端(進窗 w=0 → A(進窗點);出窗 w=1 → B(出窗點 local))與純區段值連續。
#   · 真疊加(concat 做不到):重疊窗內某瞬間兩 beat 皆非 identity 時,混合值 = (1-w)·A + w·B
#     既 ≠ 純 A 亦 ≠ 純 B;而 compose_sequence 在同一全域時間只會是**單一** clip 的值。
# honest boundary:slot 混合假設 **alpha-only 白色 tint**(本資產光暈成立),重疊窗內 slot color
#   以 "ffffff"+alpha hex 重發(純區段保留原 hex 不受影響);非白 tint 的 rgb 混合為後續。


def _alpha_hex(a):
    """alpha 0..1 → 8-hex RGBA 字串(白色 tint;重疊窗 slot 混合用)。"""
    v = int(round(max(0.0, min(1.0, a)) * 255))
    return "ffffff{:02x}".format(v)


def crossfade_weight(tau, overlap, fade="linear"):
    """混場權重 w(tau)∈[0,1]:tau=0→0(全 A)、tau=overlap→1(全 B)。A 權重=1-w(partition of unity)。
    預設 **linear**(= tau/overlap);`smooth`=smoothstep(保留但不設預設 —— 不在整合閘引入美感軸)。純函式。"""
    if overlap <= 0:
        return 1.0
    x = max(0.0, min(1.0, tau / overlap))
    if fade == "linear":
        return x
    if fade == "smooth":
        return x * x * (3.0 - 2.0 * x)
    raise ValueError("crossfade_weight: 未知 fade %r" % (fade,))


def blend_states(sa, sb, w):
    """兩個 `spine_anim.sample()` 狀態的逐通道線性混合 `(1-w)·A + w·B`(bones 全通道 + slot alpha;
    缺席通道視為 setup identity,同 `_state_max_diff` 慣例)。純函式、additive。"""
    out_b = {}
    for b in set(sa["bones"]) | set(sb["bones"]):
        da = sa["bones"].get(b, _LOOP_IDENT)
        db = sb["bones"].get(b, _LOOP_IDENT)
        out_b[b] = {k: (1.0 - w) * da.get(k, _LOOP_IDENT[k]) + w * db.get(k, _LOOP_IDENT[k])
                    for k in _LOOP_IDENT}
    out_s = {}
    for s in set(sa["slots"]) | set(sb["slots"]):
        aa = sa["slots"].get(s, {"alpha": 1.0})["alpha"]
        ab = sb["slots"].get(s, {"alpha": 1.0})["alpha"]
        out_s[s] = {"alpha": (1.0 - w) * aa + w * ab}
    return {"bones": out_b, "slots": out_s}


# 骨通道 → (keyframe 欄位名, blend-state 狀態鍵)
_BONE_CHAN = {
    "rotate":    (["angle"],    ["rotate"]),
    "translate": (["x", "y"],   ["x", "y"]),
    "scale":     (["x", "y"],   ["scaleX", "scaleY"]),
    "shear":     (["x", "y"],   ["shearX", "shearY"]),
}


def _dedup_sorted(frames, merge_tol=1e-6):
    """依 time 排序並去除時間重合幀(保留後加入者),確保 Spine『同通道時間嚴格遞增』。"""
    frames = sorted(frames, key=lambda f: f["time"])
    out = []
    for f in frames:
        if out and abs(f["time"] - out[-1]["time"]) <= merge_tol:
            out[-1] = f  # 重合 → 保留後者(混合/後段幀優先於被抹的前段幀)
        else:
            out.append(f)
    return out


def crossfade_pair(A, B, overlap, dt=1.0 / 30.0, fade="linear", merge_tol=1e-6):
    """把兩支 beat clip 以**重疊窗 overlap**(秒)烘焙成**單一**可載入 clip(duration = durA+durB-overlap)。

    結構:
      [0, offsetB)        純 A(原關鍵幀,保真);offsetB = durA - overlap
      [offsetB, durA]     重疊窗:以 dt 網格同步取樣 A(local=t)與 B(local=t-offsetB),
                          混合 `(1-w)·A + w·B`、w=crossfade_weight(t-offsetB, overlap) 發出混合關鍵幀
      (durA, total]       純 B(原關鍵幀平移 +offsetB,保真)

    overlap==0(退化)→ **逐位元等同** compose_sequence 的 C0 拼接(委派之,保證 strict-generalization 負對照)。
    回傳 composed clip(`{"bones":{...},"slots":{...}}`)。純函式、additive、確定性。
    """
    import spine_anim as _SA
    durA, durB = _SA.duration(A), _SA.duration(B)
    lo = min(durA, durB)
    if overlap < -1e-12 or overlap > lo + 1e-9:
        raise ValueError("crossfade_pair: overlap %r 必須在 [0, min(durA,durB)=%r]" % (overlap, lo))
    if overlap <= merge_tol:
        # 無重疊 → 純 C0 拼接,等同 compose_sequence(保證與 L 的拼接機制逐位元一致)
        composed, _ = compose_sequence({"__A": A, "__B": B}, ["__A", "__B"])
        return composed

    offsetB = durA - overlap
    total = durA + durB - overlap
    # 重疊窗取樣網格(含兩端點;末點釘死 durA 以免浮點漂移)
    import math as _math
    n = max(1, int(_math.ceil(overlap / dt - 1e-9)))
    grid = [offsetB + i * dt for i in range(n + 1)]
    grid[-1] = durA
    if len(grid) >= 2 and abs(grid[-1] - grid[-2]) <= merge_tol:
        grid.pop(-2)
    # 預先在網格上算好混合狀態(一次,避免逐通道重取樣)
    blended = []
    for tg in grid:
        w = crossfade_weight(tg - offsetB, overlap, fade)
        sa = _SA.sample(A, tg)
        sb = _SA.sample(B, tg - offsetB)
        blended.append((tg, blend_states(sa, sb, w)))

    composed = {"bones": {}, "slots": {}}

    # ---------- bones ----------
    parts = set(A.get("bones", {})) | set(B.get("bones", {}))
    for part in parts:
        achans = A.get("bones", {}).get(part, {})
        bchans = B.get("bones", {}).get(part, {})
        for chan in set(achans) | set(bchans):
            if chan not in _BONE_CHAN:
                continue
            fkeys, skeys = _BONE_CHAN[chan]
            frames = []
            # 純 A(窗前)
            for f in achans.get(chan, []):
                if f["time"] < offsetB - merge_tol:
                    frames.append(_shift_frames([f], 0.0)[0])
            # 重疊窗混合
            for tg, bl in blended:
                d = bl["bones"].get(part, _LOOP_IDENT)
                fr = {"time": round(tg, 6)}
                for fk, sk in zip(fkeys, skeys):
                    fr[fk] = d.get(sk, _LOOP_IDENT[sk])
                frames.append(fr)
            # 純 B(窗後,local>overlap)
            for f in bchans.get(chan, []):
                if f["time"] > overlap + merge_tol:
                    frames.append(_shift_frames([f], offsetB)[0])
            frames = _dedup_sorted(frames, merge_tol)
            if frames:
                composed["bones"].setdefault(part, {})[chan] = frames

    # ---------- slots(color→alpha hex;重疊窗白 tint) ----------
    sparts = set(A.get("slots", {})) | set(B.get("slots", {}))
    for part in sparts:
        achans = A.get("slots", {}).get(part, {})
        bchans = B.get("slots", {}).get(part, {})
        for chan in set(achans) | set(bchans):
            if chan != "color":
                continue
            frames = []
            for f in achans.get(chan, []):
                if f["time"] < offsetB - merge_tol:
                    frames.append(_shift_frames([f], 0.0)[0])
            for tg, bl in blended:
                a = bl["slots"].get(part, {"alpha": 1.0})["alpha"]
                frames.append({"time": round(tg, 6), "color": _alpha_hex(a)})
            for f in bchans.get(chan, []):
                if f["time"] > overlap + merge_tol:
                    frames.append(_shift_frames([f], offsetB)[0])
            frames = _dedup_sorted(frames, merge_tol)
            if frames:
                composed["slots"].setdefault(part, {})[chan] = frames

    for group in ("bones", "slots"):
        if not composed[group]:
            composed.pop(group)
    return composed


def crossfade_sequence(anims, order, overlap, dt=1.0 / 30.0, fade="linear"):
    """把 `order` 內多支 beat 以每接點 `overlap`(秒)左折疊成單一 crossfade 序列。
    overlap==0 ⇒ 等同 compose_sequence(純 C0 拼接)。回傳 composed clip。確定性、additive。"""
    if not order:
        return {}
    cur = anims[order[0]]
    for name in order[1:]:
        cur = crossfade_pair(cur, anims[name], overlap, dt=dt, fade=fade)
    return cur


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
