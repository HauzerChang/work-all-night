# S3 端到端:機器人件 → mesh → 對照 Award 真實 weighted mesh

- **結論**:S3 生成器對 Award 三個機器人 mesh 件(光暈 / 身體 / 左手)**端到端靜態 IoU 全過藝術家基準**
  (0.9832 / 0.9926 / 0.9913 ≥ 0.9795 / 0.9760 / 0.9681),頂點數比藝術家精簡(73 / 77 / 67 vs 78 / 98 / 80)。
  但**發現真實件是 weighted(骨骼驅動)、無 deform timeline**,現有位移場轉移閘不適用 → 需新的
  **bone-driven deform 閘**才能判定變形穩健性(下一步)。
- **依據**:`validate_against_real.py --skeleton assets/Award.json --slot 機器人拆件/<件> --gen v2`,
  atlas 切件(Award.png/Award2.png 雙頁)→ `generate_mesh_v2`(auto→有機件走 Delaunay-v1 回退)→
  IoU vs 藝術家 mesh uvs 覆蓋率。信心:高(有生產真值對照,3 件一致)。
- **相關階段**:第 2 階段 S3(mesh 生成器)× S4(切圖)端到端串接;對照真實生產標的。

## 兩個關鍵發現

### 1. Award 機器人 mesh 件是 weighted / 骨骼驅動(新 regime)

| 件 | 型別 | uvs(頂點) | vertices(攤平) | hull | 三角 | deform timeline |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | mesh **weighted** | 78 | 570 | 78(全周,無內部) | 76 | **無** |
| 機器人拆件/身體 | mesh **weighted** | 98 | 738 | 40 | 154 | **無** |
| 機器人拆件/左手 | mesh **weighted** | 80 | 556 | 42 | 116 | **無** |
| 機器人拆件/右手 | region | – | – | – | – | – |
| 機器人拆件/頭 | region | – | – | – | – | – |

- 對比 main_draw 的 4 個 mesh:那些是 **unweighted + deform timeline 驅動**(窗簾在 9 支動畫全有 deform)。
- Award 這 3 件相反:**weighted(`vertices.length != uvs.length`)**,靠骨骼權重變形,**12 支動畫全部 0 個 deform timeline**
  觸及這些 slot(已掃描確認)。光暈 hull=nv=78 → 純外周環(glow halo),無內部頂點。
- **意涵**:S3 生成器目前產 **unweighted** mesh。要在生產中替換 weighted 藝術家 mesh,需再補
  **權重指派(BBW,路線圖 S3 的一環)**;而要「像真實那樣變形」測穩健性,得先能**算骨骼驅動的世界變形**。

### 2. v1 Douglas-Peucker epsilon 0.008 對有機件過度簡化 → 已修為 0.002

- 初測(eps=0.008):3 件 IoU 0.9292 / 0.9680 / 0.9602,**全落在藝術家基準下**(hull 只 14 / 21 / 18 點)。
- IoU 由邊界取樣密度決定(呼應 s3-four-mesh-generalization 的「rows 決定 IoU」)。epsilon 掃描:

  | eps | 光暈 IoU | 身體 IoU | 左手 IoU | 全過基準? |
  |---|---|---|---|---|
  | 0.008 | 0.9264 | 0.9702 | 0.9602 | ✗(3 件皆低於) |
  | 0.004 | 0.9615 | 0.9858 | 0.9816 | ✗(光暈低) |
  | **0.002** | **0.9832** | **0.9926** | **0.9913** | ✓(**光暈為 binding constraint**) |
  | 0.001 | 0.9924 | 0.9946 | 0.9963 | ✓ 但頂點多(118 / 120 / 139,超藝術家預算) |

- **修正**:`generate_mesh.py` 預設 `epsilon_frac` 0.008 → **0.002**(hull 密度 37~43,近藝術家)。
- **回歸驗證(不破壞既有)**:
  - `curtain_left` v1:eps=0.002 下 IoU 0.9946↑、**deform 仍乾淨(si=0/flips=0)** → epsilon 變更 deform-neutral。
  - `curtain_right` v1:eps=0.008 與 0.002 **都**自交(si=19→15) → 屬 v1 已知不通用(由 v2 strip 覆蓋),非本次回歸。
  - main_draw 4 mesh 走 **v2 strip**,不經 v1 回退 → 完全不受影響(strip IoU 0.9338/0.9335/0.9549 不變,deform 全乾淨)。

## 工具異動

- `generate_mesh.py`:`epsilon_frac` 預設 0.008→0.002(含註解與 Award 校準依據);argparse `--epsilon` 同步。
- `validate_against_real.py`:對 **weighted / 無 deform timeline** 標的,`AC_real_deform` 誠實標
  `status:"n/a"`(補零位移場會得 setup pose 的假性 clean);`overall_pass` 僅取 IoU;新增 `target`
  欄回報 weighted / 藝術家頂點數 / hull。

## 標準指令(可續跑)

```
python3 tools/mesh_gen/validate_against_real.py \
  --skeleton assets/Award.json --atlas assets/Award.atlas --png assets/Award.png \
  --slot 機器人拆件/光暈 --name 機器人拆件/光暈 --gen v2   # 身體 / 左手 同
```
→ 3 件 `overall_pass=true`(IoU 過基準;deform 閘 n/a 待補)。

## 下一步(bone-driven deform 閘 —— 本次揭示的缺口)

要真正判定 weighted 件的變形穩健性(不重蹈「靜態≠變形穩健」),需分解建置:
1. **setup-pose weighted skinning**:解析 weighted vertices `[骨數, boneIdx,bindX,bindY,w, ...]`,
   由骨骼 setup 世界變換算世界座標;自驗:重建世界頂點 ↔ uvs 空間排列吻合(affine 殘差低)、0 自交。
2. **動畫骨骼 TRS timeline 求值**(rotate/translate/scale + 緊湊 bezier + 階層合成)→ 極端幀骨骼世界變換。
3. **weighted deform 轉移閘**:把藝術家權重以 UV barycentric 轉移到生成 mesh 頂點 → 套真實骨骼變換
   → 檢自交/翻面。這是 unweighted `transfer_deform_check` 的 weighted 類比。
