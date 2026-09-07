#!/usr/bin/env python3
"""分鏡類型先驗庫(S1 #3)。

每個類型 = 一組「beat(節拍)」;每 beat 有 keywords(用來把真實動畫名歸類做驗證)、
描述、以及依結構角色(body/head/limb/effect)的動作模板(給 rigger 起手)。

**驗證優先**:validated_against 指向 repo 內真實 spine;`validate_priors.py` 會檢查
該先驗的 beat 關鍵字能否覆蓋真實動畫命名(覆蓋率),確保先驗不是空想。
未驗證的類型明確標 validated_against=None。
"""

# 動作模板:beat × 角色 → 建議動作(繁中,給 rigger)
def _roles(in_body, in_head, in_limb, in_eff,
           lo_body, lo_head, lo_limb, lo_eff, out_all, out_eff):
    return {
        "In":  {"body": in_body, "head": in_head, "limb": in_limb, "effect": in_eff},
        "Loop": {"body": lo_body, "head": lo_head, "limb": lo_limb, "effect": lo_eff},
        "Out": {"body": out_all, "head": out_all, "limb": out_all, "effect": out_eff},
    }

_BIGWIN_ROLES = _roles(
    "彈入+輕微 overshoot 縮放", "隨身體彈入+回正", "大幅甩入(旋轉+位移+放大)", "炸開:放大+旋轉+亮度峰值",
    "呼吸(±小幅縮放/位移)", "微點頭/傾", "末梢小幅擺盪(相位錯開)", "脈動/緩轉(alpha/scale 微幅循環)",
    "縮出/淡出", "收斂淡出")
# candidate 0e/0f 主秀節拍(additive;經 gen_animations 路由到 beat_templates 的 gen_reveal/gen_hit)。
# burst = 大獎主秀「現身炸開」(collapsed→蓄勢 hold→overshoot→阻尼回擺,首 collapsed 尾 identity)。
# hit   = 慶祝期的衝擊重音(anticipation→impact→settle,首尾 identity → 可插在 Loop 循環間)。
_BIGWIN_ROLES["burst"] = {
    "body": "藏→蓄勢→炸開 overshoot→阻尼回穩", "head": "隨身體炸開+回正",
    "limb": "內收→爆出旋轉→阻尼回正", "effect": "全暗蓄勢→亮爆+旋轉甩→回穩"}
_BIGWIN_ROLES["hit"] = {
    "body": "反向蓄力→命中放大→阻尼回擺", "head": "微抬預備→下砸→回彈",
    "limb": "反向蓄力→whip 甩出→阻尼回擺", "effect": "先暗→亮度峰值→阻尼+旋轉甩"}
# candidate 0g→(H) 續 (E):再把 0g 的 combo/charge 主秀節拍接進先驗庫(additive)。
# combo = 連擊(遞增 impact 峰 ≥3);charge = 蓄力充能(峰前長 hold)。經 gen_animations 路由到
# beat_templates 的 gen_combo / gen_anticipate_hold(beat key 由 beat_category 認出類別)。
_BIGWIN_ROLES["combo"] = {
    "body": "三段遞增衝擊(蓄力→命中,一擊比一擊重)→阻尼回穩", "head": "隨連擊點頭遞增",
    "limb": "三連甩(幅度隨連擊遞增)→阻尼回正", "effect": "每擊亮度閃(遞增)→回穩"}
_BIGWIN_ROLES["charge"] = {
    "body": "快速下蹲→長蓄力 hold→單發大釋放 overshoot→阻尼回擺", "head": "低頭充能→抬起釋放",
    "limb": "反向拉滿並 hold→爆甩→回正", "effect": "壓暗充能 hold→釋放瞬亮→回穩"}
# candidate 0h→(I) 續 (E)/(H):再把 0h 的 cascade(跨件錯開波)主秀節拍接進先驗庫(additive)。
# cascade 與 combo/charge 本質不同 —— 它是**跨件時序**簽章:同一 beat 套到每件,但每件依**件序相位**
# 錯開觸發成一道波(peak 時刻隨件序遞增)。經 gen_animations 的 _PHASE_AWARE 把件序相位帶進各件,
# 路由到 beat_templates 的 gen_cascade(beat key 由 CASCADE_KEYWORDS 認出類別)。
_BIGWIN_ROLES["cascade"] = {
    "body": "輪到時 dip 蓄力→pop overshoot→阻尼回穩(依件序錯開)", "head": "隨波 pop",
    "limb": "輪到時反向蓄力→甩出→回正(波掃過)", "effect": "輪到時壓暗→閃亮→回穩(一件接一件亮起)"}


