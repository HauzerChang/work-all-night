# S1 檔位(tier)幅度差異化 — candidate (J)

> 里程碑 2026-09-07。讓 `slot_bigwin` 宣告的 `tiers=[Super,Mega,Omg,Legend]` **真的驅動生成**:
> `build_spine --animate --tier-variants` 直出每檔位主秀變體 `<Tier>_<beat>`,**愈高檔位主秀幅度愈大**,
> 且每檔位仍保 setup identity 介面、各 beat 結構簽章不變(只放大幅度,不改種類)。

## 缺口(為何做這步)

`genre_priors.slot_bigwin` 一直宣告 `tiers=[Super,Mega,Omg,Legend]`,但**檔位只是 metadata**——
`build_animations` 從不讀它,所有檔位共用同一組主秀 beat 幅度。這是「模板/metadata 就緒 ≠ 生成器接上」
在**檔位維度**的再現:標籤存在,生成器沒接。真實 big-win 遊戲裡「檔位愈高、演出愈盛大」是核心體感,
故補上「檔位 → 幅度」這一環。

## 做法:gain 只放大「越過 identity 的量」

給每檔位一個嚴格遞增的 **overshoot gain**(`genre_priors.TIER_GAINS`):
`Super=1.0 < Mega=1.4 < Omg=1.9 < Legend=2.5`。`genre_priors.tier_gains(genre)` 依宣告 tiers 排序回
`{tier: gain}`(無 tiers 或無 gain 表 → `None`,呼叫端據此 gating)。

主秀生成器(`gen_hit/gen_reveal/gen_combo/gen_anticipate_hold/gen_cascade`)收 `gain` kwarg,末端呼叫
`beat_templates._apply_gain(b, s, gain)`:

| 通道 | 規則 | 理由 |
|---|---|---|
| **scale** | 只放大 overshoot(>1):`v → 1+gain*(v-1) if v>1 else v` | 峰放大;squash/collapse/settle 下衝(≤1)**保持** → 不出負 scale、floor/collapsed 介面守恆 |
| **rotate / translate** | 整體 ×gain(相對 identity=0 的偏移) | 0 仍為 0 → 首尾 identity 守恆,甩幅隨檔位放大 |
| **color / alpha** | **不動** | alpha 編碼 reveal/hide 介面與亮度、非幅度;放大會破壞首尾契約 |

**gain=1.0 逐值不變** → 首檔(Super)== 無檔位輸出 == 既有 validator 逐值回歸安全(關鍵設計約束)。

`gen_animations.build_animations(skeleton, storyboard, tier_gains=None)`:對**主秀類別**
(`_TIER_VARYING={hit,reveal,combo,charge,cascade}`)beat **額外**輸出每檔位變體 `<Tier>_<beat>`;
非主秀 beat(In/Loop/Out/hold)與 `tier_gains=None`(預設)照舊只輸出基礎 beat(逐值不變)。
`build_spine --animate --tier-variants` 由 `genre_priors.tier_gains(genre)` 取 gains 傳入(feature opt-in)。

### 為何「只放大越過 identity 的量」是正確性要件(非美化)

- **介面守恆**:identity 幀(scale=1、rotate/translate=0)在任何 gain 下不變 → 每檔位變體仍能無縫插在
  Loop 循環間(hit/combo/charge/cascade 首尾 identity)、或接在 Loop 前(reveal 尾 identity)。
- **不出負 scale**:reveal 的 collapsed 起手(scale 0.02,≤1)不被放大 → 不會變成 `1+2.5*(0.02-1)=-1.45`
  的翻面。squash floor(charge ~0.85、hit anticipation ~0.93)同理保持。
- **簽章與幅度解耦**:cascade 的「各件峰時刻」、hit 的「(scale-1) 符號變化數」、charge 的「峰前蓄力
  時間佔比」皆是**時間性/次數性**量;gain 只動幅度不動時間 → 逐檔位不變。故放大**不改種類**。

## 驗收:`validate_tier_variants.py` 5 AC 全 PASS

從 **genre 先驗庫** → `analyze_target.build_storyboard`(真實 robot 5 拆件 role/件序)→ **真實
`build_spine` 骨架** → `build_animations(tier_gains)`,量測各檔位變體(整合閘,非只測模板):

