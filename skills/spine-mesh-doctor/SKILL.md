---
name: spine-mesh-doctor
description: |
  對 Spine 2D mesh(attachment)做**量化變形品質體檢**:給 pass/fail + 數字,而不只是畫線框。
  純 CPU、無需 Spine editor、無需貼圖(PNG)即可判定拓樸是否耐變形。

  Use when the user wants to:
  (1) 判定一個 mesh(unweighted deform 或 weighted 骨綁)在動畫拉扯下**會不會破**(自交/翻面/塌陷);
  (2) 拿新生成 / 改過的 mesh 與**藝術家真值**對照變形品質(不是只看靜態長得像);
  (3) 為 mesh 生成器 / 權重綁定建**自動品質閘**(CI 式回歸,防改壞);
  (4) 量化 weighted mesh 的骨綁變形平滑度(內部取樣密度 / BBW 權重評估的前置閘);
  (5) 靜態輪廓吻合度(IoU)+ 頂點預算檢查。

  觸發詞:「mesh 會不會破」「變形品質」「weighted mesh」「骨綁變形」「自交」「翻面」「mesh 體檢」
  「mesh 品質閘」「變形平滑度」「mesh IoU」「mesh 頂點預算」「這個 mesh 撐得住嗎」。

  Requires: Python 3 + numpy(靜態 IoU 另需 opencv-python-headless)。輸入:Spine 3.8 JSON(+可選遮罩 PNG)。
---

# spine-mesh-doctor

把「這個 mesh 動起來會不會破？」從肉眼猜測變成**可量化、可回歸的 pass/fail**。

> **version: 0.1.0**（2026-08-27）
>
> Changelog：
> - **0.1.0** — 初版,固化本研究 repo 的 mesh 評估器套件(達 skill 化門檻:區塊 spine-mesh-doctor
>   所有核心能力 ≥ L2 GREEN、整合 AC 達 L3;見 repo `skills/READINESS.md`)。
>   含 3 支閘:靜態輪廓 IoU、unweighted 變形(真實位移場轉移)、**weighted 骨綁變形**(今日新增,
>   對 Award 機器人 3 mesh 真值 + 負對照雙向驗證)。
>
> **與 `spine-ai-editor` 的關係**:那支 skill 的 mesh 面板只做**可視化**(頂點/綁骨直方圖);
> 本 skill 做**量化判定**(pass/fail + 數字)。兩者互補:先用 doctor 判定會不會破,再用 editor 預覽/落地。

---

## 能力邊界(誠實界定)

| 能力 | 成熟度 | 說明 |
|---|---|---|
| unweighted 變形閘 | L2 真值驗收 | main_draw 4 mesh × 9 anim benchmark 全乾淨 + 負對照可抓壞網格 |
| weighted 骨綁變形閘 | L2 真值驗收 | Award 機器人 3 mesh 真值 si=0;負對照(打亂權重/放大動作)必破 |
| 靜態輪廓 IoU | L2 真值驗收 | 對 alpha 遮罩量化覆蓋率 + 頂點預算 |
| **未涵蓋** | — | 貼圖級視覺瑕疵(需 PNG 逐像素)、美術「手感」主觀項、非 `transform="normal"` 骨 |

## 何時觸發 → 用哪支閘

| 徵兆 | 閘 |
|---|---|
| mesh 靠 **deform timeline** 變形(窗簾/陰影類),問會不會撕 | `deform_eval` / 整合 `validate_against_real` |
| mesh 綁在**骨**上靠 bone 動畫變形(角色肢體/光暈類) | `weighted_deform_eval` + `validate_weighted_deform` |
| 只想看靜態輪廓吻合 + 頂點數是否超預算 | `evaluate_mesh` |

## 用法

```bash
# weighted(骨綁)mesh 逐真實動畫體檢(單 mesh)
python3 assets/weighted_deform_eval.py <skeleton.json> "<slot>" [attachment]

# weighted 閘 + 藝術家真值 + 負對照三道校驗(區塊回歸測試)
python3 assets/validate_weighted_deform.py <skeleton.json>

# unweighted mesh benchmark(逐動畫 deform 幀)
python3 assets/deform_eval.py <skeleton.json>
```

## 判讀

- `self_intersections`:非相鄰邊真交叉 → 撕裂/破圖。**不透明結構件必須 = 0**。
- `triangle_flips`:三角相對 setup 變號 → 貼圖鏡射撕裂。
- `degenerate`:相對面積趨零的三角(已對 big-win『scale 從 0 彈入』做 scale-invariant 校正)。
- **軟性加成件(如光暈 halo)容許自我重疊** → pass/fail 門檻須依 attachment 語意分類(見 references)。

## ⚠️ Spine 3.8 地雷(本 skill 已內建處理)

1. **scale timeline 缺 channel 預設是 1 不是 0**(translate/rotate 預設 0)。誤當 0 會讓 mesh 塌陷成假性自交。
2. **weighted 變形**:`worldPos = Σ weight·boneWorld.transformPoint(bind)`;沿 parent 鏈算 world;bind 為骨局部座標。
3. 取變形後座標須**同步 re-pose**;目前只支援 `transform="normal"`(遇其他模式 raise,不靜默出錯)。

詳見 `references/spine_deform_math.md`。

## 回歸 / 維護

升版前跑(於本研究 repo):`python3 tools/check_readiness.py`。對應區塊 `spine-mesh-doctor` 須全 GREEN。
曾 GREEN 轉 RED = 迴歸,擋升版。新能力須 ≥ L2 GREEN 才可加入(MINOR bump)。