PRIORS = {
    "slot_bigwin": {
        "desc": "大獎主角:每檔位一組 進場/循環/退場",
        "tiers": ["Super", "Mega", "Omg", "Legend"],
        "beats": [
            {"key": "In", "kw": ["in", "intro", "enter", "start", "comeout"],
             "desc": "入場爆發:主體放大/彈入,肢體大幅甩入,特效炸開(旋轉+放大+亮度峰值)"},
            # 主秀節拍(candidate 0f;PROPOSAL:主秀運動無唯一正解,閘驗結構簽章非美感)。
            # Award 真值僅 In/Loop/Out → 此二 beat 於 validate_priors 顯示為 prior_beats_unused(誠實)。
            {"key": "burst", "kw": ["burst", "reveal", "showup", "現身", "炸開", "開獎"],
             "desc": "主秀現身:collapsed→蓄勢 hold→炸開 overshoot→阻尼回穩(首 collapsed 尾 identity)"},
            {"key": "hit", "kw": ["hit", "impact", "punch", "打擊", "命中", "重擊"],
             "desc": "慶祝衝擊重音:anticipation→impact→settle(首尾 identity,可插 Loop 間)"},
            # candidate 0g→(H):combo/charge 主秀節拍(PROPOSAL,結構簽章非美感)。
            # Award 真值僅 In/Loop/Out → 此二 beat 亦列 prior_beats_unused(誠實,覆蓋率單調不受擾)。
            {"key": "combo", "kw": ["combo", "multihit", "multi_hit", "chain", "連擊", "連段", "連打"],
             "desc": "連擊主秀:遞增 impact 峰 ≥3(一擊比一擊重),尾段阻尼回穩(首尾 identity,可插 Loop 間)"},
            {"key": "charge", "kw": ["charge", "windup", "wind_up", "chargeup", "蓄力", "充能", "蓄勢"],
             "desc": "蓄力充能主秀:長蓄力 hold→單發大釋放 overshoot→阻尼回擺(首尾 identity,可插 Loop 間)"},
            # candidate 0h→(I):cascade 跨件錯開波(PROPOSAL,跨件時序簽章非美感)。
            # Award 真值僅 In/Loop/Out → 亦列 prior_beats_unused(誠實,覆蓋率單調不受擾)。
            {"key": "cascade", "kw": ["cascade", "wave", "ripple", "sequence", "sweep", "wipe", "錯開", "波", "依序", "接連"],
             "desc": "跨件錯開波主秀:每件依件序相位錯開 pop(峰時刻隨件序遞增,散佈成波;首尾 identity,可插 Loop 間)"},
            {"key": "Loop", "kw": ["loop", "idle"],
             "desc": "待機循環:整體微呼吸(±小角度/位移),特效持續脈動/緩轉"},
            {"key": "Out", "kw": ["out", "exit", "end", "close"],
             "desc": "退場:主體縮出/淡出,特效收斂"},
        ],
        "roles": _BIGWIN_ROLES,
        "validated_against": "Award",
    },
    "slot_reveal": {
        "desc": "開獎/揭示物件:靜置→待機→登場→開獎主秀→命中強調→循環→收尾(觀測自 main_draw 9 支)",
        "tiers": None,
        "beats": [
            {"key": "static", "kw": ["static"], "desc": "初始靜置(單幀/擺位)"},
            {"key": "idle", "kw": ["idle"], "desc": "待機呼吸(多變體:idle/idle2/idle3 錯開節奏)"},
            {"key": "comeout", "kw": ["comeout", "come", "appear", "enter", "in"], "desc": "登場:物件入畫"},
            {"key": "open", "kw": ["open", "reveal", "draw"], "desc": "開獎主秀(最長,主體開啟/展開,特效峰值)"},
            {"key": "hit", "kw": ["hit", "win", "match"], "desc": "命中強調(短促放大/閃光)"},
            {"key": "loop", "kw": ["loop"], "desc": "結果循環"},
            {"key": "close", "kw": ["close", "out", "end"], "desc": "收尾(收合/淡出)"},
        ],
        # 開獎物件多為機構件:主體=開合,特效=光帶/粒子;沿用泛用動作模板
        "roles": {
            "static": {"body": "定位擺姿", "head": "定位", "limb": "定位", "effect": "低亮度待命"},
            "idle": {"body": "微呼吸", "head": "微擺", "limb": "末梢微盪", "effect": "微脈動"},
            "comeout": {"body": "入畫+overshoot", "head": "隨入", "limb": "甩入", "effect": "亮起"},
            "open": {"body": "開啟/展開(主秀)", "head": "抬起", "limb": "張開", "effect": "光帶炸開+粒子"},
            "hit": {"body": "短促放大", "head": "強調", "limb": "彈動", "effect": "閃光峰值"},
            "loop": {"body": "結果呼吸", "head": "微擺", "limb": "微盪", "effect": "持續流光"},
            "close": {"body": "收合", "head": "收", "limb": "收", "effect": "淡出"},
        },
        "validated_against": "main_draw",
    },
    # ↓↓ 未驗證(repo 無對應真值 spine 動畫)—— 明確標記,待有真值再校準 ↓↓
    "slot_symbol": {
        "desc": "轉軸符號(symbol):落定→待機→中獎強調(UNVALIDATED,無真值動畫)",
        "tiers": None,
        "beats": [
            {"key": "land", "kw": ["land", "drop", "in", "appear"], "desc": "落定(從上落下+彈)"},
            {"key": "idle", "kw": ["idle", "static", "loop"], "desc": "待機(微浮動/微光)"},
            {"key": "win", "kw": ["win", "hit", "match", "active"], "desc": "中獎:放大彈跳+發光+粒子"},
        ],
        "roles": {
            "land": {"body": "落下+壓縮回彈", "head": "隨落", "limb": "隨落", "effect": "落定亮光"},
            "idle": {"body": "微浮動", "head": "微擺", "limb": "微盪", "effect": "微光脈動"},
            "win": {"body": "放大彈跳", "head": "強調", "limb": "彈動", "effect": "發光+粒子爆"},
        },
        "validated_against": None,
    },
    "character_idle": {
        "desc": "泛用角色待機(UNVALIDATED):待機呼吸為主 + 偶發點綴",
        "tiers": None,
        "beats": [
            {"key": "idle", "kw": ["idle", "loop", "breath", "static"], "desc": "待機呼吸循環"},
            {"key": "accent", "kw": ["accent", "blink", "look", "special", "extra"], "desc": "偶發點綴(眨眼/張望)"},
        ],
        "roles": {
            "idle": {"body": "呼吸(胸口起伏)", "head": "微點頭/傾", "limb": "末梢自然垂盪(相位錯開)", "effect": "微光脈動"},
            "accent": {"body": "重心微移", "head": "張望/眨眼", "limb": "小動作", "effect": "閃爍"},
        },
        "validated_against": None,
    },
}

