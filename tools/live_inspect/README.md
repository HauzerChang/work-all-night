# tools/live_inspect — 無頭實機 Spine runtime harness

用 Chromium(Playwright)無頭驅動 `spine_inspector.html`,載入**真 spine-webgl 3.8 runtime**
(vendored,離線)取得 `window.spineTool` 的**真值量測**:`getState` / `getMeshData` /
`getMeshBounds` / `getWorldVertices`。這是把 Phase-1 可視化工具接進自驗迴圈的「真值渲染器」
——過去只能用 `tools/mesh_gen/` 的 Python 評估器近似 Spine 3.8 的 deform/pose 數學。

**完全離線**:inspector 優先載 `vendor/spine-webgl-3.8.75.js`(見 `vendor/README.md`),
不需放行被 egress policy 擋掉的 spine-webgl CDN。

## 用法

```bash
node tools/live_inspect/live_inspect.js             # getState + meshes（單一 JSON 到 stdout）
node tools/live_inspect/live_inspect.js --probe     # 另掃前 3 動畫量 getMeshBounds over time
node tools/live_inspect/live_inspect.js --asset main_draw --repo . --exe /path/to/chrome
```

- `--asset NAME`  `assets/NAME.{json,atlas,png}` 的 base 名(預設 `main_draw`)。
- `--repo DIR`    repo 根(預設:此檔往上兩層)。
- `--exe PATH`    Chromium 執行檔(預設:自動找 `$PLAYWRIGHT_BROWSERS_PATH` 下的 chromium-*)。
- `--probe`       掃前 3 支動畫、每支 5 點取樣第一個 mesh 的 `getMeshBounds`。

## 需求

- node `playwright`(標準研究環境預裝)。
- 一份 Chromium build(`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`,預裝)。
- 缺任一 → exit code 2 + JSON `{"ok":false,"error":...}`,呼叫端可 fallback 回 Python 評估器。

## 輸出(JSON)

`{ ok, asset, runtime, spine, bones, slots, animations, meshes, hasTexture, [probe], logs }`
成功 exit 0、失敗 exit 1(ready 逾時)/ 2(缺依賴)。

## 已驗(2026-10-12, main_draw)

spine=3.8.99・28 bones・40 slots・9 anims・hasTexture=true・4 mesh 拓樸與資產規格吻合;
`main_draw_close` 下 `image/curtain_left` 於 f≈0.75 由 w≈645→372 真變形(窗簾闔上)。
詳見 `knowledge/infra-offline-spine-webgl-live-harness.md`。
