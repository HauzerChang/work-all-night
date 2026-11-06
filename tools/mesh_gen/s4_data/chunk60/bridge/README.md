# Codex bridge 任務包(切件來源:cut_sam_v4)
由 `s4_bridge_briefs.py` 產生。搬運方式(在你的 Windows 機器上,repo 根目錄):

    python tools/mesh_gen/s4_bridge_sync.py push "C:\Users\user\Desktop\切圖補圖研究\bridge"
    # bridge 跑完後(out/ 出現 *_filled.png):
    python tools/mesh_gen/s4_bridge_sync.py pull "C:\Users\user\Desktop\切圖補圖研究\bridge"
    git add tools/mesh_gen/s4_data/chunk60/filled && git commit -m "S4: bridge results" && git push

push:複製 `briefs/todo/*.md` → bridge\briefs\todo\,`ref/*` → bridge\ref\。
pull:複製 bridge\out\*_filled.png → repo `chunk60/filled/`,並帶回 logs 的 run/exit 檔供除錯。
驗收由下次排程執行(`s4_bridge_verify.py`:黑區逐像素不變 + 1b 閘 + 目視蒙太奇)。
