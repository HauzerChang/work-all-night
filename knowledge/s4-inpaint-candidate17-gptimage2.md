# S4 候選17:gpt-image-2 headless 補圖 —— 第一次真實驗證

> 分支 `claude/spine-s4-inpainting`,2026-09-04(chunk 35)。前置:chunk 34 記錄使用者授權
> + 網路阻塞;使用者已把 `api.openai.com` 加入此排程容器的網路允許清單,阻塞解除。

## 背景

`knowledge/s4-lama-feasibility.md`(候選4)、`s4-inpaint-evaluator.md` 已量化 CPU baseline
與通用 LaMa 權重都過不了 1a 嚴格標準(機械紋理材質 ssim 上限 ~0.51/0.57)。
`s4-gptfill-plugin-knowledge.md`(chunk 19)記錄了一個**開源**的 Photoshop UXP 插件
(⚠️ 更正:chunk 19 誤記為「使用者自製」,實際是使用者提供給 Claude 做知識萃取的開源插件,
非使用者原創——見 `STATE_S4.md` chunk 35 更正說明)打 `api.openai.com` 的 `gpt-image-2`
做補圖,抄出了 mask 慣例、對位管線知識(但不是程式碼複製)。候選17要驗證:同一顆模型,
不透過 Photoshop、純 headless 呼叫,對本專案素材是否真的能跨過 1a 門檻。

## 工具

