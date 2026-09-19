# S1 (G-4''''') squash 接檔位差異化:體積守恆**耦合 amplify**

- **結論**:斜拉果凍擠壓 `squash`(G-4'''' 的 shear + 耦合非均勻 scale 節拍)已接上檔位幅度差異化 ——
  擠壓幅度 `|scaleX−1|`(與非均勻 `|scaleX−scaleY|`)隨檔位 **Super<Mega<Omg<Legend 嚴格遞增**,
  **且放大後每個擠壓幀仍 `scaleX·scaleY==1`(體積守恆保形)**。關鍵是不能用天真的
  per-component `_amp_scale`(只放大 identity 上方、scaleY<1 樓地板不動 → 破壞守恆),
  而要用**耦合 amplify**:把擠壓量 `q=scaleX−1` 隨檔位放大(`scaleX'=1+g·q`),另一軸由守恆
  **解出** `scaleY'=1/scaleX'`。這補上了 G-4'''' 明列的 honest boundary(「squash 未接 tier,需耦合 amplify」)。
- **信心**:高(純 CPU 確定性;整合閘 `validate_squash_tier.py` 5 AC 全 PASS,含耦合守衛負對照;
  16 條既有閘回歸全綠 + round-trip `validate_build` overall_pass)。
- **相關階段**:S1 反推分析器 → keyframe 生成 → 檔位變體(J 系列)/ 一般仿射運動基元(G-4 系列)。

## 為什麼天真 amplify 會壞掉(這是 G-4'''' 留下 boundary 的原因)

squash 的 scale 是**體積守恆耦合對**:每個擠壓極值 `scaleX=1+q`(拉長)、`scaleY=1/(1+q)`(壓扁),
故 `scaleX>1`、`scaleY<1`、`scaleX·scaleY==1`。

(J) 的 `_amp_scale(v,g)=1+g(v−1) if v≥1 else v` 對 hit/combo/charge 正確(只放大 overshoot、
下方 squash/collapse 樓地板不動 = 誠實)。但對 squash,它會**放大 scaleX(>1)卻保留 scaleY(<1)不動**
→ `scaleX'·scaleY' ≠ 1`,擠壓變成「拉長但沒等量壓扁」= **體積爆增**。實測 Legend(g=2.1)首極值
`scaleX 1.14→1.294`、`scaleY 0.877 不變` → 積 **1.135**(偏離 1 達 0.135 ≫ TOL_VOL 0.02)。

## 解法:耦合 amplify(`tier_variants._amp_scale_coupled`)

```
q = scaleX − 1                # 擠壓量(輸入已守恆)
scaleX' = 1 + g·q            # 擠壓量隨檔位放大
scaleY' = 1 / scaleX'        # 另一軸由守恆解出(不獨立放大)
```

- identity(`q=0`)→ `(1,1)`(**介面契約保持**,可插 Loop 間)。
- `q>0`(拉 X 壓 Y):scaleX' 隨 g 增大、scaleY' 隨之減小,`scaleX'·scaleY'≡1`(**體積守恆保持**)。
- 公式對 `q` 正負對稱 → 日後 squash 反向(拉 Y 壓 X)亦守恆。
- `g=1.0`(Super)→ `scaleX'=scaleX`、`scaleY'=1/scaleX`(對已守恆輸入 ≈ base,向後相容)。

實測 Legend 首極值:coupled `1.294 × 0.7728 = 1.000`(守恆),naive `1.294 × 0.877 = 1.135`(破壞)。

## 接線(全 additive,依 cat 路由)

- `tier_variants.py`:`MAIN_SHOW_CATS += {squash}`;新增 `VOLUME_CONSERVING_CATS={squash}` +
  `_amp_scale_coupled` + `amplify_bone_tl(...,coupled=)` / `amplify_anim(...,coupled=)`。
- `gen_animations.build_animations`:對主秀 beat 產檔位變體時,`coupled = cat in VOLUME_CONSERVING_CATS`
  → squash 走耦合 amplify、其餘主秀走原 per-component（**零回歸**)。
- `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`,
  shear-pivot 端到端把 rotate/scale/shear 三通道繞關節 pivot 補償(scale 關鍵幀不動 → 極值仍守恆)。

