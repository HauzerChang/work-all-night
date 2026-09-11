# S1 — wobble 晃動段數隨檔位遞增(candidate G-4''',`wobble_tier_segment_count` L2)

> 2026-09-11。把 (G-4'') 已隨檔位遞增的 wobble **shear 峰值(幅度)**,再補上**結構**軸:
> wobble 的阻尼擺動**極值數**(晃幾下)隨檔位(Super→Legend)嚴格遞增,兩軸**正交可疊**。
> 又一「幅度機制就緒 ≠ 結構數接上」實例 —— 完全對應 (J-2) 之於 combo(J 幅度 → J-2 連擊數)。

## 缺口(honest boundary 的接續)

- **(G-4'')** 讓 `amplify_bone_tl` 放大 shear → wobble 的 shearX **峰值**隨檔位遞增
  (Super 16° → Legend 33.6°)。但當時所有檔位仍是**同樣四擺**:有「多斜」沒「晃幾下」。
- G-4'' 誠實標記此為 honest boundary(「wobble 未接 count-aware」)。本次(G-4''')正好接上。

## 關鍵:段數是**結構**,事後 amplify 加不出來

- 同比放大(`v'=g*v`)只能放大**既有**極值幅度,無法**多長一擺** —— 極值數是關鍵幀**拓樸**,
  必須在 `gen_wobble` **生成當下**決定(同 J-2 對 combo `nhits` 的論證)。
- 故不走 amplify,而對 wobble 檔位變體以該檔位 `nseg` **重生成**整個 beat,**再**疊 (G-4'') 幅度增益。

## 做了什麼(全 additive)

1. **`beat_templates.gen_wobble(role, side, radial, nseg=4)`**:新增 `nseg`。
   - `nseg=4` → **逐位元同 G-4' 手調 golden 四擺**(env 特殊路徑,向後相容 byte-identical)。
   - `nseg≠4` → 通用 `_wobble_env(A, r, nseg)`:第 i 擺 τ 由 `WOBBLE_FIRST_TAU`(0.16)線性到
     `WOBBLE_LAST_TAU`(0.80)、值 `(−1)^i · r^i · A` → +A, −rA, +r²A, …(繞 0 振盪 nseg−1 次變號、
     相繼極值嚴格遞減=阻尼)。首尾 shearX=0、shearY≡0 不變。
2. **`tier_variants.COUNT_AWARE_CATS`** 加入 `"wobble"`(原只有 `combo`);新增
   `TIER_WOBBLE_SEGS={"slot_bigwin":{Super:4,Mega:5,Omg:6,Legend:7}}` + `wobble_segs_for(genre)`。
3. **`gen_animations`**:`_build_beat` 的 count 參數泛化(`combo_hits=3` → `count=None`;
   `None` → 呼叫生成器自身預設 = combo nhits3 / wobble nseg4,**向後相容逐位元不變**);
   `build_animations(..., tier_wobble_segs=None)`,對 wobble 檔位變體以該檔位 nseg 重生成再套增益。
   per-cat count 來源:combo→`tier_combo_hits`、wobble→`tier_wobble_segs`(兩者互不外洩)。
4. **`build_spine`**:`--tier-variants` 自動帶 `wobble_segs_for(genre)`(端到端直出)。
5. **`validate_wobble_count.py`**(新,5 AC)。
6. **`check_readiness`** 新增 cap `wobble_tier_segment_count` L2 併入 `spine-anim-forge`(仍 HOLD)。
7. 圖 `knowledge/figures/s1_wobble_count.png`(左:各檔位 shearX 阻尼包絡,段數愈多擺愈多次;
   右:段數 [4,5,6,7] 與 shear 峰 [16,21.6,27.2,33.6] 兩正交軸皆遞增)。

## 驗收(`validate_wobble_count.py` 5 AC 全 PASS)

從**先驗庫**→**真實 build_spine robot 骨架**→`build_animations(tier_gains, tier_wobble_segs)` 端到端量:

- **V1 present + backward-compat**:每檔位產 `wobble__{tier}` finite/有 bone/帶 shear;
  base wobble 恆 nseg=4 逐位元不變;**`tier_wobble_segs=None` 逐位元同 (G-4'') 幅度-only**(加性 opt-in)。
- **V2 crux — 段數遞增**:各檔位擺動極值數 == 宣告 nseg 且 **[4,5,6,7] 嚴格遞增**、每檔位仍阻尼。
- **V3 介面+簽章+幅度**:每檔位仍首尾 shearX=0、繞 0 變號 ≥3、極值遞減;**且 shear 峰仍隨檔位遞增**
  (證與 (G-4'') 幅度軸疊加不衝突 —— 段數變、峰仍漲)。
- **V4 正交**:(a) segs + 平增益(全 1.0)→ 段數仍遞增(結構獨立於幅度);
  (b) gains + 無 segs → 段數恆 4、shear 峰遞增 → 兩軸可獨立開關。
- **V5 負對照**:(a) 平段數(全 4)→ 段數單調 FALSE(證閘測遞增非恆真);
  (b) slot_reveal 無宣告 → `wobble_segs_for` None → 不產 wobble 變體;
  (c) `tier_wobble_segs` **只作用 wobble**:同時帶 segs 時 combo 峰數各檔位恆 base(不外洩到 combo)。

**回歸全綠**:validate_wobble_tier(G-4'')、tier_combo_count(J-2)、shear_gen(G-4')、tier_variants(J)、
shear_pivot/scale_pivot/pivot_rotation、全 priors/beat/more_beats/cascade/deform_gen;
round-trip validate_build 對 `--tier-variants --shear-pivot` build `overall_pass`(premult MAE 0.031、setup 不變)。
端到端 build 直出 `wobble__{tier}` 段數 [4,5,6,7] × shear 峰 [16,21.6,27.2,33.6](兩軸皆遞增)。

## honest boundary(仍在)

- 斜拉 wobble 形狀為 PROPOSAL(結構簽章客觀、手感留使用者 A 類);shearY≡0(純 shearX)。
- 段數上界 7:wobble T=0.8s 內 7 個極值 τ 由 0.16 均分到 0.80(間隔 ≈0.107,時間嚴格遞增不塌陷),
  阻尼末擺 r^6·A(特效 16° → 0.25°)仍 >dead;再高需重估時間預算或加密。
- 單一真值資產(robot 一件)→ 併入 `spine-anim-forge` 仍 **HOLD**(防運動基元先驗固化)。

## 續(擇一,皆純自主)

- 產 **shearY** / 斜拉 squash(shear + coupled scale 雙通道耦合)。
- **(J-3)** cascade 波速/散佈/件數隨檔位。
- **(G-1)** `--rig` × pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
