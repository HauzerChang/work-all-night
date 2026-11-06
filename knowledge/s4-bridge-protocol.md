# S4 Codex bridge 協定與任務包 (chunk 306, 2026-11-06)
協定來源:skill `codex-bridge`(bridge = 使用者 Windows 上的 PowerShell 常駐迴圈,輪詢 `briefs\todo\` 呼叫 `codex exec`)。
- 資料夾:`briefs\todo\`(待辦)、`running\`、`done\`、`failed\`、`ref\`(參考圖)、`out\`(產出)、`logs\`(`bridge_status.json` UTF-8 BOM、`<name>.run.txt/.exit.txt`)。
- 任務單:一圖一 `.md`,首行 `images: ref/a.png,ref/b.png`(相對 bridge 根),結尾 ``Save the result as `out/xxx.png` ``(bridge 據此判定成功)。bridge 固定叫 Codex 讀 `briefs/00_style.md` → 任務單明寫不適用。
- 使用者的 bridge 路徑:`C:\Users\user\Desktop\切圖補圖研究\bridge`。雲端排程 session **無本機裝置工具**(remote-devices 未掛載),無法直接寫入;需使用者在本機執行 `s4_bridge_sync.py` 或在「已連接裝置」的 Claude 桌面/網頁 session 操作。
## 任務包
`tools/mesh_gen/s4_bridge_briefs.py` → `s4_data/chunk60/bridge/`:6 張任務單(tails_mass 36187px、skirt 865、head 4520、sleeve_left 1628、leg_left 1414、leg_right 1096)+ `ref/<id>.png`、`<id>_mask.png`(白=補)、`<id>_preview.png`、`composite.png`。
需補區 = 件 ∩ 遮擋件(顏色污染)∪ 輪廓外 R px 延伸帶 ∩ 遮擋件(外推);R 依件 6–14。
hair_main 不在包內(切件錯誤,待 SAM 重切後再加)。
## 決策
- tails_mass:**保留整塊(方案 A)**,補圖只需 1b 寬鬆閘(動態下不露洞)。拆束留待有動畫需求時再議。
## 驗收(下次排程,`s4_bridge_verify.py` 待寫)
1. 尺寸 460x898、RGBA;2. 遮罩黑區與原件逐像素相同(alpha 含);3. 白區 alpha_gap/seam_ratio/tone_gap 1b 閘;4. 蒙太奇目視。

## 驗收器 `s4_bridge_verify.py`(chunk 307 校準)
- 流程:尺寸(等比可縮放、否則 FAIL)→ 黑區漂移只記錄(合成一律以原件覆蓋黑區,bridge 重編碼不影響)→ 合成 `verify/composed/<id>.png` → 白區三指標 → 蒙太奇。
- 指標/門檻:`white_region_alpha_gap` ≤0.05(沒畫=必擋);`white_region_grad_ratio`(白區內部梯度 / 周圍 21px 環帶)≤1.25 — 校準:噪聲 1.34–2.78、nearest/telea 0.18–0.60、真實紋理件 ≤0.95;1b 閘(score_1b,mode 自動)。
- 判定三態:**pass**(三項皆過)/ **None=需目視**(1b 不適用,如腿:洞吃掉整段輪廓)/ **fail**。
- 自測 `--selftest`:6 件 × {nearest 正對照, empty, noise, wrongsize} = 24 案例 → 正 4 pass + 2 目視、負 18 全擋。
- 已知盲點:head 的 noise 只靠 grad_ratio 擋(1b 誤 pass)→ 1b 單獨不可信,三指標須同時看。
