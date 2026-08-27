# skill 化策略 / 完成度機制 / 維護版本政策

> 這個 repo 的自驅研究成果,要**分階段、防半成品地**固化成可觸發、可交付、可持續更新的 skill。
> 本檔是策略與規則;**成熟度的真相來源是 `tools/check_readiness.py`(實跑 validator),不是任何靜態文字**。
> 每次里程碑跑 `python3 tools/check_readiness.py`,再依門檻決定打包/升版。

---

## 1. 為什麼要機制(不是想到就打包)

skill 一旦交付給使用者/團隊,就會被信任、被反覆呼叫。若把**半成品**(例如「評估器好了但生成器沒做」)
打包成 skill,會固化錯誤能力邊界、誤導後續使用。所以:**能不能 skill 化由機器可驗的成熟度閘決定**,
延續本專案鐵律「每能力必配評估器」。

## 2. 成熟度階梯(maturity ladder)

| 級 | 名稱 | 判準 |
|---|---|---|
| **L0** | 概念 | 只有想法/計畫,無可跑程式。 |
| **L1** | 原型 | 工具能跑,但只在合成/自造資料上驗(無真值)。 |
| **L2** | 真值驗收 | 對**真實生產資產 + 真值**通過,且評估器本身經**正/負對照**確認可信。 |
| **L3** | 端到端 | 串成 pipeline,對**多個**真實標的穩定通過,有**一鍵驗證指令**。 |
| **L4** | skill 固化 | 已打包為 skill(SKILL.md + 觸發詞 + references + 回歸測試)。 |

## 3. skill 化門檻(READY_TO_SKILL)

一個**區塊**達門檻,才可打包:

> **所有核心能力(gen/pipeline)≥ L2 且其 validator GREEN,且至少一條端到端能力達 L3。**

**防固化半成品的關鍵規則**:只要有任一核心能力 < L2(尤其**生成器**還停在 L0/L1),整區塊 **HOLD**。
**評估器就緒 ≠ 生成能力就緒** —— 例:`spine-weighted-forge` 的變形閘已 L2,但 BBW 生成器還 L0 → 禁止打包。

## 4. 區塊 → 目標 skill 地圖

| 區塊 id | 內容 | 目標 skill | 與既有 `spine-ai-editor` 的關係 |
|---|---|---|---|
| **spine-mesh-doctor** | 靜態 IoU + unweighted/weighted 變形品質閘 | 新 skill(品質體檢) | 補它「只可視化、無量化 pass/fail」的空白 |
| **spine-asset-forge** | 目標圖/PSD → 可載入 Spine 素材(靜態) | 新 skill(素材鍛造) | 補它明說「mesh 交給 Spine editor」的空白 |
| **spine-slicing** | PSD/atlas 無損切件重組閘 | 併入 forge 子模組 | forge 的上游步驟 |
| **spine-target-analysis** | 反推分析 → 需求規格(上游) | 折入 forge 前端 / 併 editor 可行性評估 | editor 的「可行性評估」量化版 |
| **spine-weighted-forge** | weighted mesh 生成 + BBW 權重 | 未來併入 forge | editor 的結構性擴充需要的底層能力 |

分工原則:**forge 從零生素材、mesh-doctor 把關品質、spine-ai-editor 讓素材動起來並落地 Cocos**。三者串成一條線。

## 5. 維護 / 版本政策(SemVer per skill)

每個 skill 的 `SKILL.md` 開頭帶 `version` + Changelog(對齊 `spine-ai-editor` 慣例)。

- **MAJOR**:破壞性改動(API/輸入契約/觸發範圍大改)。
- **MINOR**:新增一條達 **L2 GREEN** 的能力(跨過門檻才可加入)。
- **PATCH**:既有能力的 bug 修正 / 閘校準 / 文件。

規則:
1. **只有 ≥L2 GREEN 的能力可進 skill**;嚴禁把 L0/L1 能力寫成 skill 的「能力」(可寫成「已知限制」)。
2. 每個 skill 附**回歸指令**:`python3 tools/check_readiness.py`(對應區塊需全 GREEN 才可升版)。
3. 每次升版前跑 readiness;**曾 GREEN 轉 RED = 迴歸**,擋升版、觸發修復。
4. skill 內誠實界定**輸入契約相依**(如 forge 需分層 PSD)與**未驗維度**(如 forge 不含動畫)。

## 6. 自驅迴圈掛鉤(prompts/run.md)

里程碑收尾時:跑 `check_readiness.py` → 若某 HOLD 區塊跨過門檻 → 依 RULES **C 類里程碑**回報使用者
(打包/同步 skill 屬使用者帳號層級動作,需人拍板;repo 只負責**備好 skill 套件**於 `skills/<id>/`,
使用者決定是否 sync)。達門檻的區塊由自驅 session 產出/更新 `skills/<id>/` 套件並升版。

## 7. 現況快照

見 `skills/READINESS.md`(由 `check_readiness.py` 產出的人讀版;真相以指令即時輸出為準)。
