# (INFRA) 離線 spine-webgl 3.8 + 無頭實機驗證 harness — 解除「spine_inspector 實機 round-trip」阻塞

- **結論**:`spine_inspector.html` 的實機(真 spine-webgl 3.8 runtime)round-trip 驗證**不再被 CDN 403 阻塞**。
  把官方 **spine-webgl 3.8.75** vendored 進 `vendor/`、inspector 優先載本地檔,再用 Chromium+Playwright
  無頭驅動 `window.spineTool` API,**完全離線**即可取得真 runtime 的 `getState/getMeshData/getMeshBounds`。
- **信心**:高(實跑驗證,見下方量測;與 `CLAUDE.md`/`main_draw_解析報告.md` 的資產規格逐項吻合)。
- **相關階段**:**第 1 階段工具**的實機化(過去只能用 Python 評估器近似 3.8 runtime,現可直接量真值);
  解除 2026-10-11 run 001 soft-HOLD 列出的四阻塞之一(「放行 CDN(403)或離線 spine-webgl」的**離線**半)。

## 為什麼這是真進展(不是又一個 cascade 微變體)

- 本 repo 的 S1 評估器(`deform_eval`/`validate_against_real`)全是 Spine 3.8 deform/pose 數學的
  **Python 重寫**;過去**從未**能在排程/沙箱環境裡跑真 spine-webgl runtime 比對,因為 inspector
  靠 CDN(jsDelivr / esotericsoftware)載 runtime,而這些 CDN 被 egress policy 擋(HTTP 403)。
- 這一步把「真值渲染器」接進自驗迴圈 → 下一個 run 可**用真 runtime 交叉驗證 Python 評估器**(最高槓桿的驗證缺口)。

## 可用 / 不可用的取得管道(實測,2026-10-12)

| 管道 | 結果 |
|---|---|
| jsDelivr `cdn.jsdelivr.net` | ❌ 403(org policy,`connect_rejected`) |
| cdnjs `cdnjs.cloudflare.com` | ❌ 403 |
| esotericsoftware.com | ❌ 403 |
| npm `@esotericsoftware/spine-webgl` | ⚠️ 只有 **4.x**(與 3.8 JSON 格式不相容,不可用) |
| **GitHub 匿名 git read**(proxy 直通) | ✅ `EsotericSoftware/spine-runtimes` 分支 `3.8`,sparse+shallow 取 `spine-ts/build/spine-webgl.js` |

→ **CDN 全擋、npm 無 3.8**;唯一可行是 GitHub 匿名 read(session git proxy 直通公開 repo)。
`git clone --depth 1 --branch 3.8 --filter=blob:none --sparse` + `sparse-checkout set spine-ts/build` 最小取檔。

## 成品(已進 repo)

- `vendor/spine-webgl-3.8.75.js`(422 KB,官方 3.8.75 build;sha256 `4b108bad…c3aa5`)+ `vendor/README.md`(來源/授權/sha)。
- `spine_inspector.html`:`SPINE_CDNS` 最前面加 `"vendor/spine-webgl-3.8.75.js"`(本地優先,CDN fallback 保留給使用者端)。
- `tools/live_inspect/live_inspect.js`:自足無頭 harness(自建 temp serve dir symlink inspector+vendor+assets,
  起 http、Chromium 載入、等 `spineTool.ready()`、印 JSON;`--probe` 掃第一動畫量 `getMeshBounds`)。
  缺 playwright / chromium 時 exit 2 + 清楚訊息(呼叫端可 fallback 回 Python 評估器)。`tools/live_inspect/README.md` 說明。

## 實機量測(真 spine-webgl 3.8.75,載入 `main_draw` 含貼圖)

- `getState()`:spine=**3.8.99**、bones=**28**、slots=**40**、animations=**9**、hasTexture=**true**。
- meshes(4,全 unweighted):`image/curtain_left`(21v/24tri/hull16)、`image/curtain_right`(21/24/16)、
  `image/shadow`(12/10/12)、`image/shadow2`→共用 `image/shadow` region(12/10/12)。**與資產規格逐項吻合**。
- `getMeshBounds("image/curtain_left")` 隨 `main_draw_close`(dur 0.667)**真變形**:
  f=0–0.50 約 **w≈644.8 h≈616.2**(setup);**f=0.75 收窄到 w≈371.8 h≈535.0**(窗簾闔上);f=1.0 復原(回 Loop)。
  → 真 runtime 的世界座標變形,正是 Python `deform_eval` 一直在近似的真值。
- log 確認載入的是 **本地 vendored runtime**(`runtime 載入成功: vendor/spine-webgl-3.8.75.js`),非任何 CDN。

## 怎麼跑

```
node tools/live_inspect/live_inspect.js            # 印 getState + meshes（JSON）
node tools/live_inspect/live_inspect.js --probe    # 另掃前 3 動畫量 getMeshBounds over time
# 需 node playwright + Chromium（標準研究環境已預裝；PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers）
```

## 下一步(已解鎖,給後續 run)

- **交叉驗證**:同一動畫、同一 time、同一 mesh,比對真 runtime `getMeshBounds`/`getWorldVertices`
  vs Python `deform_eval` 輸出 → 量化 Python 評估器對 3.8 runtime 的忠實度(真值級驗證,本 repo 最大驗證缺口)。
- harness 可擴 `screenshot()` 做視覺回歸(PMA 已可驗,因 `main_draw.png` 已在 repo)。
- 細化 probe 取樣(目前 5 點粗掃會錯過部分動畫的變形窗)。

## honest boundary

- 用的是 3.8.75 runtime 對 3.8.99 資產(3.8.x 線內相容;非逐位元同使用者端 editor 版,但 deform/pose 數學同線)。
- swiftshader 軟體 GL 下 `screenshot` 的像素與硬體 GPU 可能有次像素差(幾何量測 `getMeshBounds`/`getWorldVertices` 不受影響)。
- vendored 檔是第三方 build 二進位(非本 repo 產線值),不進任何 validator 真值;僅供跑工具。