## 整合閘 `validate_squash_tier.py`(先驗庫→真實 build_spine robot 骨架→build_animations)5 AC 全 PASS

- **ST1** present + backward-compat:每檔位 `squash__{tier}` 產出/finite/有 bone/≥1 bone 同時帶 shear+scale/
  名路由回 squash;base(In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變。
- **ST2 crux** squash amp monotone:峰 `|scaleX−1|` [0.16,0.216,0.272,0.336]、非均勻 `|scaleX−scaleY|`
  [0.298,0.394,0.486,0.588]、shear `|shearX|` [16,21.6,27.2,33.6]° **三者皆嚴格遞增**;Super==base。
- **ST3 crux** volume preserved per tier:每檔位每擠壓極值幀 `|scaleX·scaleY−1|≤TOL_VOL(0.02)`(實測 <1e-4)、
  非均勻 `≥MIN_ANISO`、擠壓幅度隨極值嚴格遞減(阻尼耦合)→ **耦合 amplify 於放大後仍守恆**。
- **ST4** signature/interface per tier:每檔位 shear 首尾 0、scale 首尾 (1,1);shear 繞 0 變號≥3 + 相繼極值遞減。
- **ST5** neg-control:(a) 平增益守衛(全 1.0)→ 遞增 FALSE 且各檔位峰==base;
  **(b) 耦合守衛(crux)**:真實 squash Legend 變體,耦合 max|prod−1|=9.7e-5≤TOL_VOL、
  天真 `_amp_scale` max|prod−1|=0.152>TOL_VOL → 證「耦合」是本能力 load-bearing 差異、閘可信;
  (c) 耦合單元測:`_amp_scale_coupled` 對 (1,1)→(1,1)、放大後守恆、`|scaleX'−1|` 隨 g 單調。

## 回歸修正:`validate_tier_combo_count` K5(c) 改 driver-aware

squash 進 `MAIN_SHOW_CATS` 後,K5(c)「count 只作用 combo」的舊判準(非-combo 主秀 beat 各檔位
**峰數**不變)對 squash **假陽性**:耦合 amplify 讓 squash 的 scaleX 隨檔位變大,跨過 `impact_peaks`
的 prominence 閾值 → 峰「數」看似 0→1(那是**幅度**效果,非連擊數)。修正=判準改為
「`full`(帶 tier_combo_hits)與 `amp_only`(同 gains 無 counts)對非-combo 變體**逐位元相同**」——
直接隔離「連擊數」驅動,不被振幅誤判(同 (J) J3 從量值改 channel-aware 的精神:**負對照要量對通道/驅動**)。

## 關鍵發現

- **體積守恆節拍的檔位放大必須「耦合」**:守恆是**兩軸的乘積約束**,per-component 幅度增益(各軸獨立)
  天生會破壞它;正解是放大一個自由度(擠壓量 q)、另一自由度由約束**解出**。這是「檔位機制就緒 ≠
  每個新通道接上」的又一實例(同 E/H/I/J/G-4'/G-4''),但這次接的是**帶約束的耦合通道**,非獨立通道。
- **雙軸檔位差異化再擴一軌**:count-aware(結構/拓樸軸,J-2 combo 峰數 / G-4''' wobble 段數)、
  amplitude(幅度軸,J)之外,squash 展示**耦合振幅軸**(擠壓量隨檔位,守恆約束下)。三軸正交:
  squash 的 nosc(段數,已備參數)仍可比照 G-4''' 再接一軌 count-aware(honest boundary)。

## honest boundary（仍在）

- squash 的**擠壓段數** nosc 未接 count-aware(參數已備,比照 G-4''';下一候選 G-4'''''' 之一)。
- `shearY≡0`(僅單軸 shear);雙軸 shear / rotate+scale+shear 三通道同時(塞滿一般仿射 M 全自由度)為後續。
- 擠壓幅度階梯([0.16,…] × 檔位增益 [1,1.35,1.7,2.1])為 PROPOSAL(結構/守恆客觀,手感留使用者 A 類)。
- cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD:運動基元先驗、單一真值資產,防固化)。

圖:`figures/s1_squash_tier.png`(左:scaleX/scaleY 包絡隨檔位;中:每極值 scaleX·scaleY 耦合守恆 vs 天真破壞;右:兩通道峰隨檔位遞增)。
