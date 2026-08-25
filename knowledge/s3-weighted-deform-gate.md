# S3 — weighted-mesh 骨骼變形平滑度閘(補上唯一未驗維度)

- **結論**:建立並**驗證可信**了「weighted mesh 靠骨骼蒙皮變形」的品質閘。先前
  `compare_robot_mesh.py` 只驗**靜態**覆蓋率 IoU,STATE 明列唯一未驗維度=「weighted mesh
  骨骼變形平滑度」。本次用 Python 重現 Spine 3.8 蒙皮(`spine_skin.py`),對 Award 機器人
  3 個 weighted mesh 件施加**真實動畫 bone pose**,量化拓樸品質 → **評估器三段驗證全 PASS**
  (`evaluator_trustworthy: True`)。
- **信心**:高。蒙皮數學由「真實旋轉下藝術家 mesh 全程乾淨」反證;負對照(硬綁最近骨)
  在藝術家仍乾淨的振幅下即破裂 → 有鑑別力(非永遠 pass)。
- **階段**:第 2 階段 / S3(里程碑:補齊 weighted mesh 變形驗證,S3 對真實美術 mesh 的
  最後一塊拼圖)。
- **工具**:`tools/mesh_gen/spine_skin.py`(蒙皮)、`weighted_deform_eval.py`(閘)、
  `geom_fast.py`(向量化幾何檢查)。

## 標準指令

```
python3 tools/mesh_gen/weighted_deform_eval.py     # 3 件全 piece_pass → exit 0(~24s)
```

## 量化結果(對 assets/Award.json 真值)

| 件 | nv | 綁定骨 | AC_setup | AC_loop_clean | AC_discrim(鑑別振幅) | procrustes_rms(setup vs uv) |
|---|---|---|---|---|---|---|
| 光暈 | 78 | 4_LEG3~6 | ✅ | ✅ area[0.997,1.002] | ✅ ×5 hardbind si=2 | 0.0147 |
| 左手 | 80 | 4_LEG5,9 | ✅ | ✅ area[0.975,1.0] | ✅ **×1(real)** si=6/fl=3 | 0.0868 |
| 身體 | 98 | 4_LEG3,7,8 | ✅ | ✅ area[1.0,1.001] | ✅ ×2 si=6/fl=3 | 0.0533 |

視覺證據:`knowledge/figures/s3_weighted_deform_gate.png`(左=藝術家權重乾淨 / 右=硬綁最近骨,
紅=自交邊;身體 Legend_Loop ×3,artist si=0 vs hardbind si=17,破裂集中在 4_LEG7/8 骨界)。

## 關鍵發現

### 1. **In/Out ≠ 變形品質訊號;Loop 才是穩態平滑真值**(校準原則)
一開始用**合成 graded 旋轉**當 pose → 藝術家 mesh 自己就自交(誤判)。改用**真實動畫 bone
timeline**後發現:
- **In/Out(入/出場)**是整體 squash/pop 過場:光暈 `Legend_In` **t=0 就 si=71**、
  `Legend_Out` 縮到 area **0.169**(消失)。原始 mesh 幾何本就自交,是藝術家可接受的極短過場
  (視覺被遮/動態模糊掩蓋)→ **不是 mesh 品質訊號**。
- **Loop(穩態律動)**才是「變形平滑度」該乾淨處 → 4 支 `*_Loop` 對 3 件**全程 0 自交/翻面/退化**。
- 教訓延續 RULES.md 警告「變形閘用**真實**位移場、不要用未校準 stress_field」:此處把該原則
  推廣到**骨骼 pose**——pose 也要來自真實動畫,且要**分辨過場 vs 穩態**。閘只對 Loop 下 must-be-clean,
  In/Out 僅報告。

### 2. Spine 3.8 蒙皮重現(`spine_skin.py`)
- Bone world transform:`normal` mode(無 shear/skeleton scale);`rotY=rot+90`;
  `a=pa*la+pb*lc; b=pa*lb+pb*ld; c=pc*la+pd*lc; d=pc*lb+pd*ld`;root a=1,d=1。
- weighted vertex world:`P=Σ_bone w·(a·bx+b·by+worldX, c·bx+d·by+worldY)`。
- 動畫 override 語意(3.8 JSON,相對 setup 的 **delta**,與蒙皮 override 疊加語意一致):
  `rotate.angle`=+deg、`translate.x/y`=+offset、`scale.x/y`=**乘數**(對 1 內插)。
  ⚠️ 目前**線性內插**忽略緊湊 bezier(`{curve,c2,c3,c4}`);keyframe 上為精確值,幀間為近似
  (對 Loop 乾淨判定不影響——已用 sub=3 取樣核對)。

### 3. 負對照設計:硬綁最近骨(hard nearest-bone)
把每頂點改綁「setup 世界座標最近的綁定骨」單骨 w=1(bind local=該骨逆變換×頂點世界座標),
施同 pose → 骨界不連續造成撕裂。**在藝術家仍乾淨的最大振幅下硬綁即破** = 閘有鑑別力。
各件鑑別振幅不同(左手 real 即破、身體 ×2、光暈 ×5)反映其 Loop 運動幅度差異。

### 4. procrustes_rms(setup 蒙皮 vs uv 幾何)僅診斷、非閘
光暈 0.015(mesh≈其貼圖 uv 的相似變換),但左手 0.087、身體 0.053 → **這兩件的 setup mesh
幾何與其貼圖 uv 並非純相似**(藝術家將 mesh 相對貼圖做了非相似擺放/形變)。這是美術決定,
不當 pass/fail,只作蒙皮 sanity 佐證(數值穩定、非爆量)。

### 5. 效能:向量化幾何檢查(`geom_fast.py`)
`deform_eval` 的純 Python O(E²) 自交檢查太慢(身體單 sweep 22s)。`geom_fast.eval_pose_fast`
用 numpy 一次算完所有非相鄰邊對,**與 reference 數值一致**(990 poses 0 mismatch),身體單
sweep 22s→1.1s(~20×),全閘 ~24s 可每 session 重跑。

## 對 S3 生成器的意義(下一步)
閘已就緒且可信 → 現在可以:對一個件**生成自己的 weighted mesh**(內部取樣密度 + BBW/heat
權重綁到同一組骨),用本閘量化「我方 mesh 在同一 Loop pose 下是否同樣乾淨、鑑別振幅是否 ≥ 藝術家」。
這才真正閉合「weighted mesh 生成品質」的自主迴圈(本 session 只完成**閘**,生成端待下次)。

## 誠實界定
- 只驗**拓樸品質**(自交/翻面/退化/面積比),非像素級渲染對照(需 spine-webgl 實機,CDN 被擋)。
- bezier 內插為線性近似(keyframe 精確);對「Loop 乾淨」判定已足夠,做極端 In/Out 幀間分析時需補。
- 尚未生成我方 weighted mesh 與 BBW 權重——本 session 建立的是**評估器**(先閘後生成,符合 RULES
  「每能力必配評估器」)。