- **J1 present+monotone**:每主秀 beat×每件真峰依檔位**嚴格遞增**且皆 ≥1.12。實測(光暈 bone):
  hit `1.35→1.49→1.66→1.87`、burst `1.35→1.49→1.67→1.88`、combo `1.35→1.49→1.66→1.87`、
  charge `1.35→1.49→1.66→1.87`、cascade `1.34→1.47→1.64→1.84`。
- **J2 介面契約守恆**:每檔位變體皆**尾** setup identity(alpha=1);非 collapse 起手 beat
  (hit/combo/charge/cascade)**首**亦 identity。
- **J3 結構簽章守恆**:每檔位變體仍具該 beat 判別簽章(`_hit_signature`/`has_combo_signature`/
  `has_charge_signature`/`has_cascade_signature`/reveal collapse+真峰),復用 0f/0g/0h 判準確保一致。
- **J4 負對照**:(a) In/Loop/Out 等非主秀 beat **不產**檔位變體(stray=[]);(b) **平坦 gain**(全 1.0)
  → 各檔位真峰**相等**(證遞增來自 gain 排程,非管線把檔位放大);(c) 首檔(gain=1.0)變體與
  `tier_gains=None` 皆**逐值同 base beat**(回歸)。
- **J5 gating+coverage**:無 tier_gains 的 genre(`slot_reveal`,tiers=None → `tier_gains` 回 None)
  **不產**檔位變體(feature 正確 gated);`validate_priors` 覆蓋率仍 ==1.0(檔位變體非 beat,不擾動)。

回歸(全 PASS):validate_priors / priors_beats(E)/ priors_combo_charge(H)/ priors_cascade(I)/
beat_templates(0f)/ more_beats(0g)/ cascade(0h)/ anim(+selftest)/ pivot_rotation(0i)/
scale_pivot(G-3)/ round-trip validate_build 對 `--tier-variants` build(setup pose 不受額外 animations 影響)。

## 關鍵發現

- **「只放大越過 identity 的量」是同一模式的第三次出現**:與 0i/G-3 的 pivot 補償
  `Δ=(M−I)(O−P)`(在 identity 時為 0)、cascade 的 phase threading 一樣,都是「額外參數在中性值時
  退化為原行為」→ 回歸逐值安全、介面自動守恆。此模式讓「加維度」不需重驗舊維度。
- **幅度與簽章正交**:能只放大幅度而不動任何結構簽章,靠的是把 gain 限制在 overshoot/偏移(幅度)、
  不碰時間軸與 alpha(種類/介面)。J3 的逐檔位簽章守恆就是這正交性的量化證明。

## 產出

- `tools/analyzer/genre_priors.py`(+`TIER_GAINS`/`tier_gains()`)
- `tools/analyzer/beat_templates.py`(+`_apply_gain`,5 主秀生成器 +`gain` kwarg)
- `tools/analyzer/gen_animations.py`(`build_animations(tier_gains=)`、`_gen_beat`、`_TIER_VARYING`)
- `tools/analyzer/build_spine.py`(`--tier-variants` 旗標)
- `tools/analyzer/validate_tier_variants.py`(新整合閘,5 AC)
- 圖 `knowledge/figures/s1_tier_variants.png`(5 主秀 beat × 4 檔位 scale 包絡,首尾 identity 守恆)
- cap `tier_amplitude_differentiation` L2 併入 `spine-anim-forge`(仍 HOLD:運動基元先驗、單一真值資產)

## honest boundary / 待續

- gain 排程(Super=1.0…Legend=2.5)為**先驗手感提案**(主秀幅度無唯一正解);緩動手感留使用者(A 類)。
- **連擊數隨檔位遞增**(高檔位 combo 打更多下)為後續:現只放大幅度、不改 combo 的峰數(改次數會動
  結構簽章的參數化,需另設 AC)。可作下一個 bounded chunk。
- 檔位變體僅對有 `TIER_GAINS` 表的 genre 生效(現只 slot_bigwin);其他 tiered genre 待有真值再定 gain 排程。
