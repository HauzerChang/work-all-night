# S4 chunk 54:框位置修正後重跑 `--contour sam`,驗證是否解決 chunk47 的靜默錯誤

> 承接 chunk47「MobileSAM box-prompted 分割 20 部件裡 5 個(25%)靜默錯誤」與
> chunk49-53「逐一修正 `suggestions.json` 決策檔框位置錯誤」——chunk47-53 每一次都在
> 結尾記錄「未重跑 `--contour sam`」。本次補上這個一直被延後的驗證:**框位置修好之後,
> SAM 的靜默錯誤是否也一併解決?**

## 環境準備(可重現)

容器不持久化這些依賴,每次需要重裝:

```bash
mkdir -p tools/mesh_gen/models
curl -sSL -o tools/mesh_gen/models/mobile_sam.pt \
  https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt
git clone --depth 1 https://github.com/ChaoningZhang/MobileSAM.git /tmp/mobilesam_src
pip install torch timm   # 注意:download.pytorch.org 被擋(403),改用預設 pypi.org index 可裝
```

`pip install torch` 走預設 PyPI(不指定 `--index-url`)成功;`--index-url
https://download.pytorch.org/whl/cpu` 這個常見寫法本次環境**連不上**(proxy 403),
供未來重現時省一次排查。

## 跑法

用 chunk53 定案的決策檔快照(`tools/mesh_gen/s4_data/chunk53/decision_final.json`,即
chunk47-52 全部框位置修正的最終結果)重跑:

```bash
python3 tools/mesh_gen/s4_decompose_cut.py \
  assets/jiuwei_yanlian_char_crop.png \
  tools/mesh_gen/s4_data/chunk53/decision_final.json \
  -o tools/mesh_gen/s4_data/chunk54/cut_sam \
  --contour sam --sam-src /tmp/mobilesam_src --eval
```

AC1(20/20 產出)pass。輸出 `manifest.json` 每個部件附完整 `sam_info`
(scores/fg_ratio_in_box/n_components/largest_component_frac/low_confidence)。

## 結果:框修好解決了「框完全落錯」類錯誤,但沒解決「框正確、SAM選錯」類錯誤

### ✅ chunk49-52 修正的 5 個部件,這次用 SAM 分割視覺確認全部正確

| 部件 | chunk47 原始結果 | 本次(框修正後)SAM 結果 |
|---|---|---|
| `leg_left` | 靜默錯誤(選到布料/絲帶) | ✅ 乾淨大腿膚色輪廓 |
| `boot_left` | 靜默錯誤(選到布料/絲帶) | ✅ 乾淨靴筒輪廓 |
| `hand_left` | (chunk47未列入失敗,但chunk50發現決策檔草稿其實框錯) | ✅ 乾淨左手(纏繞絲帶+五指) |
| `hand_right` | 靜默錯誤(選到袖子布料) | ✅ 乾淨右手 |
| `tag_pendant` | (chunk47測試用的框跟這份決策檔不同版本,未直接對照) | ✅ 乾淨符紙木牌形狀 |

證實「框從一開始就沒框到目標」這類錯誤,源頭修正框位置後,SAM 不需要任何演算法改動
就能正確分割——這類錯誤本質是決策檔品質問題,不是 SAM 的能力問題,chunk48 的判斷
(「不管換哪種分割演算法都救不回來,正確修法是回頭重新框」)在這次端到端重跑中被完整驗證。

### ❌ 已知「框正確、SAM選錯鄰居內容」案例,框修正後依然失敗(不意外,但首次在最終決策檔上確認)

- **`bodice`**:框內容確認正確(chunk48 已驗證是紅色胸衣衣料),SAM 這次選到的仍是
  深色髮絲形狀,不是胸衣。
- **`sleeve_right`**:SAM 這次選到的是紅色胸衣主體(`bodice` 的內容),不是白紗袖子。

兩者都不在自動 heuristic 的攔截範圍內(`low_confidence=False`)——跟 chunk47 的結論
一致:這類錯誤的遮罩形狀乾淨、信心分數不低,heuristic 抓不到。

### 🆕 本次新發現的靜默錯誤:`skirt`

chunk52 複核判定 `skirt` 框正確(裁圖確認主體是裙擺紅色衣料,夾帶手/前臂/大腿是矩形
裁切的正常 bleed),但**這是用矩形裁切驗證的**,從未拿去測過 SAM。這次用 SAM 分割,
結果選到的是**皮膚(手臂/大腿)形狀**,不是裙擺紅色衣料主體——同一種「框正確但SAM選到
框內另一個更顯著的候選物件」模式,heuristic 同樣沒攔截(`fg_ratio=0.20`,
`largest_component_frac=0.82`,兩個門檻都沒觸發)。**這是本次排程唯一新增的、之前
沒被任何 chunk 記錄過的靜默錯誤案例。**

