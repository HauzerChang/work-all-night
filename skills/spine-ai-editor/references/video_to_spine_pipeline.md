# 影片 / 分鏡圖 → Spine 動畫 Pipeline

> 給定一份參考影片或分鏡圖，把當中的動作轉成 Spine 動畫。

---

## 適用範圍

✅ 可以做：
- 影片內角色與目標 Spine 是**同類型 IP** 或**動作完全可拆解到既有 bones**
- 動作以**上半身為主**（手臂、頭、軀幹）
- 視角穩定**正面 / 略側面**
- 影片長度 **3~5 秒內**

❌ 做不到（須拒絕並回饋）：
- 走路 / 跑步 / 跳離地（需要 leg bone，多數 chibi 沒有）
- 全身翻滾 / 360° 旋轉（雙骨架平行 spine 不支援）
- 表情變化、嘴動（無臉骨）
- 手指動作（手是一塊）
- 配件實體變形（region 不支援，要 mesh）

---

## 兩條入口

### 入口 A：影片（mp4 / mov / webm / gif）

```
影片 → ffprobe → ffmpeg 抽 frame → 逐張看圖 → pose 識別 → 對映 bones → 可行性報告 → patch
```

### 入口 B：分鏡圖（一張或多張包含標註的圖）

```
分鏡圖 → 直接 Read 圖 → 解讀文字標註 + 視覺箭頭 → 對映 bones → 可行性報告 → patch
```

入口 B 通常更精準（標註明確），入口 A 更自然（直接看連續動作）。

---

## 入口 A 詳細步驟

### A1. Probe 影片

```bash
ffprobe -v error -show_entries stream=width,height,r_frame_rate,duration,codec_name \
                 -show_entries format=duration,size \
                 -of default <video>
```

獲取：
- 解析度（記下，後續抽 frame 不變）
- fps（決定抽幀密度）
- duration（決定抽幾張）
- codec（h264/vp9 等，多數可直接用）

### A2. 抽 frame

選一個合理的抽幀策略：

| 影片長度 | 建議抽幀數 | 間隔 |
|---|---|---|
| < 1 秒 | 5~6 張 | 0.2s |
| 1~3 秒 | 6~8 張 | 0.4~0.5s |
| 3~5 秒 | 8~12 張 | 0.5~0.6s |
| > 5 秒 | 抽選首尾 + 關鍵動作幀 | 不等距 |

```bash
VIDEO=<path>
OUT=<frames_dir>
mkdir -p "$OUT"
for i in $(seq 0 8); do
  t=$(echo "scale=2; $i * 0.5" | bc)
  # ⚠️ 注意 bc 輸出可能是 ".5" 開頭，ffmpeg 不收
  # 用 awk 確保 0 前綴：t=$(awk "BEGIN{print $i * 0.5}")
  ffmpeg -y -ss "$t" -i "$VIDEO" -frames:v 1 -q:v 2 "$OUT/frame_${i}_t${t}s.png"
done
```

### A3. 逐張 Read 並識別 pose

每張 frame 用 Read tool 載入，多模態看圖。識別 6 大要素：

1. **頭**：朝向（正面/左傾/右傾/上點/下沉）
2. **肩膀 / 軀幹上**：傾斜方向、Y 位移
3. **腰部 / 重心**：左右移動、上下浮動
4. **手臂**：抬起/放下/外展/內收，估算角度（粗略 ±10° 精度）
5. **手 / 拳頭**：朝向、是否握拳/張開
6. **腿（若 spine 有）**：站姿、蹲下、抬腳等

### A4. 對映到目標 Spine

| 影片觀察 | 對應 bone(s) |
|---|---|
| 頭點頭 / 左右傾 | main_head: rotate ±X°, translate.y ±N |
| 軀幹側傾 | bady_up: rotate ±X° |
| 整體下沉 / 跳起 | main: translate.y ±N |
| 重心左右 | main: translate.x ±N |
| 手臂抬起 / 揮動 | main_arm_L/R: rotate ±X° |
| 拳頭朝向 | main_hand_L/R: rotate ±X° |
| 武器揮 | sword: rotate ±X° |
| 走路 / 跳 / 蹲 / 翻 | ❌ 拒絕，告知使用者「Fg_Main 無腿骨」等 |

### A5. 寫可行性報告

按下面結構：

```markdown
# 影片可行性報告 — <影片描述>

## 1. 整體判定
[可行 / 部分可行 / 不可行] / 信心：[高/中/低]

## 2. 逐 frame Pose 識別
| Frame | t | 觀察到的 pose | 估算 |
|---|---|---|---|
| 0 | 0.0s | 立正 | 全 0 |
| 1 | 0.5s | 左臂上揮 | main_arm_L rotate ≈ -30° |
| ... |

## 3. 動作結構解析
（是否有 cycle / 是 N 拍）

## 4. Bone 對映
| 影片觀察 | Bone | Keyframe 規格 |
|---|---|---|

## 5. 完整 keyframe 規格
（Python dict 格式）

## 6. 風險清單

## 7. 不可行項目
（給使用者選擇刪改）

## 8. 建議下一步
（A: 直接 patch / B: 調整參數 / C: 覆蓋現有動畫）
```

