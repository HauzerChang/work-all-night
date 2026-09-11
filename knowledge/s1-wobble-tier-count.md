# S1 — wobble 阻尼擺動「段數」隨檔位遞增(candidate G-4''',`wobble_tier_count` L2)

> 2026-09-11。把 (G-4') 的斜拉 wobble(shear 通道阻尼擺動)接進**檔位結構差異化**軸:
> wobble 的阻尼**擺動段數**(nswings)隨檔位(Super→Legend)嚴格遞增,與 (G-4'') 的**幅度**軸
> **正交可疊**。此與 (J-2) 對 combo `nhits` 完全同一心法:**count = 關鍵幀拓樸,必在 gen 當下決定**。

## 缺口(honest boundary 的接續)

- **(G-4'')** 讓 wobble 的 shearX **峰**隨檔位放大(`amplify_bone_tl` 對 shear `v'=g*v`),但誠實標記
  boundary:各檔位仍是**同樣四段**阻尼擺動 —— 有「多斜」沒「晃幾下」。
- 這正是 (J)→(J-2) 對 combo 走過的路:(J) 只差幅度、(J-2) 補上連擊「數」。wobble 缺的是對稱的一步。
- 本次(G-4''')補上:wobble 的擺動**段數**隨檔位遞增(Super 4→Mega 5→Omg 6→Legend 7)。

## 為什麼段數不能事後 amplify(關鍵,同 J-2)

- 幅度增益 g 是對整條 shearX 包絡**同比放大**(每幀 ×g)。同比放大**不改變關鍵幀個數/符號序列**
  —— 它只能讓既有的擺動更斜,**無法多長出一段**擺動。
- 「晃幾下」是關鍵幀**拓樸**,必須在 `gen_wobble` 生成當下決定 → 故走 `tier_wobble_swings` 對 wobble
  檔位變體以該檔位 `nswings` **重生成**整條包絡,**再**疊 (G-4'')/(J) 的幅度增益 g。
- ⇒ 兩軸**正交可疊**:`nswings` 決定晃幾下(結構)、`g` 決定多斜(幅度)。端到端量到
  段數 [4,5,6,7] 與峰 [16,21.6,27.2,33.6]° **同時**遞增(見圖)。

## 做了什麼(全 additive)

1. **`beat_templates.gen_wobble(role, side_sign, radial, nswings=4)`** 泛化:
   - `nswings==4` → **逐位元同 G-4' 手調四段擺**(golden,byte-identical 向後相容;base wobble 恆走此路)。
   - `nswings≠4` → 通用 `_wobble_env(A,r,nswings)`:第 i 段值 =(−1)^i·r^i·A(交替符號→繞 0 振盪;
     r^i 遞減→阻尼),τ 由 `WOBBLE_FIRST_TAU`(0.16)→`WOBBLE_LAST_TAU`(0.80)均勻散佈。
     nswings 段 → 變號 nswings−1 次、非零極值 nswings 個。
2. **`tier_variants`**:`COUNT_AWARE_CATS` 加入 `"wobble"`;新增 `TIER_WOBBLE_SWINGS`
   (`slot_bigwin`: Super4/Mega5/Omg6/Legend7)+ `wobble_swings_for(genre)`。
3. **`gen_animations`**:`_build_beat(...,combo_hits=3)` 泛化為 `_build_beat(...,count=None)`
   (count=None → 各生成器用自身預設 combo nhits=3 / wobble nswings=4,向後相容);
   `build_animations(...,tier_wobble_swings=None)` 新參數,對 wobble 檔位變體以該檔位 nswings 重生成再套 g。
4. **`build_spine --tier-variants`** 自動帶 `wobble_swings_for(genre)`(如 combo 帶 `combo_hits_for`)。
5. **`validate_wobble_count.py`**(新,5 AC)。
6. **`check_readiness`** 新增 cap `wobble_tier_count` L2 併入 `spine-anim-forge`(仍 HOLD)。
7. 圖 `knowledge/figures/s1_wobble_count.png`(左:各檔位 shearX 阻尼包絡,段數 4→7;右:段數 bar)。

## 驗收(`validate_wobble_count.py` OVERALL PASS,先驗庫→真實 build_spine robot 骨架→build_animations)

- **C1 present + backward-compat**:每檔位 `wobble__{tier}` 產出、finite、有 bone、帶 shear、名仍路由回
  wobble;**base wobble 恆 4 段且逐位元同 base**;**`tier_wobble_swings=None` 時 wobble 變體逐位元同
  (G-4'') 幅度-only 輸出**(證加性 opt-in、對 G-4'' 零回歸)。
- **C2 crux — 段數遞增**:擺動段數 = **[4,5,6,7]** == 宣告且 Super<Mega<Omg<Legend 嚴格遞增,
  Super==base(=4);每檔位變體內部仍阻尼(相繼極值嚴格遞減)。
- **C3 介面+簽章保形**:每檔位首尾 shearX=0、繞 0 變號 ≥3、相繼極值嚴格遞減(阻尼);且 shearX **峰**
  仍 Super<Mega<Omg<Legend 單調(證與 (G-4'') 幅度軸疊加不衝突)。
- **C4 正交**:(a) swings+平增益(全 1.0)→ 段數仍遞增且**各檔位峰相等**(幅度被關掉,只剩結構軸);
  (b) gains+無 swings(None)→ 段數**恆 4**、峰遞增 → 兩軸可獨立開關。
- **C5 負對照**:(a)**平段數**(全 4)→ C2 段數單調性 FALSE(證閘測遞增非恆真);(b)無宣告 swings 的
  genre(slot_reveal)→ `wobble_swings_for` None → 不產 wobble tier 變體;(c)swing **只作用 wobble**:
  非-wobble 主秀 beat 在各檔位仍 0 bone 帶 shear(不外洩到別的節拍)。

## 關鍵發現

- **同比放大改不動拓樸,是「count 必須 gen 時決定」的根因**——(J-2)在 combo 上、(G-4''')在 wobble 上
  兩度印證:幅度軸(amplify)與結構軸(count)天生正交,因為前者是逐幀乘常數(保拓樸)、後者是改關鍵幀
  個數(改拓樸)。這給了一條**通用設計律**:任何「數量隨檔位變」的節拍特徵都得回到生成器重生成。
- **阻尼簽章對段數穩健**:r=0.5 下第 7 段幅度 = r^6·A(特效 16°→0.25°)仍有限非零 → 相繼極值嚴格遞減
  在 nswings 拉到 7 仍成立;繞 0 變號 = nswings−1(≥3)自動滿足。段數增加不破壞 G-4' 的阻尼振盪簽章。
- **泛化 `_build_beat` 的 `count` 抽象**:把 J-2 的 `combo_hits` 特例升為通用 `count`(None=生成器自身預設)
  → 新增 count-aware 節拍(wobble)零改 dispatch 骨架,只在 `build_animations` 加一條 category→count-map 分派。

## honest boundary(仍在)

- 段數階梯(4–7)為 PROPOSAL(結構簽章客觀:段數遞增+每段阻尼;手感留使用者 A 類)。
- 仍只產 **shearX**(shearY≡0);斜拉 squash(shear + coupled scale 雙通道耦合)尚未做。
- 單一真值資產(robot_parts)。與 `spine-anim-forge` 區塊同 **HOLD**(運動基元為先驗手感、防固化)。

## 續(擇一,皆純自主)

- 產 **shearY** / 斜拉 squash(shear + coupled scale,雙通道耦合節拍)——wobble 通道軸的最後一塊。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware,同 J-2/G-4''' 心法在跨件軸上)。
- **(G-1)** `--rig`×`--pivot-rotate`/`--scale-pivot`/`--shear-pivot` per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
