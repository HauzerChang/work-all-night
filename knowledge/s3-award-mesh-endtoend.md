# S3 端到端驗收 — PSD 件 → generate_mesh → 對照 Award 真實 mesh

- **結論**:把 `robot_parts.psd` 的 **光暈 / 身體 / 左手** 三件(在生產 spine `Award` 中為 mesh)
  切件後跑 `generate_mesh_v2(mode="auto")`,與藝術家手做 mesh 在**同一張切件 alpha** 上比覆蓋率,
  **三件全 PASS**:生成 mesh 覆蓋率 ≈ 藝術家(margin 0.03 內)且**頂點數更省**。
  這是第一次「PSD→件→mesh」端到端對**真實生產標的**的量化驗收(不只合成/自對照)。
- **信心**:高(真值=PSD 切件 alpha,已由 texture-IoU 0.92~0.99 確認 = spine 生產貼圖同素材;
  藝術家 uvs 無需翻轉即對齊 → 交叉驗證 region-local 正規化慣例)。
- **階段**:第 2 階段 / S3×S4 交會(串起 S4 切圖 → S3 生成)。

## 量化結果(margin=0.03,真值=PSD 切件 alpha)

| slot | 生成(auto) | 藝術家 | Δ(gen−art) | 生成頂點 | 藝術家頂點 | pass |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | IoU 0.933(v35/hull16, delaunay-v1) | IoU 0.949(v78, weighted) | −0.0155 | 35 | 78 | ✅ |
| 機器人拆件/身體 | IoU 0.966(v60/hull20, delaunay-v1) | IoU 0.948(v98, weighted) | +0.0183 | 60 | 98 | ✅ |
| 機器人拆件/左手 | IoU 0.964(v59/hull19, delaunay-v1) | IoU 0.977(v80, weighted) | −0.0126 | 59 | 80 | ✅ |

- 生成 mesh setup 拓樸乾淨(0 bad/翻面三角面);頂點數皆 < 藝術家(35/60/59 vs 78/98/80)。
- 藝術家 IoU 0.95~0.98 且 `uv_flip=None` → **Award mesh uvs 為 region-local 正規化 [0,1] 自然方向**
  (與 main_draw 同慣例),再次確認切件↔spine 同素材同方向。

## ★ 關鍵發現:拓樸選擇取決於「變形模式」,不是一體適用

- **Award 這 3 件無任何 deform timeline**(全 repo `animations.*.deform` 為空)→ 純 **bone-weighted**,
  靠骨骼/權重變形,非逐頂點 deform warp。故對它們**只驗靜態覆蓋 + 頂點預算**;
  真實位移場轉移閘(`deform_eval.transfer_deform_check`)**不適用**(無 deform 場可轉)。
- **strip(v2 預設 rows10×cols3=30v)在這 3 件反而覆蓋不足**:光暈 0.878 / 身體 0.878 / 左手 0.918
  → 光暈、身體低於藝術家−margin。因為 strip 的規則直條拓樸適合**軸對齊、會 warp 的柔性件**(窗簾),
  對**不規則團塊**(機器人光暈/身體)貼合差。
- **`mode="auto"` 對這 3 件正確選了 delaunay-v1**(散點 Delaunay 貼不規則輪廓好)。
- **教訓 / 契約**:mesh 拓樸沒有單一最優。
  - 逐頂點 deform 變形(curtain/shadow,main_draw)→ **strip(v2)**(耐變形、0 自交,見 s3-four-mesh)。
  - bone-weighted 剛體/團塊(Award 機器人件)→ **delaunay-v1**(靜態貼合佳、省頂點)。
  - `generate_mesh_v2(mode="auto")` 已能依形狀二選一;**選擇準則應由「該件的變形方式」驅動**
    (有 deform timeline → strip;純 bone weight → delaunay)。這是給下游 SkelToJson 組裝的規則。

## 工具

`tools/mesh_gen/compare_gen_vs_award.py` — 對照器:
```
python3 tools/mesh_gen/compare_gen_vs_award.py          # 3 件全跑,exit 0=all pass
# 前置:python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --out /tmp/robot_slices
```
真值=PSD 切件 alpha;藝術家 mesh 用 region-local uvs*(W,H) 光柵化(含 v-flip 自檢,本例未觸發)。

## 下一步

- 把「件→Spine mesh attachment」寫成 **SkelToJson 組裝工具**:輸入切件 + manifest(offset/size,S4 已產)
  + 拓樸選擇規則(deform→strip / weighted→delaunay),輸出 Spine 3.8 JSON 的 mesh attachment
  (uvs region-local、hull 排前、triangles)。這是把 S4→S3 串成「能寫出檔」的最後一哩。
- weighted mesh 的**權重生成(BBW)**尚未做:目前只驗幾何/uvs,骨綁與 bind 座標(weighted 格式)未生成
  → 若要完全復現 Award 這類 bone-driven mesh,需 S5 骨架 + BBW 權重(留待後續)。
