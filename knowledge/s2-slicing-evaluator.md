# S2 切圖評估器 — 切圖/重組保真的自我品質閘

- **結論**:完成 S2 第一個評估器 `tools/mesh_gen/evaluate_slicing.py`,對 `main_draw` atlas+sheet
  端到端驗證「切圖 → 重組」保真度。真值 = sheet 本身;**45/45 region 重組 MAE=0.0、0 孤兒、0 重疊全過**,
  並回頭證明 `atlas_crop.py` 對 12 個 rotate region 的 derotate/rotate 邏輯**完全正確**。
- **依據**:正對照(真值自一致 MAE=0)+ 雙向負對照(見下)。
- **信心**:高(評估器經負對照確認具鑑別力)。
- **階段**:第 2 階段 / S2(為 S4 切圖鋪路:有此閘,未來自動切圖才能自主收斂)。

## AC(可機讀)

| AC | 內容 | main_draw 結果 |
|---|---|---|
| AC1 解析完整 | 過濾 page 行後 N region 全切出非空 | 45/45 ✅ |
| AC2 重組保真 | 每 region 依 xy/size/rotate 重組回原位 == sheet 對應區 | avg MAE 0.0,exact 45/45 ✅ |
| AC3 0 孤兒 | sheet alpha>0 像素被 region 覆蓋率 ≥ thresh | orphan_ratio 0.0 ✅ |
| AC4 0 重疊 | 被 >1 region 寫入的像素 = 0 | 0 ✅ |

## 評估器可信度驗證(先驗,延續方法論)

- **正對照**:45 region 全 MAE=0 → 真值自一致。
- **負對照 A(rotate 方向錯)**:對**非對稱**大 region 用錯方向(CCW vs 正確 CW)→ MAE 22–64(抓到);
  正確方向 MAE=0。⚠️ 但對**旋轉對稱/近純色** region(如 `image/background` 75×55)CW/CCW 結果相同、
  MAE=0 → **該 region 本身不可區分方向**,非評估器缺陷(已知局限,記之)。
- **負對照 B(xy 平移)**:把最大 region 平移 60px → orphan_ratio 0.147(抓到)。

## 已知 quirk(留給下個 session)

- `atlas_crop.parse_atlas()` 會把 atlas **page 行**(`main_draw.png`,無 xy/size)也收成一筆 region。
  `extract()` 用具名查詢不受影響;但遍歷全部 region 時需過濾 → `evaluate_slicing.real_regions()`
  已以「需有 xy+size」規避。未修改 `atlas_crop` 本體以免影響現有 `validate_against_real` 流程。

## 可重現

```
python3 tools/mesh_gen/evaluate_slicing.py   # overall_pass=True, exit 0
```

## 意義 / 下一步

- 這是 S2 四個評估器(切圖/補圖/mesh/骨架)中**切圖閘**的落地;mesh 閘已於 S3 完成。
- 補圖(inpaint)與骨架評估器尚缺;補圖閘可在此延伸(極端姿態幀 0 破洞/0 接縫,但需先有補圖能力或樣本)。
