# S4 拆解流程第3點:box-prompted 語意分割(MobileSAM)取代矩形裁切

> 使用者實測 chunk 46 的矩形裁切結果後明確反對:「只切出矩形 不符合我的需求, 我想要的
> 是 框選的範圍內 精準找到部件 並切割出來, 你需照偵測各種不規則的輪廓 進行提取」。這篇
> 記錄嘗試解決這個問題的完整過程,**包含失敗的部分**——不是只有成功案例。

## 候選1:OpenCV GrabCut(傳統色彩分割)—— 實測完全失敗

GrabCut 是 OpenCV 內建的 box-prompted 前景分割演算法,不需要額外下載模型,是最低成本
的候選,先試這個。對三個代表性部件(`head`/`choker`/`earrings`)分別用「純 rect 初始化」
跟「手動加 seed mask(框中心=一定前景、外圈=一定背景)」兩種模式測試,**三個全部選錯**:

- `head`:選到暗色背景區塊,完全沒抓到臉。
- `choker`:選到裸露肩膀的膚色區塊,不是頸飾本身。
- `earrings`:選到整張臉,不是耳環。

**根因**:GrabCut 只做顏色統計+空間連貫性分割,沒有「這是什麼物件」的語意理解。框裡如果
同時有一個小物件(耳環/頸飾)跟一大片視覺上更「顯著」的內容(臉、皮膚),它會選那個顯著
的大色塊,不管標籤寫的是什麼。這是插畫這種內部色彩變化大、前景背景界線本來就不乾淨的
素材的典型失效模式,不是參數沒調好。**結論:傳統色彩分割不適合這個任務,需要有學過
「物件」概念的模型。**

## 候選2:MobileSAM(box-prompted 語意分割)

