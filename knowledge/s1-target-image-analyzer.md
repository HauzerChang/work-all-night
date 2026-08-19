# S1 目標圖反推分析器 — 靜態 2D 圖 → Asset & Rig Requirement Spec

- **結論**:落實使用者新增研究項目(2026-08-19)「分析目標 2D 圖以更精準拆圖/補圖」,並具體化 PLAN 的
  **S1 反推分析器**。工具 `tools/analyzer/analyze_target.py` 吃分層 PSD,輸出五段規格;
  `validate_analyzer_award.py` 用真實生產 spine(Award)當真值校驗,**5 項校驗全 PASS**。
- **信心**:高(對真實生產標的 robot_parts.psd ⇄ Award 逐項量化;確定性演算法 + 可驗證閘)。
- **階段**:第 2 階段 → S1(從 ⬜ 未開始 → 首個可用原型 + 真值驗收)。

## 標準指令

```
python3 tools/analyzer/analyze_target.py assets/robot_parts.psd --md out.md --json out.json
python3 tools/analyzer/validate_analyzer_award.py       # 對 Award 真值,5 項全 PASS → exit 0
```

## 五段輸出(對應使用者五個研究項目)

| # | 使用者項目 | 工具產出 | 方法(確定性) |
|---|---|---|---|
| 1 | 運動構件 | 可動件清單 + bbox/面積/z/質心 | PSD 可見 leaf 圖層 = 候選可動件(PSD-first 契約) |
| 2 | 周邊特效 | 每件 結構/特效 分類 + 子類 + 分數 | 加權訊號:命名關鍵字(0.34)+羽化+佔比+包覆其他件+低細節+z極端 |
| 3 | 動作腳本/分鏡 | In/Loop/Out 分鏡草案 + 每件動作 | 件+類型先驗(slot 大獎);**PROPOSAL,待真值校驗** |
| 4 | 拆圖策略 | 每件交付規格(切件/padding/命名/mesh vs region/pivot) | 沿用 S4 慣例 `<檔名>/<層名>`+2px;軟/大/易形變→mesh |
| 5 | 補圖項目 | 露出區(5A)+ 封閉破洞補圖候選(5B)+ 判定 | 見下「補圖的誠實界定」 |

## 對 Award 真值的校驗結果(全 PASS)

| 校驗 | 結果 |
|---|---|
| ① 可動件召回 | **1.0**(5/5 對上 Award `機器人拆件/*` slot) |
| ② 特效分類 | **5/5**(光暈→特效;頭/身體/雙手→結構) |
| ③ mesh/region 建議 vs Award 實際 | 無 mismatch:光暈/身體 mesh=match;右手/頭 region=對;左手(Award mesh)判 partial |
| ④ 分鏡結構 | In/Loop/Out 全中;4 檔位(Legend/Mega/Omg/Super)全中 |
| ⑤ 露出項合理性 | **4/4**:每筆露出,遮擋者或被遮件在 Award 真有足量骨運動 |

視覺證據:`knowledge/figures/s1_robot_analysis.png`(綠=結構/橙=特效/洋紅=露出區)。
完整範例規格:`knowledge/s1-example-robot-spec.md`、`specs/robot_parts.spec.json`。

## ★ 關鍵發現與誠實界定

### 1. 補圖需求是「輸入契約相依」的,不是絕對的
**分層 PSD 各層本就完整** → 疊放遮擋 ≠ 缺像素。故 #5 拆成兩塊誠實區分:
- **5A 露出區**:上層可動件蓋住『下層已有內容』的區域。運動移開會露出,但下層已完整 → **不需補圖**,
  只需知會 rigger(哪些藏區之後會現出)。
- **5B 補圖候選**:只採可靠訊號 —— 下層輪廓內的**封閉破洞**(`binary_fill_holes`)。
  robot_parts 得 **0 封閉破洞** → 判定「分層完整,補圖需求極低」,這正是 **PSD-first 契約能繞開補圖**的量化證據。
- ⚠️ 若輸入是**單張未分層平圖**,結論相反:所有被可動件蓋住的區都是潛在破洞 → 補圖需求高。
  工具目前吃 PSD;平圖流程(切件後才知破洞)屬後續 S4/S5。

### 2. 靜圖沒有觀測到的運動 → #3 是「先驗提案」,靠真值校驗召回
純靜態圖無真實運動,#3/#4/#5 的「運動」由**類型先驗**(slot 大獎 = In/Loop/Out×檔位)提出,非觀測。
Award 真值證明此先驗對這類主角**結構正確**(beats + tiers 全中)。這也界定了 S1 的能力邊界:
給對類型先驗 → 分鏡結構可反推;個別動作幅度/時序仍需影片或人審(S5 / 使用者拍板)。

### 3. 特效分類:美術命名是最強訊號,但不能只靠它
robot_parts 全圖層 blend=NORMAL(光暈沒用 additive)→ **混合模式不可靠**。
有效訊號組合:命名關鍵字(光暈/glow/粒子…)最強,佐以羽化帶比例、佔畫布比、是否包覆其他件、內部細節密度、z 極端。
光暈得分 0.999(遠超 0.45 閾值),結構件全 <0.14 → 分離度高。

## 下一步候選

1. **接 S3/S4:規格 → 實際切件 + mesh 生成**。#4 建議「mesh」的件(光暈/身體)直接串 `generate_mesh_v2`,
   region 件走 `psd_slice` → 端到端「目標圖 → 可載入 spine 素材」。
2. **平圖(未分層)流程**:無 PSD 時用分割(rembg/SAM 粗切)產候選件,再跑同一分析器;補圖需求會顯著上升 → 接補圖分級。
3. **分鏡先驗庫擴充**:加更多類型(角色 idle、symbol 爆分、背景循環…)先驗,提升 #3 泛化。
4. **特效子類細分 + 參數**:粒子/放射/流光的動畫參數建議(頻率/幅度)供 rigger 起手。
