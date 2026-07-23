# S3 端到端驗收 — PSD 切件 → 生成 mesh → 對照 Award 真實藝術家 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成器)串成端到端,對**真實生產 spine `Award`** 的
  3 個 mesh 件(光暈/身體/左手)驗收 —— `generate_mesh_v2`(auto)生成的 mesh 覆蓋率(IoU vs alpha)
  **達到或超過藝術家 mesh 基準**,且拓樸乾淨(0 退化 / 0 孤兒 / 格式合法),同時**頂點數只用藝術家的
  0.45~0.74 倍**。3 件全 `piece_pass`,`overall_pass=true`。
- **信心**:中高。對真實生產標的(非合成、非 main_draw)驗證;評估器經正確/翻轉/縮小三態負對照,
  鑑別力明確(見下)。限制:此 3 件在 Award **無 deform timeline**(加權骨動,非逐頂點 deform),
  故**只驗靜態覆蓋+setup 拓樸,未驗 deform 穩健**(無 ground-truth deform 場,不硬套 → 誠實標註)。
- **階段**:第 2 階段 / S3×S4 整合(端到端里程碑)。

## 量化結果(`tools/mesh_gen/compare_generated_vs_artist.py`)

| 件 | 生成 v/t (mode) | 生成 IoU | 藝術家 v/t | 藝術家 IoU | 覆蓋對等 | 頂點比 |
|---|---|---|---|---|---|---|
| 光暈 | 35 / 49 (delaunay-v1) | 0.933 | 78 / 76 (hull=78) | 0.949 | ✅(margin .03) | 0.449 |
| 身體 | 60 / 97 (delaunay-v1) | **0.966** | 98 / 154 | 0.948 | ✅(**優於**) | 0.612 |
| 左手 | 59 / 97 (delaunay-v1) | 0.964 | 80 / 116 | 0.977 | ✅(margin .03) | 0.738 |

判定:`my_iou >= artist_iou - 0.03` 且拓樸乾淨。3 件全過。

## 關鍵發現

1. **v2 auto 對這 3 件全走 v1 Delaunay**:三件長寬比 <1.2(光暈 0.97 / 身體 1.12 / 左手 0.84),
   非「高瘦 strip」→ auto 正確回退 v1 散點 Delaunay。**這是 v1 在真實 blob 形狀上的首次真值對照**,
   證明 v1 對「非窗簾類」的一般件仍能達藝術家覆蓋率(先前 v1 只在 curtain_left 上比過)。
2. **生成器頂點更省**:同等或更佳覆蓋率下只用藝術家 45~74% 頂點。藝術家 mesh 頂點多,
   多半為了**加權變形的平滑度**(骨動時的形變自由度),而非覆蓋 —— 覆蓋率不隨頂點數線性上升。
   ⇒ 若要對齊藝術家的「可變形性」,需補的是**權重/頂點密度策略(BBW)**,不是覆蓋率。
3. **座標對映交叉驗證**:藝術家 mesh 的 `uvs` 為 region-local [0,1];柵格化進切件框架時
   **`uv_flip_y=false` 三件一致勝出**(v=0 對應影像頂列)→ 確認 Spine JSON mesh uv 的 v 軸方向,
   且切件(PSD 原生方向)與 spine region 同向。
4. **光暈是純 hull 多邊形**(78v 全在 hull、0 內部點、76 三角扇形化);身體/左手才有內部點
   (hull 40/98、42/80)。生成器用少量內部 Delaunay 點即達成同級覆蓋。

## 評估器可信度(負對照 / 鑑別力)

RULES 要求「評估器本身要可信」。對藝術家 mesh 三態柵格化 IoU:

| 件 | 正確方向 | y 翻轉(錯) | uv 中心縮小 30%(錯) |
|---|---|---|---|
| 光暈 | 0.949 | 0.426 | 0.458 |
| 身體 | 0.948 | 0.604 | 0.479 |
| 左手 | 0.977 | 0.590 | 0.500 |

→ 錯誤姿態掉到 0.43~0.60,覆蓋率 IoU **有明確鑑別力**,不是「什麼都過」的鬆指標。

## 可重現

```
python3 tools/mesh_gen/compare_generated_vs_artist.py           # overall_pass=true, exit 0
# 參數:--margin 0.03(覆蓋對等容差)、--budget 128(藝術家最高 98v)、--psd/--award 可換
```

## 未解 / 下一步

- **加權(weighted)mesh 的 deform 驗收缺口**:這 3 件靠骨骼權重變形。要真正對齊藝術家「可變形性」,
  下一個能力是 **BBW 權重生成 + 骨動 deform 驗收**(S3 路線圖的 "+BBW 權重" 尚未做)。
  Award 有這些件的骨骼綁定可作真值。
- **端到端組裝(SkelToJson)**:已驗「件→mesh 覆蓋達標」,尚缺把 mesh + `機器人拆件/<圖層名>` 命名 +
  size+2px padding 寫成完整 Spine attachment 的組裝工具(STATE 候選 #2)。
