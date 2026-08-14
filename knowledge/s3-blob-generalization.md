# S3 泛化 — 生成 mesh 對真實 Award「機器人 blob 件」達藝術家覆蓋率(端到端 PSD→件→mesh 收斂)

- **結論**:S3 生成器過去只在窗簾/陰影(高瘦 **strip** 拓樸)對照過藝術家真值。本次補上**近方形 blob**
  拓樸(Award 機器人件:光暈/身體/左手,均為 mesh 且 aspect<1.2 → 走 v1 Delaunay 分支)。
  發現預設邊界容差 `epsilon_frac=0.008`(相對周長)是**為窗簾調的**,對柔邊 blob 過粗、覆蓋率掉;
  改用**絕對像素容差 ~2px**(隨件大小自適應)後,3 件全達/超越藝術家覆蓋率且更精簡。
- **信心**:高(對真實生產 spine `Award.json` 的藝術家 mesh 逐件量化對照;靜態閘正/負校準)。
- **階段**:第 2 階段 / S3(里程碑:strip 之外的第二個拓樸類別對真值收斂)。

## 對照真值(Award.json 藝術家 mesh,alpha 來自 Award atlas 切件,uv 空間對齊)

| 件 | 藝術家 v | 藝術家 IoU | gen v(abs2px) | gen IoU | 頂點比 | 靜態拓樸 |
|---|---|---|---|---|---|---|
| 光暈 | 78 | 0.980 | 90 | **0.992** | 1.15× | 0 自交/翻面/退化 |
| 身體 | 98 | 0.976 | 77 | **0.993** | 0.79× | 乾淨 |
| 左手 | 80 | 0.968 | 61 | **0.988** | 0.76× | 乾淨 |

→ **AC1 覆蓋率 / AC2 頂點預算 / AC3 靜態拓樸 三閘 3/3 件全過**(`compare_award_mesh.py` exit 0)。

## 關鍵發現

1. **邊界容差要「絕對像素」而非「相對周長」**:相對容差對大而柔邊的件(光暈周長大)= 大絕對偏差
   → Douglas-Peucker 切角、覆蓋率掉(光暈 0.008→IoU 0.929;0.004→0.966;0.002→0.983)。
   絕對 ~2px 對三件皆自適應到藝術家水準。**已把 v1 加 `epsilon_abs` 選項;v2 的 Delaunay-fallback
   改走 `epsilon_abs=2.0`**(mode 標記 `delaunay-v1-abs2px`)。窗簾走 strip 分支不受影響(4 mesh 重驗全過)。
2. **生成器比藝術家更精簡**:身體/左手在更高 IoU 下頂點數僅藝術家 0.76~0.79×(藝術家內部點多為
   美術動畫需求,非覆蓋所需)。
3. **⚠️ `stress_field` 對 blob 不可信(第 N 次 evaluator miscalibration)**:這 3 件在 Award **無 deform
   timeline**(靠骨骼/權重變形,非逐頂點 deform)→ 無真實位移場可轉移。改用合成 `stress_field` 掃描
   時,**真實藝術家 mesh 竟在 ~0.06 bbox 幅度就自交** → 證明該剪切+正弦場對近方形 blob 形狀不對/過苛。
   故 `compare_award_mesh.py` 把變形裕度**降為診斷(不納入 overall_pass)**,並在 artist 裕度<0.3 時
   標記 `stress_trustworthy=false`。**教訓延續:無真實場時別用未校準合成場當 gate;先用藝術家真值自校準。**

## 可重現

```
export PYTHONPATH=tools/mesh_gen
python3 tools/mesh_gen/compare_award_mesh.py            # 3 件 all_pass, exit 0
# 迴歸(窗簾 strip 不受影響):
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left  --name image/curtain_left
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/shadow2       --name image/shadow  # 共用 region
```

## 對 pipeline 的意義

- S3 生成器現對**兩種拓樸類別**(strip 窗簾 + blob 機器人件)皆對真實生產 mesh 收斂 → 生成器泛化性驗證再進一步。
- 與 S4(PSD 切件 ⇄ Award slot 逐件吻合)串起來:**「PSD 圖層 → 切件 → 生成 mesh」對真實標的端到端**,
  差最後一哩「件→Spine attachment JSON 組裝(SkelToJson)」即可端到端產出可載入 spine(下一個 bounded chunk)。

## 未決 / 下一步

- deform 品質對這 3 件無法用真值閘(無 deform timeline);若要驗其變形,需一個「骨骼/權重驅動」的
  變形模型或真實含 deform 的 blob 件。目前以靜態覆蓋 + 靜態拓樸為可信閘。
- 下一步建議:**SkelToJson 組裝器**(把切件 + mesh/region 分派 + `<PSD檔名>/<圖層名>` 命名 + size+2px
  固化成寫出工具),對照 Award 結構自驗,完成 S3+S4 端到端。