### A6. 使用者 ack 後寫 patch

用 `assets/patch_templates/add_animation.py` 範本，把可行性報告中的 keyframe 規格直接放進去。

### A7. 跑 Cocos MCP 9 步流程

詳見 `cocos_mcp_push_sop.md`。

---

## 入口 B 詳細步驟

分鏡圖通常是這種格式：

```
[Frame 1]              [Frame 2]              [Frame 3]
立正 + 重心下沉        左傾 + 拳外推         右傾 + 拳內收
1. 頭部：微點上        1. 頭部：左傾          1. 頭部：右傾
2. 肩膀：下沉          2. 肩膀：跟身體傾斜    2. 同
3. 胸口：收回          3. 胸口：維持正面      3. 同
4. 手臂：靠腰側        4. 手臂：向外推出      4. 手臂：向內收
5. 腰部：居中下沉      5. 腰部：左傾          5. 腰部：右傾
6. 腿部：膝蓋微彎      6. 腿部：左腳承重      6. 腿部：右腳承重
```

### B1. Read 分鏡圖

```python
# Read tool 把分鏡圖載入，多模態看圖識別文字標註
```

### B2. 解析 6 大身體部位描述

每個 frame 拆解為 6 個項目（頭、肩、胸、手臂、腰、腿）。每個項目都對映到具體 bones / timeline。

### B3. 標出不可行項目

特別注意「腿部」相關：
- 「膝蓋微彎」→ Fg_Main 無 leg bone → 用 main.translate.y -3 模擬整體下沉
- 「腳跟微抬」→ 完全做不到 → 在報告中列為「無對應 bone，跳過」
- 「重心移到 X 腳」→ 用 main.translate.x ±N 模擬重心位移

### B4. 寫可行性 + bone 對映表

跟入口 A 類似，但更精簡（分鏡圖通常標註更明確）：

```markdown
| 分鏡指令 | Fg_Main bone | 處理方式 |
|---|---|---|
| 頭部 微點上 / 左傾 / 右傾 | main_head | rotate ±6° + translate.y +2 |
| 肩膀 微下沉 / 左右轉動 | bady_up | rotate ±3° + translate.y（已含於 main）|
| 胸口 收回 / 維持正面 | （無對應 bone） | ⚠️ 跳過 或 加 chest bone |
| 手臂 握拳 / 向外推 / 向內收 | main_arm_L/R + main_hand_L/R | arm ±15° / hand ±20° |
| 腰部 居中 / 左傾 / 右傾 | main | translate.x ±8 + .y -3 |
| 腿部 膝彎 / 換腳承重 / 腳跟抬 | （無 leg bone） | ❌ 無法做到 |
```

### B5-B7. 同入口 A

---

## 影片 / 分鏡圖兩條入口的選擇

| 條件 | 推薦入口 |
|---|---|
| 影片自帶清晰節奏與時間 | A（影片）|
| 設計師明確標註動作細節 | B（分鏡圖） |
| 動作是循環的 | B 更直觀（可標 frame 1→N→loop）|
| 動作是 one-shot 且自然 | A 更貼近原始意圖 |
| 沒有現成素材，只有文字描述 | 退化成「LLM 自編」，看 `animation_patch_patterns.md` |

---

## 給使用者的「事前期待管理」

每次接到影片/分鏡圖前，告訴使用者：

```
精度預期（誠實）：
- 角度估算誤差 ±10° 左右（單一視角的限制）
- 深度資訊不可信（z 軸資料用 fake 處理）
- 時序：影片總長 < 3 秒效果最好

會被我直接拒絕的動作類型（再次確認，免得你的影片白做）：
- 走路 / 跑步 / 跳起腳離地 / 蹲下（無腿）
- 表情變化、嘴動（無臉骨）
- 手指比動作（手是一塊）
- 全身翻滾、360° 旋轉
- 配件變形（無 mesh）

最理想的影片：
- 機甲上半身動作（揮手、鞠躬、戰鬥姿、舞步、揮劍）
- 3 秒內，建議可 loop（首尾相接）
- 正面 / 略側面視角（不要俯視 / 仰視，深度估算會爆）
```

避免使用者花 30 分鐘生一支「角色翻跟斗」的 AI 影片，最後我們只能拒絕。

---

## 結語

影片/分鏡圖轉 Spine 的本質是「**把 N 個 frame 的 visual state 投影到 M 條 bone timeline**」。M 通常遠小於 N（一個 frame 拍對應 5~8 條 timeline），所以這是個降維 + 量化問題。

實際做下來最大的挑戰**不是技術**而是**期望管理**：使用者覺得 AI 影片很自由，卻發現大半動作無法被 chibi 機甲執行。Skill 的主要價值是**快速給出可行性回饋**，幫使用者調整源頭素材，而不是事後勉強做出視覺爆走的版本。
