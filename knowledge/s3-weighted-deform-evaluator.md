# S3/S2 — weighted-mesh 骨骼變形評估器(補上唯一未驗維度)

**結論**:補上 STATE 反覆標記的唯一未驗維度 —— weighted(綁骨)mesh 的**骨骼變形平滑度**
(靜態 IoU 不涵蓋)。新增 `tools/mesh_gen/weighted_deform_eval.py` 忠實重現 Spine 3.8
「骨骼世界變換 + linear blend skinning(LBS)」,並以向量化幾何閘(自交/翻面/退化)量測
weighted mesh 在真實動畫下會不會壞。對 `Award.json` 7 個真實 weighted mesh 三條 AC 全 PASS。
**信心:高**(setup skinning 正確性硬自檢 + 負對照鑑別力雙向確認;唯一未能做的是接真 Spine runtime 對拍)。
**相關階段:S3(mesh 生成器)/ S2(評估器套件)。**

## 為什麼需要它

`compare_robot_mesh` / `evaluate_mesh` 只驗**靜態** IoU;`deform_eval` 只處理 **unweighted**
mesh(deform timeline 逐頂點加 offset)。但 weighted mesh 的價值正是**骨骼帶動的平滑變形**,
其變形來自「bone 世界變換 × bind 座標 × 權重」的 LBS,和 unweighted 完全不同路徑。
先前對 Award 機器人 3 mesh 只驗靜態覆蓋率 → 明列限制「weighted 骨骼變形平滑度未驗」。本次補上。

## 技術重現(對照 CLAUDE.md 雷點 #4/#6)

- **骨骼世界變換**:Award 全 77 骨皆 `transform:"normal"`(完整繼承)、**無 shear**、
  parent-before-child 排序 → 可精確重現。局部 `la=cosθ·sx, lb=-sinθ·sy, lc=sinθ·sx, ld=cosθ·sy`;
  world = parent∘local 的 2×2 仿射 + 平移。root 視 parent 為 identity。
- **動畫 timeline**:`rotate`(加角度)/`translate`(加位移)/`scale`(**乘**縮放);
  取所有 keyframe 時間 + 相鄰線性內插取樣(substeps=4)。curve/stepped 近似線性(extreme 落 key 上,
  已實測 keyframe-only 與含 substep 結論一致 → 非內插假象)。無 shear timeline。
- **LBS**:`worldV = Σ_j w_j · (bindX_j·a_j + bindY_j·b_j + wx_j , bindX_j·c_j + bindY_j·d_j + wy_j)`。
  weighted 解碼:`[n,(boneIdx,bindX,bindY,w)×n]` 攤平;`nv=len(uvs)//2`。
- **可見性 gating(關鍵!對照雷點 #3)**:mesh 只在 slot **可見**時才需拓樸乾淨 ——
  讀 slot `color` timeline 的 alpha(rrggbb**aa**)線性內插,alpha≤1/255 的幀跳過;
  attachment timeline 未掛此 mesh 的幀也跳過。這是評估器可信的**必要**校正(見下)。
- **效能**:自交檢查 O(E²),原純 Python 掃全 pose 會 timeout → 重寫 `MeshChecker`
  向量化(拓樸固定,預算 edge/非相鄰 pair 一次,逐 pose 只重算座標的 orient/signed-area)。

## 三條 AC(`validate_weighted_deform.py`,全 PASS)

- **AC1 skinning 正確性**:7 個真實 weighted mesh 在 setup pose 重現皆為有效幾何(0 自交/0 退化)。
  → **硬自檢**:骨/LBS 若寫錯,藝術 mesh 連靜止都會壞。7/7 PASS ⇒ 核心 skinning 數學正確。
- **AC2 可見性 gating 生效**:`superwin/Award_Super_In` 的 slot alpha `00→ff@0.067`;
  t=0(alpha=0)未 gating 時 76 自交 → gating 後該髒幀被排除。且各 hero(OMG/Mega/Super/Legend)
  mesh 經 alpha gating 後**只落在自己 tier 的 3 支動畫**(其餘 tier 該 mesh alpha=0 不可見)。
- **AC3 鑑別力(負對照)**:對藝術家乾淨的 `機器人拆件/身體`(可見 3/3 全乾淨)腐化骨綁 →
  shift-bone 506 自交、jitter±100 1602 自交/2 翻面 全被抓 ⇒ 閘非虛過。

## ⚠️ 關鍵校準發現(誠實界定,勿當 bug)

**「所有生產 weighted mesh 在可見幀都拓樸乾淨」= 經驗上為假。** 對 Award 7 mesh 實測(可見幀):
- **乾淨 5/7**:OMG/megawin1/megawin2/機器人左手/機器人身體 → 全可見幀 0 自交/0 翻面。
- **非乾淨 2/7**:
  - `superwin_角色`(112v,最複雜 hero):其擠壓/縮放 `Super_In` **可見階段就自交**
    (alpha=1、area_ratio 升到 1.31,**keyframe 上即有** SI≈34、非內插假象),`Super_Loop` 亦殘留 1 自交+1 翻面。
  - `機器人拆件/光暈`(soft halo):`Legend_In` 可見階段殘 4 自交(fade-in 期 71 自交多在不可見)。
- **啟示**:hero/halo 靠貼圖與快速運動遮掩重疊,藝術家容忍其拓樸自交。故**不存在**
  「所有藝術 mesh worst==0」的通用 pass/fail 閘(這正是先前 `stress_field` miscalibration 的同型陷阱)。

## 評估器可信度與後續用法

- **可信度來源** = AC1(skinning 正確)+ AC3(負對照鑑別力)+ AC2(gating 語意),**不是**
  「藝術 mesh 全乾淨」。此點與 unweighted `_checker_validated` 語意不同,已在 code 註記與 report key 區分
  (`_setup_all_valid` = 正確性訊號;`_artist_clean_visible` = 觀察值)。
- **對「生成 weighted mesh」的正確用法**(下一 chunk,BBW 生成後):對照**同一部位**藝術 mesh 在
  **同一動畫**的可見乾淨率,而非絕對 0。乾淨部位(如身體/左手)要求生成 mesh 同樣 0;
  hero/halo 這種藝術本身就自交的部位,要求「不比藝術更差」。
- 唯一未能做:接真 Spine runtime(webgl)對拍世界座標 —— 被 CDN 網路政策擋(既有 blocker)。
  以 setup 有效性 + 負對照替代,足以判定拓樸正確性。

## 檔案

- `tools/mesh_gen/weighted_deform_eval.py` — 評估器(`build_bones`/`world_affines`/`decode_weighted`/
  `skin`/`pose_at`/`slot_alpha_at`/`MeshChecker`/`eval_weighted_mesh`/`benchmark_weighted`)。
- `tools/mesh_gen/validate_weighted_deform.py` — 三 AC 自驗閘(`python3 … assets/Award.json`,exit 0/1)。
