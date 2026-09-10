# S1 — wobble shear 峰隨檔位遞增(candidate G-4'',`wobble_tier_amplitude` L2)

> 2026-09-10。把 (G-4') 新生成的 **shear 通道節拍(wobble)** 接進 (J) 的**檔位幅度差異化**機制:
> wobble 的 shearX 峰隨檔位(Super→Legend)嚴格遞增,同時**阻尼振盪簽章在每個檔位保形**。
> 又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4')。

## 缺口(honest boundary 的接續)

- **(J)** 讓主秀 beat 依檔位產出 `{beat}__{tier}` 幅度差異化變體,但 `tier_variants.amplify_bone_tl`
  的增益只作用 **scale / rotate / translate** 三通道。
- **(G-4')** 讓 `gen_wobble`(斜拉 jelly wobble)成為**第一個產出 `shear` 通道**的生成器,但當時
  `wobble ∉ MAIN_SHOW_CATS` 且 amplify 不碰 shear → **wobble 完全不隨檔位放大**(檔位愈高、主秀愈爆,
  唯獨斜拉晃動強度不變 = 不一致)。G-4' 誠實標記此為 honest boundary(「tier 變體未接」)。
- 本次(G-4'')正好照那條邊界接上:**shear 通道也吃檔位增益**。

## 做了什麼(全 additive)

1. **`tier_variants.MAIN_SHOW_CATS`** 加入 `"wobble"` → `build_animations(tier_gains=)` 對 wobble
   也產 `wobble__{tier}` 變體(In/Loop/Out 仍檔位無關)。
2. **`tier_variants.amplify_bone_tl`** 加 `shear` 通道處理:對 0 對稱 → `v' = g*v`(同 rotate/translate)。
   - 每幀**同比**放大 → ①首尾 0 仍 0(介面契約保持,可插 Loop);②符號序列不變;
     ③相繼極值幅度**遞減比不變**(r=0.5 阻尼比乘上共同因子 g 後仍是 r)→ **阻尼振盪簽章保形**。
   - `g=1.0`(Super)→ identity 變換 → 逐位元同無檔位輸出(向後相容);無 shear 通道的 beat 此迴圈空轉(零回歸)。
3. **`validate_wobble_tier.py`**(新,5 AC)。
4. **`validate_tier_variants.py`**(J 閘)J3 改 **channel-aware**:每主秀 beat 依其**實際使用的幅度通道**
   (scale-overshoot / rotate / shear)量遞增性 —— 因 `SA.sample` **不含 shear 通道**,wobble 用
   新增的 `_shear_amp` 直讀 keyframe。J 閘現自然涵蓋 wobble(shear 軸遞增)且對舊 scale/rotate 節拍不變。
5. **`check_readiness`** 新增 cap `wobble_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
6. 圖 `knowledge/figures/s1_wobble_tier.png`(左:各檔位 shearX 阻尼包絡;右:峰 |shearX| 遞增 bar)。

## 驗收(`validate_wobble_tier.py` OVERALL PASS,先驗庫→真實 build_spine robot 骨架→build_animations)

- **T1 present + backward-compat**:wobble base 有 shear;每檔位 `wobble__{tier}` 產出、finite、有 bone、
  帶 shear、名仍路由回 wobble;**base(含 In/Loop/Out + base wobble)帶/不帶 tier_gains 逐位元不變**。
- **T2 crux — shear 峰遞增**:峰 |shearX| = **[16.0, 21.6, 27.2, 33.6]°** Super<Mega<Omg<Legend 嚴格遞增,
  且 Super(g=1)== base(向後相容)。
- **T3 阻尼簽章逐檔保形**:每檔位 wobble bone 仍(a)首尾 shearX=0;(b)繞 0 變號 ≥3;(c)相繼極值嚴格遞減。
- **T4 shear 隔離**:全 storyboard(含所有 `__tier` 變體)僅 wobble 及其變體帶 shear → `include_shear`
  補償對象仍只鎖 wobble,對 (J) 既有 scale/rotate 節拍零 shear 外洩。
- **T5 負對照**:(a)**平增益守衛** 全 1.0 → T2 遞增 FALSE(證閘測遞增非恆真)且各檔位逐位元==base;
  (b)**通道隔離單元測** `amplify_bone_tl`:scale-only bone → 不生 shear 鍵、scale 照放大;
  shear-only bone → shear 放大 g*v、不生 scale 鍵(證 shear 增益加性、與其他通道正交)。

## 關鍵發現

- **同比放大 = 阻尼簽章的自然保形變換**。阻尼振盪簽章 = 「繞 0 變號 + 相繼極值遞減」兩條件並立
  (G-4' 的 W2)。對整條包絡乘上共同正因子 g:符號序列不動、遞減**比**(r)不動 → 兩條件都保。
  這與 (J) 對 scale「只放大 identity 上方 overshoot」異曲同工:**檔位改的是強度、不是結構**(誠實)。
- **channel-aware 是 J 閘的正確一般化**:`SA.sample` 只回 rotate/x/y/scaleX/scaleY(**無 shear**),
  故舊 J3 對純 shear 的 wobble 量到 scale_overshoot=[0,0,0,0] → 若不改會**假陰性**。改成「量該 beat
  實際使用的通道」後,J 閘成為完整的檔位-幅度閘,對 scale/rotate/shear 節拍一致把關。

## honest boundary(仍在)

- shear 峰階梯沿用 (J) 的幅度增益 `{Super:1.0,Mega:1.35,Omg:1.70,Legend:2.10}`(PROPOSAL,結構簽章客觀、
  手感留使用者 A 類)。
- 仍只產 **shearX**(shearY≡0);wobble 尚未接 **count-aware**(如「晃動次數隨檔位」——需在 gen 時決定振盪
  段數,同 J-2 對 combo 的做法,不能事後 amplify)。
- 單一真值資產(robot_parts)。與 `spine-anim-forge` 區塊同 **HOLD**(運動基元為先驗手感、防固化)。

## 續(擇一,皆純自主)

- **(G-4''')** wobble 接 count-aware:晃動振盪**段數**隨檔位遞增(比照 J-2 combo nhits,gen 時決定)。
- 產 **shearY** / 斜拉 squash(shear + coupled scale,雙通道耦合節拍)。
- **(J-3)** cascade 波速/散佈/件數隨檔位。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
