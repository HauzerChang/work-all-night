---
name: spine-asset-request
description: 根據使用者描述的 spine 動畫需求(想做什麼動作/轉向/表情),判斷現有素材夠不夠用,不夠就自動驅動切圖(PSD-first)與補圖(CPU baseline / gpt-image-2)pipeline,產出可直接用的 spine 資產。使用時機:使用者說「我想讓角色做XX動作」「這個轉向現在的素材不夠」「幫我補這塊缺口」「這個動畫需要新的部件」等,牽涉到 spine 資產本身要不要新增/修改切圖或補圖時觸發。
---

# Spine 資產需求驅動切圖/補圖(初步版,2026-09-04 建立)

> 這是 S4(切圖+補圖研究排程,分支 `claude/spine-s4-inpainting`)成果的**應用層封裝**——把
> 已驗證的個別工具串成一套「使用者說需求 → 自動判斷缺口 → 驅動對應工具 → 自我驗證」的流程。
> 不是重新發明能力,是把 `tools/mesh_gen/` 底下已經量化驗證過的工具接起來用。
> **初步版**:目前流程需要 Claude 逐步人工判斷「缺口屬於哪一類」,還沒有全自動的「影片→
> 規格」反推器(那是路線圖上的 S1,尚未建成,見 `Spine能力鍛鍊計畫.md`)。

## 何時用這個 skill

使用者描述一個**想要的 spine 動畫效果**(不是直接給程式指令),例如:
- 「我想讓這個角色轉身,露出側面」
- 「這個開獎動畫我想加一個角色眨眼的表情」
- 「這隻手現在動不了,我想讓它單獨甩動」
- 「這個部位露出來的時候好像缺一塊」

## 核心流程

### 第 0 步:讀懂需求,定位牽涉的 slot/attachment

1. 用 `spine_inspector.html` 的 `window.spineTool` API(`getState()`/`listAnimations()`/
   `getMeshData()`等,見 `CLAUDE.md`「Phase-2 API」章節)或直接讀 spine JSON,列出現有骨架
   /slots/attachments,找出需求牽涉哪個(或哪些)slot。
2. 若專案有對應的來源 PSD(見 `knowledge/s4-psd-contract.md`),同時打開確認圖層結構
   ↔ slot 的既有對應關係(`knowledge/s4-psd-inplace-edit.md` 有既有案例參考)。

### 第 1 步:分類缺口(決定走哪條路)

依 `knowledge/s4-inpaint-taxonomy.md` 的既有分類法判斷:

| 缺口類型 | 判斷方式 | 對應動作 |
|---|---|---|
| **A. 部件已存在,只是沒被單獨拆成 slot** | PSD 有分層,但該部位跟別的部位黏在同一張圖層 | 走「切圖」(第2步) |
| **B. 部件已拆出但露出時有缺口/破綻,且動態下不能露餡(1b)** | 該 slot 已存在,遮擋物拿掉/轉向後某塊區域會透明或不完整,但只要求「不穿幫」 | 走「補圖-CPU優先」(第3步) |
| **C. 缺口需要精確重現特定內容(1a 需表演)** | 例如需要眨眼、特定表情、特定紋理必須正確,不能只是「看起來合理」 | 走「補圖-生成式」(第3步,但驗收標準不同,見下方⚠️) |
| **D. 需要原圖不存在的視角(情境2,視角外推)** | 例如水平轉向要露出圖裡完全沒畫過的側面/背面 | **目前無解**,見下方「無法自動處理的情況」 |

### 第 2 步:切圖(缺口類型 A)

```bash
python3 tools/mesh_gen/psd_slice.py <psd> -o <out_dir>          # 切出各圖層 PNG + manifest
python3 tools/mesh_gen/atlas_crop.py <out_dir>/<layer>.png ...  # 併入 atlas(注意 derotate 方向)
```
- 驗收:`psd_slice.py` 內建的重組無損閘(合成 + 貼回原 composite 比對)必須 PASS。
- 若 PSD 沒有分層(平圖):**目前無法自動拆件**(見 `CLAUDE.md`「誠實界定」段落),回報使用者
  需要美術提供分層檔,或走 S5(骨架半自動)+ 生成式路線(比 S4 範圍大,不在本 skill 內)。

### 第 3 步:補圖

**優先序:CPU baseline → 1b 驗收 → 不夠才上生成式。**理由:CPU 免費、秒級;1b(防穿幫)
標準下,既有研究(`knowledge/s4-inpaint-1b-lenient-gate.md`)證實機械紋理等「看起來補不動」
的材質其實 1b 都能過。

1. **先跑 CPU baseline + 1b 閘**:
   ```python
   from inpaint_eval import score_candidates, select_best
   scored = score_candidates(holed_rgba, mask, mode="interior")  # 或 "edge"
   best = select_best(scored)  # 1b 分數盲選
   ```
   `best["pass"]` 為 True → 直接用 `psd_inplace_patch.patch_layer_auto()` 寫回 PSD,完成。

