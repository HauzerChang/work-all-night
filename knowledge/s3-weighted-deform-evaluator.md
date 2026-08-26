# S3 — weighted-mesh deform 評估器(LBS 骨骼驅動變形閘)

- **結論**:補上 S3 唯一未驗維度的**前置閘**——「weighted mesh 在骨骼拉扯下的變形品質」。
  新增 `tools/mesh_gen/skinning_eval.py`:一支 **Spine 3.8 pose 引擎 + Linear Blend Skinning** 評估器,
  能對任一 weighted mesh(vertices=`[n,boneIdx,bindX,bindY,w,...]`)在任一動畫任一時刻算出變形後世界頂點,
  再下幾何品質閘(自交/翻面/退化/面積比 + 平滑度 edge_cv/area_cv)。
  閘用 `validate_weighted_deform.py` 對 Award 7 個真實美術 weighted mesh **雙向自驗**:
  **正對照 7/7 自一致、負對照 7/7 抓到破壞** → 閘可信。
- **信心**:高。pose 引擎在 5/7 件產出「setup 下 si=0 flips=0」且真實動畫下拓樸乾淨;
  負對照(交換相鄰頂點骨綁定)全被抓到(身體件單獨測 si 0→669);視覺 wireframe 疊圖確認為
  coherent skinning(非亂數)。
- **階段**:第 2 階段 / S3(候選 2 的**第一個 bounded chunk**:先有變形閘,才能自主收斂 weighted+BBW 生成)。

## 標準指令
```
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/validate_weighted_deform.py   # 7/7+7/7 → exit 0
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/skinning_eval.py assets/Award.json  # 逐件基準線
```

## Pose 引擎(對照 Spine runtime,normal transform mode)
- 每骨 setup 局部值(x,y,rotation,scaleX/Y,shearX/Y;JSON `null`→預設 0/1/0)。
- world 合成沿父→子:`la=cosDeg(rot+shX)·sx  lb=cosDeg(rot+90+shY)·sy  lc=sinDeg(rot+shX)·sx  ld=sinDeg(rot+90+shY)·sy`;
  `a=pa·la+pb·lc … wx=pa·x+pb·y+p.wx`。
- 動畫疊加:`rot+=rotate.angle  x+=translate.x  y+=translate.y  sx*=scale.x  sy*=scale.y`;shear 同理。
- LBS:`world_vertex = Σ_i w_i·(boneWorld_i ⊗ (bindX_i,bindY_i))`。
- **取樣誠實界定**:keyframe 時刻精確;相鄰 keyframe 間**線性內插 bone 參數**細分。線性值必落在兩端
  keyframe 凸包內 → 涵蓋與真實 bezier 相同值域,對「拓樸撐不撐得住」的幾何閘足夠(不精確重現緩動)。

## ⚠️ 核心校準教訓:絕對「si==0 & flips==0」對 weighted 角色 mesh **miscalibrated**
初版用絕對零閘,`_checker_validated=False`——**7 件美術真值有 2 件自己就非零**。逐幀定位(全在**精確
keyframe 時刻**,非內插假象)後確認引擎正確、是**閘定義錯**:

| 件 | 真實動畫下 worst | 原因(出貨且視覺正常) |
|---|---|---|
| 機器人拆件/身體、左手、OMG、mega1/2 | si=0 flips=0 | 硬件,乾淨 |
| **機器人拆件/光暈** | si=71 flips=7 | **軟邊發光** mesh,被展開的 4_LEG3~6 拉扯必然自重疊(additive 混色,無破) |
| **superwin_角色** | si=76 flips=12 | (a) `2_SUP2` 在 Super_In **t=0 有 scale=0.396 蓄力擠壓**(area_ratio→0.14,微小不可見) (b) idle loop 一撮 sliver 三角(setup 面積 −12~−18 的摺疊細節區,tri#103)會翻面 |

→ 這些都是**美術刻意/可接受**的。絕對零閘會誤殺美術真值。**正解 = 校準式相對閘**
(`gate_against_baseline`):生成 mesh 的變形指標須「**不劣於該件美術基準線 + margin**」
(si/flips ≤ 基準、edge_cv/area_cv ≤ 基準·(1+margin)、area_ratio 不超美術包絡 ±margin)。
與專案既有哲學一致(compare_robot_mesh 用 IoU 美術基準 −0.03;deform_eval 用自一致性)。
**教訓延續**:又一次「絕對閾值 miscalibration」——真值本身就違反樸素直覺,閘必須錨在真值基準線。

## 為何這是 candidate 2 的正確第一步
STATE 候選 2(S3 weighted+內部取樣密度+BBW 權重)最終要「量化生成 weighted mesh 的變形平滑度
vs 美術」。依 RULES「每能力必配評估器」——**先有可信的變形閘,生成才有自主收斂的判準**。
本 session 完成閘 + 雙向可信度驗證;下一步才做「BBW 權重生成 → 對照基準線」。

## 真值資料(已備妥,下一步可直接用)
- 3 機器人 mesh 綁定:光暈←4_LEG3/4/5/6;左手←4_LEG5/9;身體←4_LEG3/7/8(2~3 骨/頂點)。
- 驅動動畫:`Award_Legend_In`(rotate/translate/scale keyframe)、`Award_Legend_Loop`。
- 視覺:`knowledge/figures/weighted_deform_lbs.png`(藍=setup / 橙=posed LBS,4 件皆 coherent)。

## 下一步候選(candidate 2 續)
1. **BBW/harmonic 權重生成**:對 S3 生成的 mesh 頂點,依骨骼位置算平滑權重(純 CPU,harmonic
   近似或 heat-diffusion),寫成 weighted vertices → 用本閘對照美術基準線判定變形品質。
2. **內部取樣密度控制**:身體美術 98v 有密集內部點服務變形平滑度;S3 boundary-dense 幾乎只有邊界
   → 加內部 Poisson/格點取樣密度旋鈕,量測 edge_cv/area_cv 是否逼近美術基準線。
