# S4 Codex bridge 第二輪結果 (chunk 310, 2026-11-07)
`chunk60/filled_round2/`(3/3 有產出),驗收 `chunk60/verify_filled_round2/`(ref = commit 12e948b 的 bridge/ref)。

| 件 | 閘 | 目視 | 決定 |
|---|---|---|---|
| tails_mass | 1b(edge)fail:alpha_gap .21 — 外推帶誤擋 | 髮遮擋增量補毛自然 | **accept** |
| leg_right | 1b 不適用 | 兩條遮罩帶被畫成脫離腿部的粉色浮空長條(非輪廓延伸) | **reject** |
| hair_main | 1b fail:seam 1.21 | 右上矩形亮塊接縫 + 左下浮空雜點,劣於原件 | **reject** |

- 套用:`cut_sam_v4_filled` → `cut_sam_v5_filled`(僅 tails_mass)→ `jiuwei_yanlian_decompose_v6_filled.psd`。
- 命令:`psd_node/manifest_to_psd.js <manifest> <layer_dir> <out.psd>`(需先 `npm ci`)。
- leg_right 遮罩(兩條長帶)本身形狀不是「貼輪廓外擴」,即使措辭過濾解決也畫錯 → **需人決策**:重畫遮罩(貼靴口上緣一條帶)或接受 CPU/人工補;hair_main 同理需縮小遮罩(避免大矩形區)。
