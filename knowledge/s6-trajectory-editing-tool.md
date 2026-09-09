# S6 軌跡分析／曲線編輯工具鏈（把「來回試錯」換成「一次調到位」）

**結論**：次級動態（配件跟隨）的調整迴路可以工具化到「分析一次 → 在網頁上把曲線調到滿意 →
一行指令套回並自動驗證」。關鍵不在畫圖，而在三件事：
(1) **自身位移必須三分解**才能無損回寫；(2) **編輯器的預測要與實測對得上**（實測 0.0001–0.12px），
否則使用者仍得靠「改完再看」；(3) **寫檔前的結構閘**（總長／只動目標骨骼／原動畫與 skins 未動）
把 skill 的退件條件變成機器可判。

**依據**：`tools/motion/validate_motion_tools.py` A1–A8 對兩個真實資產全 PASS
（`main_draw`/`face`、`Award`/`4_LEG5`），含負對照與無頭瀏覽器端到端。
**信心**：高（工具鏈本身有量化真值）；美感（延後多少幀好看）仍是使用者的 A 類決策。
**相關階段**：第 2 階段能力鍛鍊 · 服務 `spine-motion-skill`。

## 產出

| | |
|---|---|
| `spine_trajectory_editor.html` | 單檔零相依（CDN 被政策擋，所以自己畫圖自己算）。載入 traj.json 或 skeleton JSON → 世界 X/Y 雙面板、拖曳關鍵幀、加/刪點、延後與幅度旋鈕、即時量化、匯出 spec/CSV/skill 交辦文字 |
| `tools/motion/` | 分析器、spec 數學、套用器、驗證器、AC 驗收、node parity 探針、橋接夾具、截圖工具（見該目錄 README） |
| `spine_inspector.html` | 新增 `getBoneTrajectory()`（用官方 runtime 取世界軌跡）、`openTrajectoryEditor()`（iframe/popup 內嵌編輯器）、`spine-motion/preview` 訊息 → 寫回 rawJson → rebuild 即時預覽 |

## 三個必須記住的技術結論

### 1. `own = actual − rigid` 不夠，要拆三塊

對追蹤點 p：

```
actual(t) = rigid(t) + rotOwn(t) + transOwn(t)      # 實測殘差 < 1e-13 px
```

- `rigid`：目標骨骼**所有**動畫通道歸零 → 主體帶給它的運動
- `rotOwn`：只留 rotate/scale/shear → 骨骼自轉帶動 p 的位移
- `transOwn`：只由 translate 造成 = 父體世界矩陣 × local 位移

Spine 的 bone local 是 `T·R·S`，translate 造成的世界位移與 rotate 無關，所以三者**精確可加**。
**只有 `transOwn` 能無損寫回 translate 關鍵值**：第一版拿總量 `own` 回寫，round-trip 後 X 幅度
從 0.071 變成 0.142px（剛好兩倍）——rotate 的貢獻被重複計入。這個 bug 只有做 round-trip 才抓得到。

### 2. 追蹤點預設不能用骨骼原點

rotate-only 的配件（`bell`）骨骼原點在自轉下完全不動，追原點量到的自身位移是 0。
改成預設取該骨骼 slot 的 attachment 中心後，`bell` 量到 0.207px 的自身位移。
分析器 `--point auto`（可覆寫），spec 會記下 `target.point`，驗證與套用都用同一點。

### 3. 迴圈邊界要 de Casteljau 切分，且 loop 尾端的重複 key 要先拿掉

延後 L 幀後最後一段跨過總長：把該段 bezier 在邊界切成兩段、各自正規化，t=0 與 t=總長 放同一內插值。
實測「延後後的曲線 == 原曲線循環平移 L 幀」誤差 **7e-13**（任意 L，含非整數）。
踩雷：loop timeline 慣例上 `frame=總長` 的 key 是 `frame=0` 的複製，**延後前必須先移除**，
否則取模後兩者撞在同一幀，去重會留下錯的曲線（症狀：曲線莫名變線性、平移比對誤差 0.5px）。

## AC（`validate_motion_tools.py`）

| AC | 內容 | main_draw/face | Award/4_LEG5 |
|---|---|---|---|
| A1 | 三分解可加性 | 1.1e-13 px | 0 px |
| A2 | 無損 round-trip（local 關鍵值逐值相同 + V1–V7） | 0 px | 0 px |
| A3 | 延後 5 幀 == 原曲線循環平移 5 幀 | 0.118 px | 0.0001 px |
| A4 | 幅度 ×1.15（以震盪中心縮放） | 比值 1.1500 | 1.1500 |
| A5 | 負對照：V2/V4/V5/V7 各要抓得到 | 4/4 | 4/4 |
| A6 | JS↔Python parity（頁內演算法 vs 工具） | 世界座標 0、spec 數學 8.9e-16 | 5.7e-14 / 8.9e-16 |
| A7 | 無頭瀏覽器端到端：頁面匯出 spec → 套回，**預測 vs 實測** | 0.113 px | 0.00014 px |
| A8 | viewer 橋接契約（harness 收 preview keys → 貼進動畫 → 同一套閘） | 0.114 px | 0.00016 px |

A3/A7 的 0.118px 是**世界↔local 內插的固有殘差**：關鍵值換算精確，但關鍵幀之間 Spine 在 local
內插、編輯器在世界內插；`main_draw` 的父骨 `main` 有 scale 動畫所以看得到，Award 的父體沒縮放就是 1e-4。

**負對照逼出的真 bug**：V7 原本寫成「key 時間 ≤ 新動畫總長」——但新加的長 key 自己把總長撐大，
檢查恆真。改成以**原動畫**總長為準才抓得到（這正是 skill 列為退件原因的「動畫被撐長、主體末尾凍結」）。
另一個：JS 的曲線求值原本重用對齊 runtime 的 `bezierY`（有 1e-7 提早跳出），與 Python 的純二分差 1e-6，
parity 閘抓到後改成同演算法 → 8.9e-16。

## 對 spine-motion-skill 的接口

spec（`spine-motion-spec/1`）帶 `edit.keys`（世界座標自身位移）＋四個旋鈕＋`metrics.before/after`
＋`predicted`（供 Q1 閉迴路比對）＋`skill.notes`（要主動告知的副作用，例如互補導致世界總幅縮小）。
可貼進 SKILL.md 的章節見 `tools/motion/skill_snippet.md`。

## 界線

- 只動 translate（可選 rotate）；mesh/權重/deform/attachment 屬結構層，不碰。
- 目標 translate 只有 1 個 key = 靜態擺位（美術用動畫通道擺件），沒有曲線可調，分析器出警告、
  旋鈕類 AC 自動 skip；要做跟隨得先沿主體節拍加關鍵幀。
- **viewer 即時預覽（進階功能）只驗到訊息契約**：`spine_inspector.html` 依賴 spine-webgl CDN，
  本環境對外 403，畫面預覽要在使用者端確認。
- transform 繼承只精確支援 `normal`/`onlyTranslation`，其餘近似並列警告。
