# tools/motion — 軌跡分析 / 曲線編輯 / 回寫驗證（S6）

把 spine-motion-skill 的手工流程（取樣 → 出圖 → 猜參數 → 改檔 → 再出圖）換成
**一條可量化、可回放的迴路**：分析一次 → 在網頁上把曲線調到滿意（旁邊即時顯示調完會變怎樣）→
匯出一份 spec → 一行指令套回 Spine JSON，寫檔前自動跑驗證。來回試錯的次數從「每改一版跑一輪」
變成「調到滿意才跑一次」。

```
analyze_trajectory.py            spine_trajectory_editor.html          apply_motion_spec.py
  Spine JSON ──► traj.json ──►  拖曲線 / 加刪點 / 延後 / 幅度  ──► spec.json ──► 新動畫 + V1–V7/Q1–Q3
                    ▲                     │
                    └──── 也可直接載入 skeleton JSON（頁內同一套演算法）
```

## 檔案

| 檔案 | 用途 |
|---|---|
| `spine_world.py` | 世界座標取樣器：沿父鏈算世界矩陣、`zero=` 可**逐通道**歸零、`own_split()` 把軌跡拆成 rigid / rotOwn / transOwn（精確可加）、極值 / Pearson / 循環互相關 |
| `analyze_trajectory.py` | CLI：Spine JSON → `traj.json`（取樣序列 + 量化指標 + 可編輯關鍵幀）與 skill 規範的對照表 CSV |
| `motion_spec.py` | spec 數學：延後 / 幅度旋鈕、迴圈邊界 de Casteljau 切分、Spine 3.8 緊湊 bezier 讀寫、取樣 |
| `apply_motion_spec.py` | CLI：spec → 新動畫寫回 Spine JSON（世界位移 → local translate），**驗證未全過就不寫檔** |
| `verify_motion.py` | V1–V7 結構閘 + Q1–Q3 量化閘（可 import） |
| `validate_motion_tools.py` | 本工具鏈的自我驗收（A1–A8，含負對照、JS↔Python parity、無頭瀏覽器端到端） |
| `js_core_probe.js` | 把編輯器頁內的 `spine-motion-core` 抽出來在 node 跑，供 parity 比對 |
| `bridge_harness.html` | 測試夾具：模擬 viewer 端的 postMessage 契約 |
| `shot_editor.py` | 無頭瀏覽器對編輯器截圖（產文件圖、不靠肉眼驗收） |

## 典型流程

```bash
# 1) 分析：目標=次級部位骨骼，主體=帶動它的骨骼（節拍來源）
python3 tools/motion/analyze_trajectory.py --json assets/main_draw.json \
    --anim main_draw_loop --bone face --body main \
    --out out/traj.json --csv out/對照表.csv

# 2) 編輯：瀏覽器開 spine_trajectory_editor.html，載入 out/traj.json（或直接載 skeleton JSON）
#    拖藍點改幅度與時間、雙擊加點、Del 刪點；右側旋鈕調延後 L / 幅度；
#    量化面板即時顯示「前 → 後」的幅度、相關、相位與互補的代價。按「下載 motion spec」。

# 3) 套回 + 驗證（未全過不寫檔）
python3 tools/motion/apply_motion_spec.py --spec out/main_draw_loop_v2.spec.json --write
```

## 兩個關鍵設計（決定這條迴路可不可信）

**1. 自身位移要拆成三塊，不能只做 `actual − rigid`。**
對追蹤點 p：`actual = rigid + rotOwn + transOwn`（實測殘差 < 1e-13 px）。
`rigid` 是目標骨骼所有通道歸零後、純被主體帶著走的運動；`rotOwn` 是它自轉帶動 p 的位移；
`transOwn` 只由 translate 通道造成。**只有 `transOwn` 能無損寫回 translate 關鍵值**——
若拿總量 `own` 去回寫，rotate 的貢獻會被重複計入（實測 X 幅度剛好變兩倍）。

**2. 追蹤點不能預設用骨骼原點。**
rotate-only 的配件（鈴鐺、耳環）骨骼原點完全不動，追原點會把跟隨運動誤讀成 0。
預設取該骨骼 slot 的 attachment 中心（`--point auto`），也可 `--point x,y` 指定。

## 驗證清單

寫檔前 `apply_motion_spec.py` 一定會跑：

| | 檢查 |
|---|---|
| V1 | 新動畫總長 == 原動畫總長 |
| V2 | 兩份動畫有差異的骨骼 == 只有目標骨骼 |
| V3 | slot timeline 完全相同 |
| V4 | 原動畫未被碰（新版另存供 A/B） |
| V5 | skins（權重 / attachment）未被碰 |
| V6 | 其他所有動畫未被碰 |
| V7 | 所有 keyframe 時間 ≤ **原**總長（超過＝動畫被撐長＝主體末尾凍結） |
| Q1 | 世界軌跡 vs 編輯器預測的最大誤差 |
| Q2 | 實測自身位移 vs spec 設計值 |
| Q3 | 滯後幀 / own↔主體相關 / 峰對峰幅度（前 → 後） |

## 自我驗收

```bash
python3 tools/motion/validate_motion_tools.py                      # main_draw / face
python3 tools/motion/validate_motion_tools.py --json assets/Award.json \
    --anim Award_Legend_Loop --bone 4_LEG5 --body 4_LEG3           # 第二個真實資產
python3 tools/motion/validate_motion_tools.py --no-browser         # 無 playwright 時
```

A1 三分解可加性 · A2 無損 round-trip · A3 延後 L 幀 · A4 幅度縮放 · A5 負對照（V2/V4/V5/V7 各要抓得到）
· A6 JS↔Python parity · A7 無頭瀏覽器端到端 · A8 viewer 橋接契約。

## 已知界線（誠實說）

- **世界↔local 內插殘差**：關鍵值換算是精確的（round-trip local 關鍵值誤差 0），但關鍵幀**之間**
  Spine 在 local 空間內插、編輯器在世界空間內插。父體有 scale/rotate 動畫時兩者會有殘差
  （main_draw `face`：0.12px；Award `4_LEG5` 父體無縮放：0.0001px）。要更緊就加密關鍵幀。
- **只動 translate（可選 rotate）**：mesh / 權重 / deform / attachment 屬結構層，本工具不碰。
- **靜態擺位不是曲線**：目標的 translate 只有 1 個 key（美術用動畫通道擺件）時沒有可調曲線，
  分析器會出警告，旋鈕對它無效——要做跟隨動態得先沿主體節拍加關鍵幀。
- **viewer 即時預覽尚未在本環境實測**：`spine_inspector.html` 依賴 spine-webgl CDN，本研究環境
  對外 CDN 被政策擋（403）。訊息契約已用 `bridge_harness.html` 驗過（A8），
  但「畫面真的動起來」要在使用者端（CDN 通）確認。
- Spine transform 繼承模式只精確支援 `normal` / `onlyTranslation`，其餘以 normal 近似並在
  `traj.json.warnings` / 編輯器警告區列出。
