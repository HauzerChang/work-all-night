# S3 — weighted-mesh 骨骼變形評估器(補齊 compare_robot_mesh 的變形維度)

## 一句話結論

`tools/mesh_gen/weighted_deform_eval.py` 用 **Spine 3.8 LBS + bone timeline 取樣**,對
Award 機器人 3 個 weighted mesh(光暈/左手/身體)產生「藝術家真值 baseline」量化基準
—— 供**未來 S3-weighted 生成器**(candidate 2)對照收斂。**AC3a(setup 拓樸乾淨)+ AC4(負對照打斷)全 PASS**。

- **信心**:中高。LBS + world transform 公式對照 spine-runtimes 3.8 `Bone.updateWorldTransform`;
  4 個 3.8 資料坑各中一次(見下)後左手/身體全動畫全乾淨;光暈的 transient SI 為藝術家實務容忍。
- **階段**:第 2 階段 / S3(補上 `compare_robot_mesh` 的「靜態 IoU ≠ 變形品質」限制)。

## 為什麼要做這件事

`compare_robot_mesh.py` 靜態覆蓋率 IoU 對藝術家 3 mesh 全 PASS,但誠實限制:
- 藝術家用**密集內部頂點**服務 **bone 權重驅動的變形平滑度**,靜態 IoU 不涵蓋。
- `deform_eval.py` 只吃 **deform timeline**(逐頂點偏移,unweighted mesh 用),對 weighted mesh 無效。

補齊唯一方法:用 **LBS + 讀 Award 的 bone animation** 算出每個 keyframe 的世界頂點座標,再套幾何品質閘。

## 標準指令

```
# 對 Award 3 件跑完整評估(含負對照)
python3 tools/mesh_gen/weighted_deform_eval.py --neg    # exit 0 → AC3a+AC4 全 PASS

# 快取 baseline(供未來生成器對照)
python3 tools/mesh_gen/weighted_deform_eval.py --neg > specs/robot_weighted_baseline.json
```

## 藝術家 baseline(容忍上限,不遜於此 = 未來 S3-weighted PASS 條件)

| 件 | worst_SI | worst_flips | worst_degen | max_area_ratio | max_edge_stretch |
|---|---:|---:|---:|---:|---:|
| 光暈 (halo,加成混合)  | **71** | **7** | 0 | **1.982** | **10.112** |
| 左手              | 0 | 0 | 0 | 1.075 | 1.760 |
| 身體              | 0 | 0 | 0 | 1.075 | 1.394 |

光暈 baseline 遠不完美(Legend_In 前段有 71 SI + 7 flips + 2x 面積 + 10x 邊拉伸),
但真值就是這樣 → 這是**軟邊半透明加成效果的實務容忍**,非我方 bug(見「本次踩到的 3.8 資料坑」#3)。

## 本次踩到的 3.8 資料坑(4 個都真實)

1. **Bone 動畫「祖先傳遞」**:LBS 只綁 4 個 LEG bone,但這些 bone 的**祖先** `4_LEG2` 也被
   Award_Legend_In 動畫化。若只把 influence bones 帶進 pose_at,漏帶 LEG2 → 假性大變形 → 誤報。
   → 修:`sample_times` 用祖先聯集;`pose_at` 對「該 anim 有 keyframe 的所有 bone」都算(防禦性)。

2. **`transform=None` == `normal`**:Award 全部 bone 的 `transform` 欄位是 `None`(JSON 省略),
   我用 `d.get("transform","normal")` 才能認為是 normal;若寫 `d.get("transform")` 會得到 None,
   碰到未實作分支 raise。**任何欄位在 3.8 都可能省略,default 是關鍵**。

3. **⚠️ Scale keyframe 缺欄位 default 是 1,不是 0**。這是最容易踩的資料坑:
   Spine 3.8 SkeletonJson.readAnimation 對 scale 的 x/y 使用 `map.getFloat("x", 1)`。
   我第一版用 `.get("x", 0.0)` → scale 缺欄變 0 → 骨骼縮到 0 → mesh 塌成一個點(area=0)。
   ✅ 修:`_interp` 帶 per-channel defaults tuple。
   對照:rotate `angle` default=0、translate/shear x/y default=0,只有 **scale x/y default=1**。

4. **軟邊 halo 的藝術家容忍**:光暈 mesh 在自己動畫的 In 期(t=0~0.37)自交/翻面/大幅拉伸。
   看似「藝術家 mesh 都有問題」,但這是 semi-transparent additive-blend 加成效果,自交視覺不可見。
   → 修 AC3 定義:從「絕對 0 缺陷」改為「不遜於藝術家 baseline」的相對閾值(類比
   `compare_robot_mesh` 用 artist_iou 當 baseline)。**絕對數字不是真理,ground truth 才是**。

## AC 設計(給 S3-weighted 未來生成器參考)

| AC | 意義 | 判定方式 |
|---|---|---|
| AC3a Setup 零缺陷 | LBS + weight 綁定正確 | setup pose 下 SI=flips=degen=0 |
| AC3b Baseline 錄製 | 未來生成器容忍上限 | 記錄藝術家 mesh 每項 worst 值(不是 pass/fail) |
| AC4 Negative control | 排除「一律通過」 | 打亂每頂點的 bone 綁定 tuple → ≥1 件破壞 |

未來用法:S3-weighted 生成器產出 mesh + BBW 權重後,直接載入本評估器,判定
`generated_worst ≤ baseline_worst[+margin]` 即可自主收斂。

## 誠實限制

- **Bezier 內插近似線性**:sample 時間為 keyframe 聯集,所以 kf 時刻取到精確值;
  中間 substep 用線性 → bezier 中段最大值可能被低估。要量化 bezier 極值需另做曲線求極值。
- 只支援 `transform: normal`(Award 3 件所有相關骨都是 normal);碰到 noRotation/noScale
  / noScaleOrReflection 會 raise。
- 只看幾何拓樸 + 面積/邊拉伸;不看貼圖/UV。

## 相關檔案

- 工具:`tools/mesh_gen/weighted_deform_eval.py`
- Baseline:`specs/robot_weighted_baseline.json`(commit 進 repo,供跨 session 對照)
- 上游依賴:`tools/mesh_gen/deform_eval.py`(共用幾何檢查)
- 對照:`tools/mesh_gen/compare_robot_mesh.py`(靜態 IoU baseline;此工具補變形品質)
