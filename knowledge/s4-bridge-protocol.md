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
