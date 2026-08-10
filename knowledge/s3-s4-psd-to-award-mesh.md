# S3+S4 端到端:PSD 切件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)與 S3(`generate_mesh_v2`)串成端到端,對 **Award 生產 spine 的
  真實藝術家 mesh** 驗收通過。`robot_parts.psd` 三個在 Award 中為 mesh 的件(光暈/身體/左手)
  各自生成 mesh,**靜態覆蓋率(IoU)達到或超過藝術家 mesh,且頂點數明顯更少、0 自交**。
  這是 S3 生成器在**第三個、與 main_draw 無關的資產家族(機器人 big win)**上的通用性證據。
- **信心**:高。有藝術家 ground truth 交叉比對 + 雙向負對照確認鑑別力。
- **階段**:第 2 階段 / S3×S4 整合(里程碑:合成→真實單件→端到端對真實生產 mesh)。

## 量化結果(`validate_psd_to_award.py`,2026-08-10)

| 件 | piece px | 藝術家 verts/tris/hull | 藝術家 IoU | 生成 verts/tris/hull | 生成 IoU | mode | 判定 |
|---|---|---|---|---|---|---|---|
| 光暈 | 706×683 | 78 / 76 / 78 | 0.9445 | **35** / 49 / 16 | 0.9343 | delaunay-v1 | ✅ |
| 身體 | 379×425 | 98 / 154 / 40 | 0.9476 | **60** / 97 / 20 | **0.9661** | delaunay-v1 | ✅ |
| 左手 | 257×215 | 80 / 116 / 42 | 0.9766 | **59** / 97 / 19 | 0.9643 | delaunay-v1 | ✅ |

- 三 AC 全過:① IoU ≥ 藝術家 −0.03 margin;② 生成頂點 ≤ 藝術家 ×1.30(實際遠少於藝術家);
  ③ 靜態 self-intersection = 0、degenerate = 0(合法三角化)。
- **生成器用 ~一半的頂點達到藝術家等級覆蓋**(光暈 35 vs 78、身體 60 vs 98、左手 59 vs 80),
  身體甚至 IoU 更高(0.966 > 0.948)。頂點預算效率是這批件的亮點。
- v2 auto 模式對這 3 件都選了 `delaunay-v1`(散點 Delaunay);strip 是 curtain 類長條件才勝出。

## UV 對映(重要,已校驗)

Award mesh 的 `uvs` 是 **region-relative [0,1]**,直接 `uv*W, uv*H`(**不 flip v**)即對齊
PSD 切件像素空間 → 藝術家 mesh 覆蓋自身 alpha 得 0.945/0.948/0.977(合理,含邊緣鋸齒殘差)。
這也再次確認 **PSD 切件 = spine 生產貼圖素材同一份、同方向**(呼應 s4 的 alpha-IoU 0.92~0.99)。

## 負對照(鑑別力)

- 光暈藝術家 mesh 套到**身體 alpha**(件錯配)→ IoU **0.488**(遠低於 0.9)。
- 光暈藝術家 mesh **v-flip** 套自身 alpha → IoU **0.426**(遠低於 0.94)。
→ IoU 比對非「什麼都過」;錯配 / 錯方向會被抓到。

## ⚠️ 為何不做變形閘(誠實聲明)

這 5 個機器人件在 Award **無 deform timeline**(見 `s4-psd-to-spine-real.md`),靠骨骼/權重變形、
非逐頂點 deform → **沒有真實位移場可轉移**。依 `RULES.md`「變形閘用真實位移場轉移,**不要用未校準的
stress_field**」,本驗收**不捏造變形場**,只做靜態拓樸對照。生成 mesh 的**變形穩健度**已在
main_draw 4 mesh(有真實 deform 場、9 anim)證明乾淨,見 `s3-four-mesh-generalization.md`。
若日後要對機器人件做變形驗收,需其骨架/權重驅動的世界座標(需 runtime 或權重反解),屬另一課題。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_pieces
python3 tools/mesh_gen/validate_psd_to_award.py            # all_pass=true, exit 0
```

## 下一步候選

- **切圖→Spine JSON 組裝(SkelToJson)**:已有真實命名慣例(`<PSD名>/<圖層名>`)、size+2px、
  mesh/region 分配、region-relative uv 對映 —— 把「件 + 生成 mesh」寫成完整 Spine attachment JSON,
  端到端產出可載入的 skeleton(下游最後一哩)。
- S2 補圖閘 / 骨架閘(補齊 S2 樞紐)。
