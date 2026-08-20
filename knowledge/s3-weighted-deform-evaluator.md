# S3 — weighted-mesh(骨綁蒙皮)變形評估器

- **結論**:補上 `s3-robot-mesh-vs-award.md` 誠實界定的唯一未驗維度 —— weighted mesh 靠**骨骼+權重**
  變形(非逐頂點 deform timeline),`deform_eval.py` 不涵蓋。新建
  `tools/mesh_gen/weighted_deform_eval.py`:Spine 3.8 **normal-mode 前向蒙皮**(forward skinning)
  + 沿用 `deform_eval` 的拓樸閘(自交/翻面/退化)。對 Award 機器人 3 個真實美術 weighted mesh
  **評估器可信度驗證 PASS**(`evaluator_validated: true`)。
- **信心**:高。蒙皮數學經**獨立正確性錨**佐證(非自我循環):setup 包圍盒主軸 ≈ region 尺寸。
- **階段**:第 2 階段 / S3(評估器樞紐:先有 weighted 變形閘,才能自主收斂 weighted mesh 生成)。
- **工具**:`tools/mesh_gen/weighted_deform_eval.py`(可重現)。

## 標準指令

```
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/weighted_deform_eval.py   # evaluator_validated → exit 0
```

## 評估器設計(兩段)

1. **前向蒙皮**:`world_transforms(bones,pose)` 依 Spine `Bone.updateWorldTransform`(normal mode)
   由 bones 陣列算每根 world 仿射 `(a,b,c,d,wx,wy)`;`skin_vertices` 對 weighted 頂點
   (格式 `[boneCount,(boneIdx,bindX,bindY,weight)*bc,...]`)做 `Σ_j w_j·(bone_j.world · bind_j)`。
   pose = 在 setup local 疊加的 `{boneName:{rotate,x,y,scaleX,scaleY}}`(對齊 Spine 動畫偏移語意)。
   ⚠️ 僅支援 **normal** transform mode;Award 全 normal(已檢查),非 normal 需擴充。
2. **拓樸閘**:重用 `deform_eval.eval_pose`(self_intersections / triangle_flips / degenerate,
   相對 setup 判定)。

## 可信度驗證(為何可信,非只是「跑得出數字」)

evaluator_validated = **(A) 蒙皮正確性錨** ∧ **(B) 折疊偵測力**:

### (A) 正確性錨(獨立佐證,非自我循環)
| 件 | 權重和=1 | setup 拓樸乾淨 | setup bbox 主軸 / region | 判定 |
|---|---|---|---|---|
| 光暈 | ✓ | ✓ (0/0/0) | 692.9 / 708 = **0.98** | PASS |
| 左手 | ✓ | ✓ (0/0/0) | 257.0 / 259 = **0.99** | PASS |
| 身體 | ✓ | ✓ (0/0/0) | 401.3 / 427 = **0.94** | PASS |

bbox 主軸 ≈ region 尺寸 是**外部真值**:若 Y-up / 旋轉 / scale 繼承算錯,蒙皮出的形狀尺度/朝向會偏,
比值不會落在 [0.85,1.1]。左手 0.99、光暈 0.98 幾乎精確 → 蒙皮數學正確。

### (B) 折疊偵測力(calibration-free)
`break_angle`:繞 setup 對驅動骨兩方向逐度旋轉,回報**首次破壞角**。setup(0°)乾淨 → 無假陽性;
每件都有**有限**破壞角(<90°)→ checker 確實會抓折疊,非靜默放行。

| 件 | 驅動骨(權重占比) | smooth 破壞角 | hard-partition 破壞角 |
|---|---|---|---|
| 光暈 | 4_LEG6 (38.1) | 7° | 3° |
| 左手 | 4_LEG9 (9.2) | 24° | 90°(不破) |
| 身體 | 4_LEG7 (12.0) | 31° | 31° |

> ⚠️ 避開 `deform_eval.stress_field` 的教訓:**不用人為位移場幅度當閘**(mag miscalibration 會假性失敗);
> break-angle 是無需校準的相對量。

## 關鍵發現(誠實界定)

1. **「平滑權重一定比硬指派耐變形」是錯的 —— 依驅動骨影響力而異**:
   - 光暈(驅動骨占比 38%):smooth 7° > hard 3°(平滑確實較耐)。
   - 身體(驅動骨占比 12%):兩者同為 31°(驅動骨影響區小,差異被稀釋)。
   - 左手(驅動骨占比 9%):**hard-partition 反而永不破壞** —— 硬指派把幾乎所有頂點歸給主骨
     (4_LEG5 71%),移除了小影響骨的混合 → 該件近乎剛體、旋轉小影響骨動不了它。
   → 故 smooth/hard 破壞角列為**資料**,不當通用 pass/fail 閘。此發現本身校正了直覺。
2. **驅動骨選擇很重要**:須選「parent 也在該件用骨集合、權重占比最大」的子骨才製造相對運動;
   選到微權重骨(如光暈的 4_LEG4 占 1.2%)會讓對照失效(旋轉幾乎不動)。
3. Award 這 3 件皆 weighted 且**無 deform timeline** → 只能用骨骼 pose 驅動變形,正好是本評估器的用途。

視覺證據:`knowledge/figures/weighted_deform_eval.png`(每列一件:setup / smooth@破壞角-1(乾淨)/
hard-partition@同角(自交紅線))。

## 用途 / 下一步

- **這是 weighted mesh 生成的自我品質閘**:未來 S3 產生 weighted mesh(內部取樣密度 + BBW 權重)後,
  用同一支對「相同驅動骨 pose」比對 —— 生成件的破壞角應 ≥ 美術件、setup bbox 對齊、拓樸乾淨。
- 下一 bounded chunk 候選:**BBW 權重生成器**(對 S3 生成的 mesh + 骨架,解 bounded biharmonic
  → 平滑權重),用本評估器驗其變形品質對齊美術基準。純 CPU(scipy 稀疏解)。
- 限制:僅 normal transform mode;IK/約束/mesh 自帶 deform 疊加未處理(Award 這 3 件不需)。