DEFAULT_GENRE = "slot_bigwin"

# candidate (J):檔位(tier)幅度差異化。slot_bigwin 宣告 tiers=[Super,Mega,Omg,Legend],但先前
# 所有檔位共用同一組主秀 beat 幅度 —— 檔位只是 metadata,從未影響生成。此處給每檔位一個嚴格遞增的
# **overshoot 增益**(gain):愈高檔位主秀愈大。gain 只作用在「越過 identity 的量」(scale 的 >1
# overshoot、rotate/translate 偏移),**不動 alpha/介面** → 每檔位仍保 setup identity 首尾、各 beat
# 結構簽章不變(只放大幅度,不改種類)。**首檔 gain=1.0** → 與無檔位輸出逐值一致(回歸安全)。
TIER_GAINS = {
    "slot_bigwin": {"Super": 1.0, "Mega": 1.4, "Omg": 1.9, "Legend": 2.5},
}


def get(genre):
    return PRIORS.get(genre, PRIORS[DEFAULT_GENRE])


def tier_gains(genre):
    """回傳該 genre 的 {tier: gain}(依宣告 tiers 排序,嚴格遞增,首檔=1.0);
    無檔位(tiers=None)或未定義 gain 表回 None → 呼叫端據此判斷是否產檔位變體。"""
    g = TIER_GAINS.get(genre)
    tiers = (PRIORS.get(genre, {}) or {}).get("tiers")
    if not g or not tiers:
        return None
    return {t: g[t] for t in tiers if t in g}


def _tokens(name):
    """把動畫名切成 token:先以非英數分段,再拆 camelCase。全小寫。
    例 'Award_Legend_In'→['award','legend','in'];'mainDrawOpen'→['main','draw','open']。"""
    import re as _re
    parts = _re.split(r"[^A-Za-z0-9]+", name)
    toks = []
    for p in parts:
        if not p:
            continue
        p = _re.sub(r"(?<=[a-z])(?=[A-Z])", " ", p)   # camelCase 邊界
        # 字母串與數字串各自成 token(numbered 變體:idle2→['idle','2'])
        toks += _re.findall(r"[A-Za-z]+|[0-9]+", p)
    return [t.lower() for t in toks]


def classify_anim(name, prior):
    """真實動畫名 → 該先驗的 beat key。以**整個 token** 比對(非子字串,避免 'end'∈'legend'、
    'draw'∈'main_draw' 誤判),並**優先採用最後一個 token(節拍後綴)**;
    同位置以較長關鍵字 tie-break;無匹配回 None。"""
    toks = _tokens(name)
    if not toks:
        return None
    kw2beat = {}
    for b in prior["beats"]:
        for kw in b["kw"]:
            kw2beat.setdefault(kw, b["key"])
    # 由最後一個 token 往前找;每個位置取「等於某關鍵字」的最長關鍵字
    for i in range(len(toks) - 1, -1, -1):
        cands = [kw for kw in kw2beat if kw == toks[i]]
        if cands:
            return kw2beat[max(cands, key=len)]
    return None
