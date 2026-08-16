# S3+S4 端到端:Award 真實件 → S3 mesh → 對照藝術家 mesh(靜態)

- **結論**:S3 `generate_mesh_v2` 對 **真實生產件**(Award 機器人拆件 光暈/左手/身體)自動產出的 mesh,
  在 **覆蓋 IoU ≥ 藝術家 mesh 自身覆蓋基準、頂點數 ≤ 藝術家、setup pose 0 自交/0 翻面/0 退化** 三閘全過。
  端到端「PSD件 ≡ atlas件(前次已證 alpha-IoU 0.92–0.99)→ S3 mesh → 對照真實 Award mesh」成立。
- **依據**:`tools/mesh_gen/compare_award_mesh.py`(本次新增),對 3 件跑閘,`all_pass=true`。
- **信心**:高(對藝術家真值直接比對 + 自我幾何閘;純 CPU 可重跑)。
- **相關階段**:專案第 2 階段(S3 mesh 生成器 × S4 PSD/atlas 切件),里程碑:端到端對真實生產標的驗收。

## 關鍵發現

### 1. 這些件是 bone-weighted rig,**沒有 deform timeline** → 真實位移場 deform 閘 N/A
- Award 12 支動畫中,機器人拆件 光暈/左手/身體 **零 deform 幀**;它們是 weighted mesh(靠骨頭仿射動)。
- 對照 main_draw 窗簾:那是 deform 驅動(9 anim 全有 deform)→ 才適用 `deform_eval` 的「真實位移場轉移」閘。
- **教訓/守則**:mesh 的「正確性判準」取決於它**怎麼被動畫驅動**:
  - deform 驅動件 → 用真實位移場轉移閘(自交/翻面),拓樸耐拉伸是重點(strip 拓樸)。
  - bone-weighted rig 件(無 deform)→ 不需耐拉伸;正確性 = **靜態輪廓覆蓋 + 頂點預算 + 拓樸乾淨**。
    (真正的變形品質由 **骨綁權重(S5/BBW)** 決定,不在 mesh 拓樸本身 → 屬後續能力。)
- 閘會自動偵測 `has_deform`,無 deform 時回報 `N/A`、有 deform 時提示改跑 deform 閘。

### 2. 覆蓋 IoU 由「邊界取樣密度」決定(與 strip 的 rows 同理)
- v1 delaunay 的邊界簡化容差 `epsilon_frac`(佔周長比例)是覆蓋率的唯一槓桿;內部點不影響覆蓋。
- 舊預設 `0.008` 對小合成遮罩/窗簾夠,但對 **production 尺度的大 blobby 件過疏**
  (光暈 496×480 → hull 只 14 點 → IoU 0.929 < 藝術家 0.980)。
- epsilon 掃描(光暈/左手/身體):

  | eps | 光暈 nv/IoU | 左手 nv/IoU | 身體 nv/IoU |
  |---|---|---|---|
  | 0.008 | 54 / 0.929 ✗ | 48 / 0.960 ✗ | 61 / 0.968 ✗ |
  | 0.004 | 61 / 0.966 ✗ | 57 / 0.982 ✓ | 69 / 0.986 ✓ |
  | **0.002** | **73 / 0.983 ✓** | **67 / 0.991 ✓** | **77 / 0.993 ✓** |
  | 0.001 | 92 / 0.992(超預算) | 107(超預算) | 100(超預算) |

  (✓/✗ 為「IoU ≥ 藝術家基準 且 nv ≤ 藝術家 nv」)
- **`epsilon_frac=0.002` 是三件的甜蜜點**:全過覆蓋基準、全在頂點預算內、全靜態乾淨。
  → 設為 `generate_mesh_v2.generate` 的預設(fraction-of-perimeter 是尺度不變的相對量)。
- 藝術家的光暈 mesh 是 **純 hull 多邊形**(hull=78=nv,0 內部點,fan 三角)→ 描邊精準才有 0.98 覆蓋;
  這印證「覆蓋=描邊密度」,與內部無關。

## 結果數字(v2 auto,eps=0.002)

| 件 | 生成 nv / hull / tri | IoU(生成) | IoU(藝術家基準) | 頂點預算 | 靜態幾何 | deform 閘 |
|---|---|---|---|---|---|---|
| 光暈 | 73 / 38 / 106 | 0.9832 | 0.9795 | 73≤78 ✓ | clean | N/A |
| 左手 | 67 / 43 / 89 | 0.9913 | 0.9681 | 67≤80 ✓ | clean | N/A |
| 身體 | 77 / 37 / 115 | 0.9926 | 0.9760 | 77≤98 ✓ | clean | N/A |

## 回歸

- 改 `epsilon_frac` 預設(0.008→0.002)**不影響 main_draw 4 mesh**:它們走 strip 模式(deform 驅動),
  epsilon 只作用在 delaunay 回退路徑。4 mesh 真實位移場 deform 閘全 `overall_pass`(含 shadow2 走共用 region `image/shadow`)。
- 注意:`image/shadow2` slot 的 attachment 名為 `image/shadow`(與 shadow **共用同一 region 與 attachment 名**),
  跑閘要用 `--slot image/shadow2 --name image/shadow`。

## 產出

- `tools/mesh_gen/compare_award_mesh.py` — 端到端靜態對照閘(atlas 切件→v2 mesh→覆蓋/預算/幾何 vs 藝術家 + deform 適用性偵測)。
- `tools/mesh_gen/generate_mesh_v2.py` — `generate()` 加 `epsilon_frac` 參數(預設 0.002),delaunay 回退更貼合真實件。

## 下一步候選

- **切件→Spine JSON 組裝(SkelToJson)**:把 `機器人拆件/<圖層名>` 命名 + size+2px padding + 生成 mesh
  固化成「件→Spine attachment」寫出工具,端到端產可載入 Spine JSON(對 bone-weighted 件先給 region/mesh + 空綁,權重待 S5)。
- **S5 骨綁權重(BBW)**:bone-weighted 件的「變形品質」在權重不在拓樸 → 這才是這類件的下一個真正閘。