[MobileSAM](https://github.com/ChaoningZhang/MobileSAM)(Apache 2.0,商用無虞)是
Meta Segment Anything(SAM)的輕量版:同樣的 box-prompted 介面,但用 TinyViT(5M參數)
換掉笨重的 ViT-H encoder(632M),CPU 可跑,權重僅 ~40MB。

### 取得方式(網路政策記錄,供未來重現)

`huggingface.co` 被 org 網路政策明確擋掉(gateway 403 policy denial),但 GitHub 的
`raw.githubusercontent.com`(檔案下載)可用(`codeload.github.com`、`api.github.com`
仍受這個 session 的 repo 授權範圍限制,擋掉;純 `git clone https://github.com/...`
走 git 協定則可用)。MobileSAM 剛好把權重直接放在 repo 裡(不像多數專案放
Google Drive/HuggingFace),因此改用 `raw.githubusercontent.com` 直接抓到:

```bash
# 權重(不進 git,見 .gitignore;需要時重新下載)
curl -sSL -o tools/mesh_gen/models/mobile_sam.pt \
  https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt
# sha256: 6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f

# mobile_sam 原始碼(非 PyPI 套件,需另外拿;Apache 2.0,同一個 repo)
git clone --depth 1 https://github.com/ChaoningZhang/MobileSAM.git /tmp/mobilesam_src

# Python 依賴(pypi.org 在允許清單內,不受限)
pip install torch timm
```

## 整合進 `s4_decompose_cut.py`

新增 `tools/mesh_gen/s4_sam_segment.py`(`SamSegmenter` 類別,封裝
`predictor.set_image()` + `predictor.predict(box=...)`)。`s4_decompose_cut.py` 新增
`--contour {rect,sam}` 參數(預設 `rect`,不動舊行為),`sam` 模式下對每個部件用
MobileSAM 找不規則遮罩,套進裁切結果的 alpha 通道(裁切窗口大小/offset 不變,manifest
格式不變,只是 alpha 從「整塊=255」變成「照 mask 形狀」)。`manifest_to_psd.js` 完全
不用改,因為它本來就吃任意 alpha,不是只認矩形。

### 每個 part 的 3 個候選遮罩怎麼選

SAM 的 box prompt 一次回傳 3 個候選遮罩(不同細節層級)+ 各自的信心分數。預設取分數
最高的一個。

### 自動信心判準(兩個 heuristic,兩者都是本次實測校準的經驗值,非普適常數)

1. `too_much_fg`:框內前景比例 ≥75%——通常代表框本身沒貼近目標物件,SAM 找不到可信的
   內部邊界,只好整框當前景。
2. `fragmented`:前景被切成好幾塊不相連的小碎片(最大連通元件占全部前景 <60%)——即使
   比例數字正常,視覺上明顯是雜訊而非一個部件的輪廓。

## 端到端真實測試:九尾焰蓮 20 部件(使用者親自調整過的決策檔,非草稿)

用 chunk 46 同一份使用者手動確認的決策檔,`--contour sam` 重跑,AC1 pass(20部件全部
產出)、AC3 因來源圖無 alpha 依規則 skip、AC2 資訊性(MAE 比矩形版更高,17.0/88.3 vs
矩形版4.4/32.2——**這是預期且合理的**,因為現在部件會主動排除不屬於自己的內容,跟
矩形版故意保留所有 bleed 的重組保真度本來就不是同一件事,數字變大不代表變差)。

**視覺逐格檢視,不只信任聚合指標跟自動 heuristic**——這次誠實的完整結果:

| 結果 | 部件 | 數量 |
|---|---|---|
| 明確正確(視覺確認乾淨對應標籤) | head, fox_ears, hair_front, choker, sleeve_left, tag_pendant, leg_right, boot_right, hand_left | 9 |
| 自動 heuristic 正確標記為 low_confidence | earrings(too_much_fg)、sash_train(fragmented) | 2 |
| 已知本來就難(Claude 第1/2點分析時已標低信心) | hair_main、tails_mass(同材質大範圍重疊) | 2 |
| **自動 heuristic 沒標記,但人工目視確認選錯(靜默失敗)** | bodice(選到頭髮)、leg_left(選到布料)、boot_left(選到布料)、sleeve_right(選到胸衣)、hand_right(選到袖子布料) | 5 |
| 含糊/部分正確,難判定 | belt、skirt | 2 |

**20 個部件裡有 5 個(25%)是自動信心判準完全沒抓到的靜默錯誤**——這是這次測試最重要
的誠實發現,不能被「9個明確正確+2個成功攔截」這種正面敘事蓋過去。

### 靜默失敗的共同模式:框跟鄰近部件重疊,SAM 選到了鄰居的內容

觀察這 5 個錯誤案例,共同點很清楚:每一個都是原始框跟**相鄰部件的視覺內容大幅重疊**
(`sleeve_right` 框跟 `bodice` 的紅色胸衣重疊、`hand_right` 框跟白紗袖子重疊、
`boot_left`/`leg_left` 框跟飄逸的紅色布料裝飾重疊)。SAM 是在「找框裡最像一個獨立物件
的東西」,如果框裡剛好有兩個都算「合理獨立物件」的候選(自己的部件 vs 鄰居部件的一角),
它選錯的機率不小,而且**選錯之後產生的遮罩通常形狀乾淨、信心分數不低**,兩個 heuristic
(前景比例、破碎度)都抓不到,因為問題不是「找不到清楚邊界」,是「清楚地找到了錯的邊界」。

## 誠實結論

- **比 GrabCut 好非常多**(GrabCut 3/3 全錯 vs MobileSAM 9/20 明確正確+2/20 正確攔截
  低信心),證實「需要語意理解的模型」這個判斷方向正確。
- **不是解決方案,是進步**:25% 靜默錯誤率意味著這個 pipeline 目前**不能盲目信任自動
  輸出**,每次跑完都需要人工視覺複核(跟這次的做法一樣)。
- 已知的下一個改進方向(本次未實作,留待使用者決定是否值得投入):
  1. **點提示(point prompt)輔助**:SAM 原生支援框+正/負點的組合提示,不只是純框。
     在 assist viewer 加一個「點一下目標物件內部」的可選步驟,對這 5 個靜默失敗案例
     這種「框內有多個候選物件」的情況,一個正向點提示很可能直接解決歧義——比純框精準
     很多,但需要使用者多做一步互動。
  2. **收緊原始框**:失敗案例的框普遍偏鬆(涵蓋了鄰居部件的一大塊),收緊決策檔階段的
     框邊界(讓框更貼近目標物件本身)能直接降低歧義,不需要改分割演算法本身。
  3. 兩者可以並行:先嘗試收緊框(較低成本),仍有歧義的部件再加點提示。
- AC 自動閘門(low_confidence 標記)是有用的三角警訊,但**不是品質保證**——這次的兩個
  heuristic 加起來只抓到 2/7 個真正有問題的部件,使用者不能只看「有沒有被標記」就信任
  結果。

## 檔案

- 新增 `tools/mesh_gen/s4_sam_segment.py`(SamSegmenter 封裝 + 兩個 low_confidence
  heuristic)。
- 更新 `tools/mesh_gen/s4_decompose_cut.py`(`--contour {rect,sam}` 參數,預設不變)。
- `tools/mesh_gen/models/mobile_sam.pt`(權重,~40MB,已加入 `.gitignore`,見上方
  重現指令+sha256)。
- 未修改 `psd_node/manifest_to_psd.js`(不需要,已支援任意 alpha 形狀)。
