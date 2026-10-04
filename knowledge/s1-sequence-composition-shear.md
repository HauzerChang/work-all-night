# S1 大獎序列組合的 shear 通道無縫(candidate L-2)

> 補 candidate L(`s1-sequence-composition.md`)明列的 honest boundary:序列組合閘看不見 shear 通道。

## 問題(candidate L 的 honest boundary)

candidate L 的序列組合閘以 `spine_anim.sample()` 量接點殘差。但 `sample()` 當時只覆蓋
**rotate / translate / scale**(+ slot alpha)—— **shear 通道對取樣器不可見**。

而 wobble / squash / twist 這三支 beat 的**運動基元正是活在 shear 通道上**
(wobble 純 shearX、squash shearX+耦合非均勻 scale、twist 反相雙軸 shearX/shearY)。
因此 candidate L 的正向序列 `In→hit→combo→charge→cascade→Loop→Out` **刻意不含任何 shear beat**:

> 不是因為 shear beat 不能組合,而是因為「組不組得起來」當時**驗不了**(接點閘看不見 shear)。

這是「**量測限制**」偽裝成「能力限制」的典型:工具的通道覆蓋缺口,會讓一整類 beat 被排除在
已驗證範圍之外。

## 做法(全 additive)

### ① `spine_anim.sample()` 補 shear 取樣

bone 回傳 dict 新增 `shearX` / `shearY` 兩鍵(setup 預設 `(0,0)`),若 bone 有 `shear` 通道
則以同一 `_interp` 內插 x,y。

**向後相容(逐位元)**:全 repo 的 `sample()` 呼叫端一律以**固定鍵集**存取
(`_is_ident`/`_state_diff` 都 `for k in IDENT` 五鍵;無人迭代 bone-dict 全鍵)→ 新增兩鍵
對既有閘**完全不可見**,既有行為逐位元不變(無 shear 通道的 bone 回 `(0,0)`,與不取樣時一致)。
以 `check_readiness` 全閘回歸確認(0 GREEN→RED)。

### ② `validate_sequence_compose_shear.py`(新,5 AC)

含 shear beat 的正向序列 `In → hit → wobble → squash → twist → combo → Loop → Out`
(皆 identity 介面)。接點殘差以 **shear-inclusive** state-diff(七鍵:rotate/x/y/scaleX/scaleY/
**shearX/shearY**)量測;另備 **shear-blind** 子集(前五鍵,重現 candidate L 舊閘)供負對照對照。

| AC | 內容 | 結果 |
|---|---|---|
| **LS1** present+well-formed | 含 shear beat 序列合法;shear 通道確實被帶進 composed | PASS |
| **LS2 crux** shear-aware seam | 每內部接點 shear-inclusive 殘差 **0.0** < 1e-3 | PASS |
| **LS3** shear endpoints id | 每支 shear beat 每個 bone shear 首/末幀 **(0,0)**(=無縫結構原因) | PASS |
| **LS4** faithful concat | 回切每支 shear beat 段逐幀還原孤立 clip 含 shear,殘差 < 1e-4 | PASS |
| **LS5 crux** 負對照 | 見下 | PASS |

### LS5 — crux 負對照(閘可信的關鍵)

造一支**端點 shear≠0** 的壞 wobble(複製 wobble,把某 bone shear 通道**末幀** x 設為 15°,
rotate/x/y/scale **一律不動**),放序列中段 `…→wobble_bad→squash→…`:

- **shear-aware 接點閘抓到**:`wobble_bad->squash` 殘差 = **15**(=注入量)>> tol,且正確指認肇因接點;
- **同一接點的 shear-blind 殘差 = 0** < tol(rotate/x/y/scale 都還是 identity → **舊閘判無縫**);
- → 乾淨證明「補 shear 覆蓋」是**抓這類非無縫的必要條件**(舊閘對 shear 盲),而非冗餘。

## 關鍵發現

1. **取樣器的通道覆蓋缺口會讓接點閘對該通道「盲判無縫」** —— 補通道的價值,用
   「舊閘漏判、新閘抓到**同一注入**」乾淨證明(LS5:同一接點 aware=15 / blind=0)。
2. **三支 shear beat 端點本就 identity(LS3)→ 其實一直可無縫組合**;candidate L 把它們排除
   是**量測限制非能力限制**。補上取樣器覆蓋後,shear beat 與其他 identity-介面 beat 一樣
   屬「可自由排序的 beat 集合」(承 candidate L 的 composability 發現)。
3. **「向後相容」的正確證法是「既有呼叫端的存取模式不觸及新鍵」**:這裡因全 repo 皆固定鍵集
   存取 sample() 輸出,新增鍵天然不可見 → 以全閘回歸(0 GREEN→RED)固化。

## honest boundary(仍在)

- beat **排序**仍 PROPOSAL(手感 A 類);shear beat 之 shear **幅度**為手感(A 類)。
- 單一真值資產(robot);運動基元為手感先驗未學自真值 → `spine-anim-forge` 仍 **HOLD**。

## 關聯

- 前置:`s1-sequence-composition.md`(candidate L,序列組合主體)、`s1-shear-channel-generation.md`
  (wobble 的 shear 生成)、`s1-twist-dual-axis-shear-generation.md`。
- 工具:`tools/analyzer/spine_anim.py`(sample 補 shear)、
  `tools/analyzer/validate_sequence_compose_shear.py`(本閘)。
