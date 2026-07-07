# S3 端到端驗收:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(`光暈`/`身體`/`左手`)切出來,用 S3
  (`generate_mesh` v1 Delaunay)生成 unweighted mesh,對照 Award 真實生產 mesh 的**靜態覆蓋**與
  **頂點經濟性**,**3 件全 PASS**:生成 mesh 覆蓋 IoU **≥ 藝術家同件**,且**用比藝術家更少的頂點**達成。
  端到端「PSD art source → S3 topology → 真實生產標的」在**拓樸維度**打通(第一個對真實 big-win 主角驗收)。
- **信心**:高(對真實生產 spine 的藝術家 mesh 當真值 + 座標框一致性 sanity check + 幾何閘 + 自主收斂)。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:S3 首度對真實生產 mesh 驗收)。
- **工具**:`tools/mesh_gen/validate_against_award.py`(可重現;`python3 tools/mesh_gen/validate_against_award.py`)。

## 關鍵發現

### 1. Award 機器人 mesh 是**另一種 regime**:weighted / 骨骼驅動 / 無 deform timeline
main_draw 的 4 mesh 是 **unweighted + deform-timeline**(窗簾/陰影,逐頂點 deform)。
Award 的 3 件相反:

| 件 | Award type | 頂點 | hull | weighted | deform timeline |
|---|---|---|---|---|---|
| 光暈 | mesh | 78 | 78 | ✅(`len(verts)=570≠len(uvs)=156`) | ❌ 無 |
| 身體 | mesh | 98 | 40 | ✅(738≠196) | ❌ 無 |
| 左手 | mesh | 80 | 42 | ✅(556≠160) | ❌ 無 |

→ 這類 mesh 變形靠**骨骼+權重**,不是逐頂點 deform。故 `validate_against_real.py` 的
「真實位移場轉移」變形閘**不適用(N/A)**。能公平比對的維度 = **靜態覆蓋 + 拓樸經濟性**。

### 2. Spine mesh `uvs` 存於**邏輯 upright 空間**,與 atlas rotate 無關 → PSD 件是理想比對框
Award 中 `光暈`/`身體` 在 atlas **rotate=true**、貼圖被縮小打包 ~0.70(見 s4 doc),但 JSON 的
mesh `uvs`(區域局部 0..1)是在**未旋轉的邏輯 attachment 空間**(rotate 是 atlas 打包細節,load
時才套用)。實測:把藝術家 uvs 直接疊到**upright PSD 切件**上,覆蓋 IoU = **0.949/0.948/0.977**
(高)→ 座標框對齊確認。**因此不需處理 atlas rotate/0.70 縮放**,直接用乾淨的 PSD 件 alpha 當真值,
比 atlas_crop(縮小+derotate)更精確。(此為 `validate_against_award.py` 的 `frame_sanity` 閘。)

### 3. 生成 mesh 覆蓋率 ≥ 藝術家,且更省頂點(自主 eps 收斂)
覆蓋率由**邊界取樣密度**決定(呼應 v2 strip「IoU 由 rows 決定」)——這裡是 Douglas-Peucker 的
`epsilon_frac`。工具沿 `0.008→0.004→0.002→0.001` 自主收斂(≤5 輪),在「頂點 ≤ 藝術家」天花板內
取第一個「覆蓋達標 + 幾何乾淨」點:

| 件 | 生成 eps | 生成 IoU / 藝術家 | 生成 nv / 藝術家 nv | 幾何 |
|---|---|---|---|---|
| 光暈 | 0.002 | **0.9796** / 0.9486 | **64** / 78 | 0退化/0孤兒/重心在內 |
| 身體 | 0.008 | **0.9660** / 0.9477 | **60** / 98 | 乾淨 |
| 左手 | 0.004 | **0.9796** / 0.9768 | **70** / 80 | 乾淨 |

- 光暈 在 eps=0.004(nv=44)覆蓋已達標,但**重心在內比例 < 99%**(glow 凹形)→ 幾何閘擋下,
  自動續進到 eps=0.002(nv=64,乾淨)。閘正確運作。
- 3 件生成頂點數(64/60/70)全 < 藝術家(78/98/80)→「用更少頂點達到同等以上覆蓋」。

### 4. 端到端目前的缺口 = **BBW 權重**(不是拓樸)
S3 目前只產 **unweighted topology**;Award 3 件是 **weighted**。靜態拓樸已對齊生產,但要做到
「骨骼驅動變形 parity」,S3 需能**產出權重**(BBW = Bounded Biharmonic Weights,純 CPU)。
這是 S3 下一個明確能力(PLAN 已列「BBW 權重」)。

## 教訓 / 方法論

- **不同 mesh regime 要用不同閘**:deform-timeline mesh 用「位移場轉移」;weighted/骨骼 mesh
  該比對「靜態覆蓋 + 經濟性」(+ 未來:權重平滑度)。硬套錯閘會得到無意義的 N/A 或假訊號。
- **座標框先做 sanity check**:任何「疊真值到影像」的比對,先驗真值本身覆蓋率高(frame_sanity),
  否則量到的是框沒對齊的噪音(延續 evaluator 校準教訓)。
- **PSD 件 > atlas 件當真值**:art source 無縮小/derotate 插值誤差(s4 已證同素材,alpha-IoU 0.92~0.99)。

## 可重現

```
python3 tools/mesh_gen/validate_against_award.py          # 3 件全 PASS(exit 0)
python3 tools/mesh_gen/validate_against_award.py --margin 0.01   # 放寬覆蓋 margin
```

## 下一步

1. **S3 BBW 權重**:對生成 topology 算骨骼權重(需 Award 骨架 + bind pose),與藝術家權重比對
   (權重平滑度 / 骨骼影響區域 IoU)→ 補齊 weighted mesh parity(端到端最後一塊)。
2. **件→Spine JSON 組裝(SkelToJson)**:把「`PSD名/圖層名` 命名 + size+2px + mesh/region 分配」
   固化成寫檔工具,把生成 mesh 掛回 Spine JSON。
