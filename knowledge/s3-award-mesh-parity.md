# S3 端到端驗收 — PSD件 → 生成 mesh → 對照 Award 真實生產 mesh(有藝術家真值)

- **結論**:S3 生成器對真實生產 spine(Award)的 3 個 mesh 件(光暈/身體/左手)達成**藝術家真值 parity**
  ——生成 mesh 覆蓋 IoU ≥ 藝術家 mesh 的 IoU(margin 0.02),且**頂點數更精簡**、拓樸乾淨(0 退化/0 孤兒/
  質心全在遮罩)。這是專案第一個「有藝術家 ground truth 可比」的 S3 端到端驗收(main_draw 4 mesh 無真值對照,
  只有藝術家自身 IoU 當基準)。
- **信心**:高(對真實生產檔 + 藝術家 mesh 交叉比對;atlas 與原生 PSD 兩來源皆過;正/負向皆有量化)。
- **階段**:第 2 階段 / S3(里程碑:合成 → main_draw → **真實生產標的 parity**)。
- **工具**:`tools/mesh_gen/compare_award_mesh.py`(整合 AC);`generate_mesh.py` 新增自適應細化。

## 標的(Award,機器人拆件)

3 件在 Award 為 **weighted mesh** 且**無 deform timeline**(變形靠骨骼+權重,非逐頂點 deform):

| 件 | slot/attachment | 藝術家 mesh | region(atlas,0.70 縮放) |
|---|---|---|---|
| 光暈 | `機器人拆件/光暈` | 78v / 76t / **hull=78(全邊界,無內點)** | 496×480 |
| 身體 | `機器人拆件/身體` | 98v / 154t / hull40 | 267×299 |
| 左手 | `機器人拆件/左手` | 80v / 116t / hull42 | 181×152 |

**deform 閘為何 N/A**:這 3 件無 deform timeline,`deform_eval.real_deform_field` 不適用。逐頂點拓樸
穩健由靜態 well-formed 閘(evaluate_mesh 退化/孤兒/質心)把關;真實變形品質屬骨骼權重範疇(未來 S5)。

## 關鍵發現

### 1. Spine mesh uvs 為 region-local 正規化(直接可用,不需 v-flip)
`uvs` 是 0..1 over attachment region(經驗證:main_draw curtain 與 Award 左手 span≈[0,1])。`atlas_crop.extract()`
已把 rotate 件轉回原方向,故 `uv*(W,H)` 直接對應 extract 出的遮罩。實測 direct IoU 0.97 vs v-flip 0.44–0.60
→ **direct 才對**。旋轉件(光暈/身體 rotate:true)同樣成立。

### 2. 單一固定 `epsilon_frac` 對「大而平滑輪廓」取樣不足 → 加自適應細化
- 原 `generate_mesh` 用固定 Douglas-Peucker `epsilon_frac=0.008`。對大而平滑的光暈(近圓 blob,藝術家用
  **78 個全邊界點**描),只給 hull≈14 → IoU 0.929,**低於藝術家 0.9795 約 5pt**(身體/左手在 0.008 已 parity)。
- epsilon 掃描(對光暈):0.008→0.929, 0.004→0.966, **0.002→0.983**, 0.001→0.992。到 0.002 才追平藝術家。
- 但**全域直接調到 0.002 會爆頂點預算**(evaluate_mesh 預設 `vertex_budget=64`;光暈 0.002→73v、身體→77v)。
- **解法:自適應邊界細化**(`generate(..., target_iou=0.97)`)——由 epsilon 起逐步 ÷1.6 降容差,直到覆蓋
  IoU ≥ target 或頂點數超 `vertex_cap`(預設 128)或觸 `eps_floor`。`target_iou=None` = 原固定行為(**預設不變、
  無回歸**)。這把「頂點密度」交給客觀覆蓋目標決定,而非武斷常數。

### 3. parity 結果(target_iou=0.97, margin=0.02)

| 件 | 藝術家 v / IoU | 生成(atlas) mode / v / IoU / clean | parity | 預算(≤藝術家v) | 生成(PSD) v / IoU |
|---|---|---|---|---|---|
| 光暈 | 78 / 0.9795 | adaptive / 67 / **0.9772** / ✓ | ✓ | ✓ | 64 / 0.9796 |
| 身體 | 98 / 0.976 | adaptive / 68 / **0.9834** / ✓ | ✓ | ✓ | 67 / 0.9802 |
| 左手 | 80 / 0.9681 | adaptive / 53 / **0.9755** / ✓ | ✓ | ✓ | 66 / 0.9737 |

→ **overall_pass=True**。生成 mesh 覆蓋追平/超越藝術家,且**頂點數約為藝術家的 2/3**(更精簡)。
atlas 與原生 PSD 兩來源皆過 → 生成器對 atlas 0.70 縮放**尺度穩健**。切件保留 RGB 供 Canny 內部取樣
(初版誤把 mask 攤平成純白 → Canny 失效、內部只剩格點;已改餵真實切件影像)。

## 方法論(留痕)

- **有外部真值才叫真驗收**:main_draw 只能比藝術家自身 IoU;Award 讓我們比「生成 vs 藝術家 mesh」的相對品質。
- **客觀 criterion 交給評估器自適應**:與其猜 epsilon 常數,不如讓生成器朝覆蓋 target 收斂(對齊 RULES「客觀項全自主迭代」)。
- **改動最小化避免回歸**:自適應為 opt-in(`target_iou=None` 預設),main_draw 4 mesh + 合成測試重驗全綠。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/aw/psd_parts   # 先切 PSD 件
python3 tools/mesh_gen/compare_award_mesh.py                                       # overall_pass → exit 0
# 回歸:python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left
```

## 下一步

- 把「件 → Spine mesh attachment」慣例(`PSD名/圖層名` slot、mesh vs region 分配、+2px padding、
  region-local uv、自適應 target_iou)固化成 **SkelToJson 組裝工具**,端到端輸出可載入 Spine JSON(候選 #2)。
- weighted mesh 的**權重生成**(BBW)尚未做:目前生成 unweighted;Award 真值為 weighted。要完整對齊生產,
  需 S3 權重階段(接 S5 骨架)。此為已知缺口,非本次範圍。
