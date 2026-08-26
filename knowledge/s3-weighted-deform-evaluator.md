# S3 — weighted-mesh 骨骼變形評估器 + 藝術家真值校準

> 補上前一里程碑(`s3-robot-mesh-vs-award.md`)明列的**唯一未驗維度**:
> weighted mesh「靜態覆蓋率 PASS ≠ 骨骼變形平滑度對等」。本次做出量測工具並用真值校準出容忍包絡。

- **工具**:`tools/mesh_gen/weighted_deform.py`(純 CPU;重用 `deform_eval.check/signed_area` 幾何閘)。
- **標準指令**:
  ```
  PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/weighted_deform.py assets/Award.json          # checker + benchmark
  PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/weighted_deform.py assets/Award.json --check   # 只跑可信度閘
  ```
- **信心**:高。可信度閘達機器精度;對 7 個真實生產 weighted mesh × 12 動畫全跑通。

## 這工具做什麼

weighted mesh 不靠逐頂點 `deform` timeline,而是**骨骼 world transform × 每頂點權重的線性混合(LBS)**。
`deform_eval.py` 只處理 unweighted 的逐頂點 offset,無法評 Award 的 7 個 weighted mesh(4 big-win 角色 + 機器人 3 件)。

管線:
1. `parse_weighted` — 解析 weighted 格式 `[骨數,(boneIdx,bindX,bindY,weight)×n]`;**每頂點權重正規化**(除以總和)。
2. `bone_setup`/`bone_order`/`world_transforms` — 重現 Spine 3.8 **normal-inherit** bone world transform
   合成(`a,b,c,d,wx,wy`;Award 全骨為 normal,無 shear/transform-mode)。
3. `pose_local` — 套 `rotate`(+angle)/`translate`(+x,y)/`scale`(×x,y)/`shear` timeline(相鄰 keyframe 線性內插)。
4. `skin` — LBS:`world_v = Σ w_k·(boneWorld_k 施於 bindLocal_k)`。
5. 幾何閘:`self_intersections`/`triangle_flips`/`degenerate` + **`flip_area_frac`**(翻面三角面積÷setup總面積,嚴重度)。

## 可信度閘(checker validation,不依賴外部真值)

| 閘 | 量測 | 結果 |
|---|---|---|
| 權重和 | 原始 JSON 每頂點 Σweight 偏差 | 1.0e-5(JSON 四捨五入到 ~5 位;正規化後精確 1) |
| **仿射協變** | 對所有骨 world 左乘同一剛體 R,skin 後每點應精確 = R·(原點) | **2.3e-13(機器精度)→ 證明 LBS 數學正確** |
| setup 合法性 | setup pose skin 出的 mesh 乾淨 | 7/7 mesh 0 自交/0 退化 |

> 關鍵校準教訓:未正規化時仿射協變誤差 = `(Σw−1)·T` ≈ 1e-5×12.5 ≈ 1.25e-4(**完全對得上**),
> 證明殘差純來自 JSON 權重精度、非數學 bug。正規化(runtime 近似依賴之)後降到機器精度。
> 另一自洽證據:Legend_In 的 settle 幀(t=0.5~0.7)位移回到 ≈0、自交回到 0 → bone chain 對齊 setup。

## 🎯 藝術家真值校準包絡(本次最重要產出)

對 7 mesh × 其驅動動畫跑「最壞姿勢」翻面嚴重度(`flip_area_frac`):

| 類型 | mesh(nv/hull) | 最大位移 | 最大 area 比 | max 自交 | **max flip_area_frac** |
|---|---|---|---|---|---|
| **實心(有內部頂點)** | OMG 69/48、megawin1 38/29、megawin2 50/33、左手 80/42、身體 98/40 | **238~328px** | 1.33 | **0** | **0.0000** |
| 實心(有 sliver 內三角) | superwin 112/56 | 363px | 1.31 | 76 | 0.0074(0.7%) |
| **邊界唯一(additive glow)** | 光暈 78/**78**(hull=nv) | 627px | 1.98 | 71 | 0.1386(13.9%) |

視覺:`knowledge/figures/weighted_deform_calibration.png`(灰=setup、藍=最壞變形、紅=翻面三角)。

### 三個結論(直接回答上一里程碑的開放限制)

1. **內部頂點密度 = 變形平滑度槓桿(實測證實)**:5 個「有內部頂點」的實心角色 mesh,即使被骨骼拉到
   **300px+ 位移、面積縮到 10%~脹到 133%**,仍 **0 翻面、0 自交**。這正是上次 `s3-robot-mesh-vs-award.md`
   推測「美術用密集內部頂點服務骨骼變形」的**量化證明** —— 內部取樣讓 LBS 局部近似仿射,不折疊。

2. **二元「0-fold」閘對 weighted mesh 是錯的**:藝術家自己的真值也非全乾淨 —— superwin 有一個 sliver
   內三角在細微 loop(~20px)就翻面(視覺無感,0.7%)。→ 正確閘是 **`flip_area_frac` 嚴重度**,非計數。

3. **mesh 類別決定閘**:邊界唯一的 additive glow(光暈)在 intro 爆發(骨 scale 1.667×)自交 13.9%,
   但**加法混合下自交視覺無害** → glow/halo 類**不套折疊閘**;實心角色類才套。

### 建議校準門檻(供後續評 S3 自產 weighted mesh)

- **實心角色 weighted mesh**:`flip_area_frac ≤ 0.01`(藝術家真值最壞 0.0074,留 margin)跨所有驅動動畫。
- **additive glow/halo**:折疊閘 N/A(自交預期且無害);只驗靜態覆蓋率(見 `compare_robot_mesh`)。

## ⚠️ 誠實界定

- timeline 曲線用**線性內插**近似(在 keyframe 上精確;bezier easing 幀間為近似)。已驗:折疊在**精確
  keyframe** 上就出現(非內插假象),故不影響上述判定。
- 只驗**幾何拓樸**(折疊/自交/面積),未驗貼圖 UV 拉伸的視覺觀感(那是主觀項,留使用者)。
- 校準真值 = Award 這批 mesh;門檻 0.01 為單資產推估,收到更多生產 spine 可再收斂。

## 下一步候選

- **S3 自產 weighted mesh + BBW 權重**:用本評估器當閘 —— 生成「含內部取樣密度控制」的 mesh、
  用 BBW(bounded biharmonic weights,scipy 純 CPU)綁到 Award 骨架,對同一批動畫跑 `weighted_deform`,
  要求實心件 `flip_area_frac ≤ 0.01`。真值(權重/骨架/動畫)全在 `Award.json`。
- 把「內部取樣密度」接進 `generate_mesh_v2`(目前 boundary-dense 幾乎無內部點 → 不適合 weighted 件)。