2. **1b fail,或缺口屬於類型 C(需要精確表演)** → 才考慮候選17(gpt-image-2):
   - **⚠️ 先讀 `knowledge/s4-inpaint-candidate17-gptimage2.md`**:目前已知逐像素 1a 分數
     (ssim/premult_mae)對生成式輸出可能不公平(生成內容風格對但幾何形狀不同,肉眼看不出
     破綻但分數判 fail)。**驗收請優先用 1b 自我參照分數或 vision-proxy 判定**,不要單靠
     1a ssim 就判定「gpt-image-2 補不好」。
   - 兩種呼叫方式:
     - **無人自動(排程/批次)**:`tools/mesh_gen/s4_openai_client.py` 的 `edit_image()`,
       key 從環境變數 `OPENAI_API_KEY` 讀(需先確認此環境的網路政策已放行
       `api.openai.com`,見 `log/s4-2026-09-04-034.md`/`035.md` 的阻塞排除紀錄)。
     - **有人互動(即時調整 prompt/mask)**:`tools/mesh_gen/s4_ai_viewer.html`,瀏覽器打開
       即可用,key 由使用者自己貼(存本機 localStorage,不經過任何伺服器)。
   - 每次呼叫都會自動記錄用量到 `tools/mesh_gen/s4_data/openai_usage.jsonl`,用
     `tools/mesh_gen/s4_usage_dashboard.html` 檢視。**每次呼叫都是真實花費**,batch 跑多個
     案例前,先讓使用者知道大概要打幾次。
   - 生成結果**可能有像素漂移/縮放**(`knowledge/s4-gptfill-plugin-knowledge.md` §3),
     目前 `s4_openai_client.py`/`s4_ai_viewer.html` **都還沒做像素對位**——結果貼回前,
     用視覺比對(`psd_preview.html` 差異熱圖,或直接肉眼比對)確認接縫沒有明顯漂移,
     漂移明顯就不能直接套用,需要先做對位(尚未實作,是候選17後續工作項)。

### 第 4 步:寫回 + 真實場景驗證

```bash
python3 tools/mesh_gen/psd_inplace_patch.py <psd> --layer <name> --auto   # 寫回 PSD(統一座標系)
python3 tools/mesh_gen/atlas_crop.py ...                                  # 重新出 atlas
python3 tools/mesh_gen/atlas_patch.py ...                                 # 貼回真實 spine atlas
```
用 `tools/mesh_gen/s4_spine_render_harness.html`(多頁 atlas 支援)或 `spine_inspector.html`
(單頁 atlas)跑動畫時間軸截圖,肉眼(或 `s4_award_screenshot_compare.py` 全場景像素比對)
確認新素材在真實動畫尺度下沒有露餡/接縫/色差。

### 第 5 步:記錄

若在 S4 排程分支(`claude/spine-s4-inpainting`)下執行,依 `RULES.md`/`prompts/run_s4.md`
更新 `STATE_S4.md` + 寫 `log/s4-*.md`;新發現的可轉移知識寫 `knowledge/s4-*.md` 並在
`knowledge/README.md` 尾端 append。若在主排程或一般互動 session 下執行,依當下情境記錄
即可,不用套用 S4 專屬檔案隔離契約。

## 無法自動處理的情況(誠實回報,不要硬做)

- **情境2(視角外推)**:原圖不存在的視角/內容,不是補圖演算法問題。回報使用者:需要美術
  提供額外參考圖、走生成式 AI 從頭生成、或動畫設計端規避真轉向(見
  `knowledge/s4-inpaint-taxonomy.md`)。
- **平圖(未分層)自動拆件**:CPU 完全做不到語意分割,回報使用者需要分層 PSD 或人工拆件。
- **候選17生成結果有明顯像素漂移**:目前沒有自動對位管線,不要硬套,回報使用者需要人工
  微調或等對位管線做出來。

## 相關工具/文件速查

- 切圖:`psd_slice.py`、`atlas_crop.py`、`knowledge/s4-psd-contract.md`
- 補圖(CPU):`inpaint_eval.py`、`knowledge/s4-inpaint-evaluator.md`、
  `knowledge/s4-inpaint-1b-lenient-gate.md`
- 補圖(生成式):`s4_openai_client.py`、`s4_ai_viewer.html`、`s4_usage_dashboard.html`、
  `knowledge/s4-inpaint-candidate17-gptimage2.md`、`knowledge/s4-gptfill-plugin-knowledge.md`
- 寫回/驗證:`psd_inplace_patch.py`、`atlas_patch.py`、`s4_spine_render_harness.html`、
  `spine_inspector.html`、`s4_award_screenshot_compare.py`
- 分類法/驗收標準:`knowledge/s4-inpaint-taxonomy.md`