新增 `tools/mesh_gen/s4_openai_client.py`——**完全獨立於 Photoshop**,純 REST API 呼叫
(`urllib`,不依賴 `requests`,維持專案最小依賴慣例)。核心函式 `edit_image(rgba, mask_bool,
prompt, model, size, quality)`:
- mask 編碼採 OpenAI 官方慣例(與插件一致):alpha 0=可編輯、255=保留。
- key 只從環境變數 `OPENAI_API_KEY` 讀,絕不寫死。
- 每次呼叫都記錄 metadata(時間戳/tag/model/size/quality/prompt長度/mask覆蓋率/耗時/
  HTTP狀態/**API 回傳的真實 usage token 數**)到 `tools/mesh_gen/s4_data/openai_usage.jsonl`
  ——**不含 key、不含圖片內容**,append-only,git 追蹤。
- **不含**插件的五層像素對位管線(那是給「生成結果會漂移」的問題用的,本次先驗證核心能力
  本身有沒有用,對位是候選17後續才要解的獨立問題)。

新增 `tools/mesh_gen/s4_usage_dashboard.html`——純前端單檔用量儀表板(比照
`psd_preview.html`/`spine_inspector.html` 架構),讀 `openai_usage.jsonl` 顯示:呼叫次數/
成功失敗數/累積 input-output token/逐筆明細表/累積 token 折線圖。**誠實限制**:
`platform.openai.com`(定價頁)目前未在網路允許清單裡,查不到官方 $ 定價,儀表板只呈現
token 數(API 回傳的用量真值),不做 $ 換算——要換算金額需使用者自行對照 OpenAI 帳單頁,
或之後把 `platform.openai.com` 也放行。本次只做語法檢查(`node --check`),**未用
Playwright 做完整互動驗證**(環境未裝 playwright python 套件),與既有工具的驗證慣例有落差,
留意若後續要提升信心可補測。

## 第一次真實測試

材質:`機器人拆件/左手`(已知 1a 全 fail 的機械紋理代表材質,見 `s4-inpaint-evaluator.md`)。
挖洞:`punch_hole(mode="interior", frac=0.12, seed=0)`,與既有 CPU/LaMa baseline 同一組
參數,直接可比。裁切上下文:整層(215×256px,非孤立最小 bbox),resize 到 1024×1024(gpt-image
支援的標準尺寸之一;未做插件式的「1.2倍/512px下限」上下文擴展,先用最簡版)。
`quality="low"`(最低成本檔位,先驗證可行性)。

Prompt:「Restore the missing mechanical panel texture inside the masked hole so it
seamlessly continues the surrounding metallic surface: same panel lines, screws,
grooves, lighting direction and material finish. Keep everything outside the mask
exactly unchanged. Do not add new objects.」

**API 呼叫成功**(HTTP 200,耗時 16.7s,`usage`: input 1077 tokens〔含 1024 image + 53
text〕、output 196 tokens)。

### 量化結果(既有 1a/1b 評分函式,零改動)

| | premult_mae | ssim | seam_grad_diff | 1a pass | alpha_gap | seam_ratio | tone_gap | 1b pass |
|---|---:|---:|---:|:---:|---:|---:|---:|:---:|
| CPU 最佳(cv2_ns) | 21.3 | 0.441(身體)/0.177(左手) | 27.4 | ❌ | - | - | - | ✅ |
| LaMa(通用權重) | 9.2(身體) | 0.574(身體)/0.260(左手) | 22.3 | ❌ | - | - | - | ✅ |
| **gpt-image-2(本次,左手)** | **54.5** | **0.274** | **79.2** | ❌ | **0.0** | **1.631** | **5.04** | ✅ |

1a 依然 fail(ssim 0.274,比 LaMa 的 0.260 略高但同量級,仍遠低於 0.75 門檻;
premult_mae/seam_grad_diff 數字上看起來比 CPU/LaMa 更差)。1b 大幅 pass,且**三指標都是
本專案至今看過最好的數字**(tone_gap 5.04,遠低於既有機械紋理材質常見的 19~27)。

### ⚠️ 關鍵發現:1a 數字差是「評分方法論」問題,不是「補得差」——視覺證據直接矛盾量化結論

把三張圖(gt / 破洞 / gpt-image-2 補丁)並排看,補丁**視覺上完全看不出破綻**:材質風格、
紅色面板、關節反光、明暗方向全部一致,甚至自己加了一顆符合機械風格的螺絲細節。4x 放大
逐像素比對接縫處也看不到色調斷層或接縫痕跡——**跟同一批 CPU baseline 那種一眼可見的
「奶油糊」模糊完全不是同一個等級**。

那為什麼 ssim 只有 0.274、premult_mae 高達 54.5?因為**gpt-image-2 沒有重現 GT 那個特定的
關節凸起幾何形狀,而是生成了一個風格一致但形狀不同的合理替代方案**(關節弧度、高光位置、
螺絲位置都跟 GT 不同)。1a 的評分邏輯是「像不像這張特定的真值圖」(逐像素 ssim/mae),
但生成式模型的本質是「畫一個風格正確、看起來合理的內容」,不是「重建同一組像素」——**兩者
在方法論上就是在問不同的問題**。對「1a 需表演」的原始定義(如墨鏡拿掉後眼睛要眨眼)來說,
「有沒有特定內容存在」才重要,細節形狀通常不是唯一解;用逐像素 ssim 比對生成式輸出,
可能從一開始就是**用錯尺量錯東西**。

**誠實限制,n=1,不可過度推論**:
- 只跑了一個材質、一個洞、一次呼叫(`quality=low`,最低檔位),未做正負對照校準(候選17
  目前還沒有自己的「合成挖洞→打洞→比對」正負對照閘,借用的是既有 1a/1b 閘,但那兩個閘
  的設計前提〔逐像素比對 gt〕可能對生成式方法不公平,見上一段)。
- 未測試更高 `quality` 檔位(medium/high)是否能同時改善 1a 數字。
- 未套用插件式的像素對位管線(本次生成的圖恰好沒有明顯漂移/縮放問題,但這是運氣還是
  gpt-image-2 本身對齊夠好,只跑一次無法下結論)。
- 未測 edge 模式(咬輪廓的洞,理論上比 interior 更難)。

## 建議(留給下一 chunk)

1. **候選17若要繼續**,下一步應該是:**幫生成式方法設計專屬的評分方式**,而不是硬套 1a 的
   逐像素 ssim。候選方向:(a) 借用既有 1b 自我參照三指標(本次已經 pass,且數字是目前
   最佳)當生成式方法的主要驗收線;(b) 借用 chunk 18 已有的 vision-proxy 工具
   (`s4_vision_proxy_compare.py`)做「像不像有破綻」的視覺判定,這條路本來就不依賴 gt 的
   精確形狀比對,理論上更適合生成式輸出。
2. 擴大樣本(多材質、多洞、edge 模式、多 quality 檔位)前,先確認 1 是可行的評分方式,
   避免用不適合的尺重複量出「gpt-image-2 也不行」的錯誤結論。
3. 若要落地生產,插件的五層像素對位管線(`s4-gptfill-plugin-knowledge.md` §3)仍是必要
   工程,本次的巧合對齊不能當保證。

## 檔案

- 新增 `tools/mesh_gen/s4_openai_client.py`(獨立呼叫模組 + 用量記錄)。
- 新增 `tools/mesh_gen/s4_usage_dashboard.html`(用量可視化,純前端)。
- 新增 `tools/mesh_gen/s4_data/openai_usage.jsonl`(累加用量明細,git 追蹤,不含 key)。
- 未修改 `inpaint_eval.py`(候選17尚未正式接成候選 baseline,先用獨立腳本驗證可行性)。
