# S4 九尾狐 SAM 重切 v4:交叉靴分離 + 長髮主體 (chunk 308, 2026-11-06)
使用者授權雲端跑 MobileSAM(torch 2.15 PyPI CUDA 版在 CPU 可跑;`download.pytorch.org` 被 proxy 擋,PyPI 可;pip 對應 python3.13,`python3` 是 3.11 → 一律用 `python3.13`)。

## 結果(cut_sam_v4,19 件,AC1 pass)
| 件 | v2 問題 | v4 作法 | 量化 |
|---|---|---|---|
| boot_left/right | 重疊 73%(SAM 負點後反升到 90%:同材質相觸,SAM 把兩靴當一物件) | SAM 聯集(輪廓好)∩/− **前靴多邊形**(`s4_boot_split.py`,頂點由 3x 細格目視定) | 重疊 **0 px**,前靴 16256 / 後靴 7502,聯集流失 24 px |
| hair_main | 切到標題字/背景暗區(非髮) | 正負點重定(`decision_v4_pts.json`)→ SAM 仍合併紗袖+尾尖(淺色相鄰,負點無效)→ **圖層減法** `s4_layer_subtract.py`:−sleeve_left −hand_left −(tails_mass ∩ 尾尖框 ∩ 粉色 R−B>18) | 55069→43138 px;∩sleeve/hand 0;∩tails 10047(髮絲飄在尾巴上,屬正常前後關係) |

## 教訓
- SAM point prompt 對「同材質相觸」(兩靴)與「淺色相鄰」(髮/紗/毛)都分不開 → 用 SAM 取外輪廓、用幾何/色彩/圖層關係做內部切分,比繼續調點有效。
- 尾尖框純幾何減法會砍掉框內真髮絲;加色彩判準(框內 tails 像素 R−B 中位 22 vs 髮區 −14)才兩全。

## 產出
- `chunk60/cut_sam_v4/`、`chunk60/jiuwei_yanlian_decompose_v4.psd`(19 層,psd-tools 驗證)。v3 已刪(被 v4 取代)。
- bridge 任務包重產(`--cut cut_sam_v4`):7 張,新增 07_hair_main(7797 px);tails_mass 增列 hair_main 為遮擋件(48851 px)。