### 🆕 `head` 這次被 heuristic 正確攔截(`fragmented`,`largest_component_frac=0.56`)

chunk51 才把 `head` 框從畫面最上方文字區改到正確的臉部位置(用 `cut_rect` 裁圖已視覺
確認是完整臉部,見 `tools/mesh_gen/s4_data/chunk53/cut_rect/00_head.png`)。但這次用
**正確的框**跑 SAM,分割結果仍然錯誤(選到類似兜帽/髮絲飄動的形狀,不是臉),不過這次
**heuristic 有正確標記 `low_confidence`**(前景碎成4塊,最大連通元件只佔56%)——跟
chunk47 用的是完全不同的框(chunk47當時的框本身位置有問題,這次是框正確、純粹分割本身
在「臉部 vs 大範圍頭髮」這種邊界複雜的目標上失效),heuristic 這次表現正確,不是巧合
攔截。

### `hair_front` 的失敗是已知重疊問題的具體化,不是新問題

`hair_front` 這次 SAM 選到的內容跟 `fox_ears` 幾乎一樣(耳朵形狀),對照 chunk53
的 `cut_rect` 裁圖(`02_hair_front.png`)可見框本身涵蓋了臉/雙耳/瀏海一大片重疊區域
——這正是 chunk51 已經記錄、留給使用者用 assist viewer 判定的「`hair_front` 跟
`head`/`fox_ears` 新框大幅重疊」問題,這次只是用 SAM 具體示範了這個重疊會讓分割選到
錯的子物件(耳朵而非瀏海),沒有新增獨立問題。

### 其餘 13 個部件:視覺複核確認正確

`fox_ears`、`choker`、`sleeve_left`、`belt`、`leg_right`、`boot_right` 逐一開圖確認
形狀對應標籤內容;`hair_main`/`tails_mass`/`sash_train` 屬 chunk47 已知的「同材質大範圍
重疊,本來就難」類別(`sash_train` 這次也被 heuristic 正確標記 `fragmented`)。

## 統計與結論

框位置修正(chunk49-52)讓 SAM 分割的**正確率明顯提升**(至少 5 個部件從錯誤變正確),
證實這類修正是有效槓桿。但**沒有改變 SAM 本身「框正確時仍可能選到框內其他顯著候選物件」
這個核心限制**——這次 20 部件裡仍有至少 4 個(`bodice`/`sleeve_right`/`skirt`/
`hair_front`,20%)是這個模式的靜默或半靜默錯誤,跟 chunk47 的 25% 落在同一量級。
**heuristic 攔截率這次是 2/20(`head`/`sash_train`),對真正有問題的 ~5-6 個部件來說
攔截率仍偏低**,呼應 chunk47 的誠實結論:「這批 heuristic 是三角警訊,不是品質保證」。

**沒有改動任何 production 代碼**(`s4_decompose_cut.py`/`s4_sam_segment.py` 本次原封
不動),純粹用既有工具重跑既有已修正的決策檔做驗證。

## 誠實限制

- 只驗證了框修正後 SAM 是否正確,**沒有嘗試修正新發現的 `skirt`/`bodice`/
  `sleeve_right`/`hair_front` 這 4 個 SAM 選錯案例**——`bodice`/`sleeve_right` 是
  chunk47/48 已確認的演算法歧異案例(點提示已測試 4 次無效,見 `s4-sam-segment.md`);
  `skirt` 是本次新發現,尚未嘗試任何修法;`hair_front` 待使用者用 assist viewer 裁決
  語意邊界後才能重新框。
- 未產出第二份 SAM 版 PSD 交付物(不同於 chunk53 的矩形版)——因為已知至少 4 個部件
  內容錯誤,現在組 PSD 意義不大,留到上述問題解決後再組。
- 未重新測試點提示(point prompt)對 `skirt` 這個新案例是否有效——這是合理的下一步
  候選,但屬於新的有界工作塊,本次未做。

## 檔案

- 本次未新增/修改任何 `tools/mesh_gen/*.py` 生產代碼。
- 輸出:`tools/mesh_gen/s4_data/chunk54/cut_sam/`(20 部件 PNG + `manifest.json` 含
  `sam_info`,及 `composite.png`)。
