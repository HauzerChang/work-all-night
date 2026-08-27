# Spine 3.8 變形數學 + 評估閘設計(spine-mesh-doctor 參考)

## 1. 兩種變形驅動

| 類型 | 驅動 | 判定 | 例 |
|---|---|---|---|
| **unweighted** | `deform` timeline 逐頂點加偏移 | `vertices.length == uvs.length` | 窗簾、陰影 |
| **weighted** | bone 動畫 + 骨綁權重 | `vertices.length != uvs.length` | 角色肢體、光暈 |

## 2. unweighted 變形(deform_eval)

`deformed_local[i] = setup[i] + offset[i]`(sparse offset 段補零對齊)。這是 attachment-local 空間,
足以判定拓樸(自交/翻面/面積),不受控制骨仿射影響。**正式閘用真實位移場轉移**(`transfer_deform_check`),
不用未校準的 `stress_field`(合成壓力會造成假性失敗 —— 這是踩過的教訓)。

## 3. weighted 變形(weighted_deform_eval)

- **格式**:`vertices = [boneCount, (boneIdx, bindX, bindY, weight)*bc, ...]`;bind 是**骨局部**座標。
- **bone world transform(transform="normal")**:
  local 2×2 仿射 `a=cos(rot+shx)·sx, b=cos(rot+90+shy)·sy, c=sin(rot+shx)·sx, d=sin(rot+90+shy)·sy` + 平移(x,y);
  `world = parent ∘ local`,沿 bones 陣列順序算(parent 必在 child 前)。
- **skinning**:`worldPos(v) = Σ_i weight_i · boneWorld_i.transformPoint(bindX_i, bindY_i)`。
- **timeline 套用**:translate/rotate **加**在 setup 局部值、scale **乘**;沿 parent 鏈重算 world。

## 4. ⚠️ 踩過的雷(閘已內建處理)

1. **scale timeline 缺 channel 預設 = 1**(translate/rotate 預設 0)。Spine 匯出省略 == 預設的 channel;
   誤把缺的 scale 當 0 → mesh 在某軸塌陷成一線 → **假性自交/翻面**。
2. **big-win『scale 從 0 彈入』≠ 拓樸缺陷**:In/Out reveal 首幀整體 scale→0,全 mesh 均勻收合;
   絕對面積閾值會把全部三角誤判 degenerate。改用**相對面積**(< 1e-4×同姿勢平均;整體收合時判 0)。
   self-intersection / flip 本就 scale-invariant。
3. **只支援 `transform="normal"`**;遇 IK/約束或其他 transform 模式會 raise(不靜默出錯)。

## 5. 依 attachment 語意分類 pass/fail(重要)

- **不透明結構件**(身體/肢體):要求 `self_intersections == 0`。
- **軟性加成件**(光暈 halo、additive 特效):容許自我重疊(混合下視覺無害),只記錄重疊幅度,不硬性 fail。
  實證:Award 光暈在 reveal 期真實自交 si=71,且發生在 **t=0 精確 keyframe**(非內插假象)—— 藝術家真值。

## 6. 閘可信度方法論(每能力必配評估器)

判定壞 mesh 前,先證閘可信:
- **正對照**:藝術家真值(main_draw 4 mesh / Award 3 robot mesh)用真實動畫驅動 → 全幀乾淨(si=0)。
- **負對照**:故意壞網格(打亂權重 / 放大動作 / 合成壓力)→ 必產生自交/翻面。
- 近剛體件用**放大動作**分離「好綁定 vs 壞綁定」(amp=4:藝術家 si=0 vs 打亂 si=54),使鑑別力不依賴資產動作大小。
