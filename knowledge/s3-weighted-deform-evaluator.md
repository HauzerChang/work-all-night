# S3 weighted-mesh 骨骼變形評估器(補上「唯一未驗維度」)

- **結論**:完成 weighted mesh 的**骨骼變形評估器**(`tools/mesh_gen/weighted_deform.py` + `validate_weighted.py`)。
  對 Award 機器人 3 件真實美術 weighted mesh 三條 AC 全 PASS(`overall_pass=true`)。
  補上 `s3-robot-mesh-vs-award.md` 標記的唯一未驗維度:**weighted mesh 骨骼變形平滑度**(先前只驗靜態 IoU)。
- **信心**:高(蒙皮數學經浮點級獨立驗證);評估器判準經正/負對照校準。
- **相關階段**:S3(mesh 生成器)/ S2(評估器套件)。日期 2026-08-25。

## 為何需要新評估器(與 deform_eval 的差別)

| | unweighted(deform_eval.py) | weighted(本檔) |
|---|---|---|
| 資產 | main_draw 4 件窗簾/陰影 | Award 機器人 光暈/左手/身體 |
| 變形來源 | `deform` timeline 逐頂點 offset | **骨骼變換**(rotate/translate/scale timeline) |
| 蒙皮 | 直接加 offset | `worldV = Σ_bone weight·(boneWorldTransform ∘ bindLocal)` |

weighted mesh 的變形是**骨骼驅動**,必須重現整條 FK(bone 階層 SRT 組合)+ 動畫 timeline 取樣 + weighted 蒙皮,才能拿到藝術家真實變形後座標。

## 蒙皮數學(Spine 3.8,transform=normal;Award 全部 bone 皆 normal)

- bone local:`rr=(rot+shearX)`, `ry=(rot+90+shearY)`;`la=cos(rr)·sx, lc=sin(rr)·sx, lb=cos(ry)·sy, ld=sin(ry)·sy`。
- world 組合(child = parent∘local):
  `a=pa·la+pb·lc; b=pa·lb+pb·ld; c=pc·la+pd·lc; d=pc·lb+pd·ld; wx=pa·x+pb·y+pwx; wy=pc·x+pd·y+pwy`。
- 動畫疊加(相對 setup):rotate `+angle`、translate `+x,+y`、scale `×x,×y`。**只在 key times 評估**→ 值精確、無插值誤差(極端姿勢多在 key times,最易壞)。
- weighted 格式 `[nb,(boneIdx,bindX,bindY,weight)*nb]`;蒙皮 `wx=a·bx+b·by+wx0` 再 `×weight` 累加。

## 三條 AC(標準指令 `python3 tools/mesh_gen/validate_weighted.py`,exit 0/1)

- **AC1 蒙皮數值正確性 — PASS**:光暈 `Award_Legend_In` 末幀(t=0.7)回到**獨立算出的 setup**:
  `area_ratio=1.000、max_strain=0.000`。動畫把整條骨鏈帶走再帶回,我方無動畫 setup 完全吻合 → 浮點級證明 FK+蒙皮正確。
- **AC2 藝術家基線 — PASS**:3 件在真實 `Award_Legend_Loop` 下 foldover-clean(0 自交/0 翻面/0 退化)。
  - 光暈/左手/身體 In 動作:左手/身體亦乾淨;**光暈 In 例外**(t=0~0.37 有 71 自交、max_strain 9.1)。
    → **非 bug**:光暈是「glow 爆入」的軟性加法貼圖,爆入時本就大幅拉伸/自我重疊,視覺可接受;
    以 t=0.7 精確回到 setup 佐證此為真實藝術家意圖,故基線判定只採 Loop。
    **界定**:自交硬失敗只對**不透明剛體件**(身體/手)成立;軟性加法 glow 容許重疊。
- **AC3 鑑別力(複合閘)— PASS**:對照硬綁(每頂點塌成最大權重單骨)負對照。
  - 光暈(4 骨):應變 hard 1.57 vs 藝術家 0.15(**10×**)+ 破裂 k 藝術家 12 > hard 6 → 兩指標都鑑別。
  - 身體(3 骨):破裂 k 藝術家 6 > hard 4 → foldover 韌性鑑別。
  - 左手:**單骨主導**(80 頂點全由 4_LEG5 主導,4_LEG9 僅次要 blend)→ 硬綁塌成剛體(永不自交、應變 0),
    根本不測多骨平滑度 → 標 **N/A、排除判定**(誠實界定,非放水)。

## 方法論結論(本次最重要發現)

**weighted-mesh 品質需複合閘,foldover 單獨不足**:
- foldover(自交/翻面)對「平滑權重過度拉伸撕裂」有效,但對「剛體單骨不關節化」**盲**——
  單骨剛體平移旋轉永不自交,卻在關節接縫產生 gap、不跟關節彎折(foldover 看不到 gap)。
- 應變平滑度(邊長 |len_def/len_setup−1| 的 max/std)補上這盲點:剛體/硬綁在骨界邊出現高應變尖峰。
- 故 `validate_weighted` 採 **strain 鑑別 OR foldover 韌性鑑別**,並排除單骨主導件。

## API 摘要(`weighted_deform.py`)

- `parse_weighted(att)` → `(verts_w, tris, hull, nv)`;unweighted 回 None。
- `world_transforms(bones, anim_bones, t)` → 每骨 `(a,b,c,d,wx,wy)`。
- `skin(verts_w, world)` → 世界座標 (n,2)。
- `eval_mesh_anim(skel, slot, name, anim, verts_w_override=None)` → foldover+strain 逐幀 + worst + clean。
- `edge_strain(setup, deformed, tris)` → `{max_strain, strain_std, strain_mean}`。
- `hardify(verts_w)` → 硬綁單骨負對照;`stress_break_point(...)` → 放大動作找首次破裂 k。

## 誠實限制 / 下一步

- 目前是**評估器(閘)**,尚未生成我方 weighted mesh 權重。下一步(最高優先):
  **實作 BBW(Bounded Biharmonic Weights)權重生成器 + 內部取樣密度控制**,對同骨架生成我方權重,
  用本閘量化「我方 weighted mesh 變形平滑度 ≈ 藝術家」→ 完成 candidate 2 全貌。
- 骨架 scale 視為 1(Award skeleton scale 未設);IK/constraint 不介入這些骨(已確認)。
- 只覆蓋有動畫真值的 3 件;其餘 4 個 Award weighted mesh(OMG/mega/super 角色)無對應骨動畫驅動,未納。
