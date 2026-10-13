# 2.0 (B3) 繞關節 pivot 變換：pivot_about 入口（Δ=(M−I)(O−P））併進結構軸

> 相關階段：spine-ai-editor 2.0 MERGE_PLAN Phase **B3**（承 B2）。信心：高（7AC 全 PASS，真值+負對照+G2 編輯器真值皆過）。
> 來源：`skills/spine-ai-editor/assets/gen_lib/pivot_about.py`、`tools/analyzer/validate_b3_pivot.py`、
> repo `tools/analyzer/pivot_rotation.py`（既有數學）、`references/structural_expansion.md`（新增 SOP E）。

## 結論

把 repo 累積的 **pivot 補償引擎**（`pivot_rotation.py`，`Δ=(M−I)(O−P)`）包成 **skill 層級的「結構軸」入口**
`assets/gen_lib/pivot_about.py`，提供 `apply_pivot_about`（就地把「件繞件中心變換」轉成「件繞**關節 pivot** 變換」）
與 `generate_bigwin_about_pivots`（B2 生成 + B3 pivot 一步到位）。併進 `references/structural_expansion.md` 成
**SOP E**：這是 SOP A/B（加 bone / reparent，**動骨架結構**）的**互補解**——bone 留在件中心、額外補一條 `translate`，
**淨效果 = 件繞關節 pivot 做同樣的旋轉/縮放/切變，骨架結構一字不動**。

## 為什麼這個 chunk 有價值（B3 相對 repo 既有 pivot_rotation）

1. **對外契約化**：repo 的 pivot 補償散在 `pivot_rotation.apply_pivots`（底層），B3 給它一條**公開 skill 入口**
   （自動從 skeleton bones setup 推 `bone_origin`、整份 skeleton / 單支 anim 雙模式、wire G1），與 B2 的
   `make_beat.generate_bigwin` 並列成 gen_lib 的兩條確定性生成/變換軸。
2. **G2 編輯器真值（新增，repo 原閘沒有）**：repo 的 `validate_pivot_rotation.py` 只做**純 Python 模擬**驗不動點，
   **未**驗 pivot 補償後的密通道能否過**編輯器真值閘**。B3 閘把補償後**整份 skeleton 丟進 `validator_v1`**，
   證 **0 error + loop 閉合 0** → pivot 補償不是只有數學對，**遊戲能播且編輯器能匯入**（延續 B1/B2 的雙真值紀律）。

## 數學（確定性、無 ML）

bone setup 原點 O（parent 座標）、該幀 bone local 2×2 線性部 M（純旋轉 R(θ)／含縮放 R·diag(sx,sy)／含 shear 真實 Spine local R·shear·S）。
繞 pivot P 做 M：加平移 **Δ = (M − I)(O − P)**。不動點 `world(ℓ_P)=(O+Δ)+M·(P−O)=P` 對**任意 M** 成立；
θ=0 & S=I & shear=0 → M=I → **Δ=0**（setup/loop 端點/In-Out 介面保 identity，B2 生成波無縫性不破）。
Δ 對 θ/s 非線性 → 通道**加密重取樣**成密網格線性鍵（dt=1/60），幀間殘差 ~ (1/8)|O−P|·(dθ)² << 0.1px。

## AC（`validate_b3_pivot.py`，移植 repo 7AC 改經公開入口 + 加 G2）

真值幾何 = Award 機器人左手拆件世界輪廓（42 verts）+ `infer_pivots` 推得接觸縫肩 pivot（|O−P|=117.4px）。

- **B3-1 fixed-point**（repo AC1）：經入口 `apply_pivot_about` 補償後 pivot 不動點幀間殘差 **<0.5px**（實測 ~0.01）。
- **B3-2 neg-control**（AC2）：**不補償**（繞件中心 O）→ pivot 漂移 **48.83px**（比補償 **4247×**，≥10px）→ 閘非恆真。
- **B3-3 part-moves**（AC3）：離 P 最遠件點位移 **94px**（≥8）→ 沒把件凍住。
- **B3-4 identity-interface**（AC4）：θ=0 幀 Δ=0（<1e-6）→ setup/loop 端點/In-Out 介面保 identity。
- **B3-5 rigid-isometry**（AC5）：所有件點到 P 的距離逐幀絕對偏差 **<0.012px**（真等距繞 P 旋轉）。
- **B3-6 curve-tolerance**（AC7）：rotate 帶緊湊 bezier 緩動時 B3-1 仍成立（殘差 0.06px；加密重取樣正確處理 curve）。
- **B3-7 end2end+G2**（AC6+）：**B2 gen_lib `generate_bigwin(cascade)`**（效果骨 `b_光暈` 帶 rotate+scale pop 脈衝）
  → **B3 入口 `apply_pivot_about(include_scale=True)`** 繞合成關節 pivot（件上方 90px）→
  (a) finite+時間嚴格遞增；(b) loop 端點相等（無縫）；(c) 生成 loop 上 pivot 殘差 **0.25px**（<0.5）；
  (d) 負對照未補償 **36px** 漂移（>>c）；(e) **G2**：補償後整份 skeleton 過 `validator_v1` **0 error + loop 閉合 0**
  （密 rotate/scale/translate 鍵仍 editor 可匯入 + loop 閉合）。

## 關鍵發現

1. **「件繞關節 pivot 變換」有兩條互補路**：**結構軸**（加 bone/reparent，動骨架，最乾淨、永久）vs **keyframe 級**
   `Δ=(M−I)(O−P)`（不動骨架，適合不想改結構/暫時試）。2.0 兩條都收進結構軸文件（SOP A/B vs SOP E），擇一用。
2. **不動點對任意 bone local 仿射 M 成立**（純代數，不需 M 是旋轉/相似）→ 同一入口一路支援 rotate→scale→shear；
   θ=0&S=I 時 Δ=0 **自動保 B2 生成波的無縫性**（不需特判端點）。
3. **pivot 補償後的密通道仍過編輯器真值閘**（0 error + loop 閉合 0）→ 加密重取樣引入的大量線性鍵**不是新的 editor crash 面**
   （末鍵無 curve、首尾 Δ=0 閉合），與 B1 的洞見一致（末鍵 curve 風險在序列 compose，不在單 beat / 單變換）。
4. **include_scale 要對齊實際動的通道**：`b_光暈` 同時有 rotate+scale pop，只補 rotate（M=R）會因未補償 scale 漂；
   `include_scale=True`（M=R·S）才讓件真的繞 pivot 旋轉+縮放（肢體從關節伸長而非自身中心脹縮）。

## honest boundary

- **pivot（哪件繞哪個關節）= 上游 S5 rig 推斷的輸入**，不是本 chunk 生成的：B3 閘用**真值** Award 肩 pivot 驗機制、
  用**合成** pivot 驗端到端。pivot 準度 = 件輪廓保真（見 `s5-rig-pivot-inference.md`）。
- 多件肢體鏈父子傳遞、非均勻 scale / shear 的**端到端**（含 `include_shear`）留後續 chunk；本閘端到端只驗單一效果骨 include_scale。
- 過渡期 import repo `tools/analyzer`（`pivot_rotation`/`spine_anim`）+ `assets/curve_tools`；E1 self-contained bundle 後 standalone。
- Cocos 實機 round-trip / 視覺確認 = 使用者端（排程 scope 邊界，用 `validator_v1` 無頭等價替代）。

回歸：`check_readiness` **0 RED**（新增 cap `b3_pivot` L2 pipeline，併入 `spine-anim-forge` 仍 HOLD）。
