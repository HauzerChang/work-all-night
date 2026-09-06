# S4 — 九尾焰蓮拆解:第二份完整組裝 PSD,`skirt` 點提示正式落地(chunk 57)

## 背景

chunk 56 把「SAM 輔助點提示」接線進 production(`s4_sam_segment.py`/`s4_decompose_cut.py`/
`s4_decompose_assist.html`),並用真正的 `s4_decompose_cut.py --contour sam --eval` 驗證過
`skirt` 加一個正向點確實能修正 chunk54/55 發現的靜默錯誤(SAM 選到皮膚而非裙擺紅布)。但
chunk56 留下明確的誠實限制:驗證用的 `decision_with_points.json` 只是 `tools/mesh_gen/
s4_data/chunk56/` 下的臨時檔,**不是**拿去組裝正式 PSD 的那份決策檔——`skirt` 的點還沒有
真正「落地」。本次(chunk57)承接這個唯一候選,把點正式寫進一份新的官方決策檔快照,重跑
完整 pipeline,組出第二份 SAM-contour 的 production PSD。

## 執行

1. **官方決策檔快照**:以 chunk53 的 `decision_final.json`(chunk47-52 全部框位置修正的
   最終結果,也是第一份 production PSD 的來源)為基準,只疊加 chunk56 驗證過的
   `skirt.points = [{"x":290,"y":420,"label":1}]`,存成
   `tools/mesh_gen/s4_data/chunk57/decision_final.json`。逐欄位比對確認**除了 `skirt`
   之外,20 個部件裡其餘 19 個跟 chunk53 基準完全一致**(純加法,無意外改動)。
2. 重裝環境依賴(容器不持久化,沿用 chunk54/56 記錄的可重現指令):
   `mobile_sam.pt` 權重(sha256 `6dbb9052...e37d6c2f`,跟 chunk54/56 記錄一致)+
   `git clone --depth 1 MobileSAM` 原始碼 + `pip install torch timm`(預設 PyPI index,
   不指定 `--index-url` 才能裝,同 chunk54 記錄的網路限制)。
3. 跑 `python3 tools/mesh_gen/s4_decompose_cut.py assets/jiuwei_yanlian_char_crop.png
   tools/mesh_gen/s4_data/chunk57/decision_final.json -o tools/mesh_gen/s4_data/chunk57/
   cut_sam --contour sam --sam-src /tmp/mobilesam_src --eval` → 20/20 部件產出,
   `AC1_parts_produced.pass=true`。
4. `npm install`(`tools/mesh_gen/psd_node`,同 chunk53 需重裝)+ `node manifest_to_psd.js
   ../s4_data/chunk57/cut_sam/manifest.json ../s4_data/chunk57/cut_sam
   ../s4_data/chunk57/jiuwei_yanlian_decompose_sam.psd` → 20 圖層 PSD。

## 自我驗證

1. **決策檔純加法**:`chunk57/decision_final.json` 與 `chunk53/decision_final.json` 逐
   part 比對,**只有 `skirt` 一項不同**(多了 `points` 欄位),其餘 19 項位元級相同。
2. **`skirt` 分割結果重現 chunk56 的加點版**:`sam_info` = `fg_ratio_in_box=0.4478,
   n_components=1, largest_component_frac=1.0`,跟 chunk55 ad-hoc 驗證、chunk56
   production 驗證的數字完全一致;裁圖 `12_skirt.png` 視覺複核為乾淨裙擺紅布(含金色
   刺繡),無皮膚色塊。
3. **其餘 19 個部件的 `sam_info` 逐欄位比對 chunk56 `cut_sam_points/manifest.json`**
   (chunk56 用臨時決策檔跑的加點版):**完全相同,0 處差異**——證明用正式快照重跑跟
   臨時驗證檔案的行為等價,純粹是「把驗證過的東西正式收進 repo」,沒有引入任何新變數。
4. **AC1(裁切)**:20/20 產出,`overall_pass: true`。
5. **AC2(PSD 圖層幾何 round-trip)**:`psd-tools` 重開 `jiuwei_yanlian_decompose_sam.psd`,
   逐圖層比對 manifest 的 `name`/`offset`/`size`——**20/20 完全相符**。
6. **AC3(PSD 圖層像素 round-trip,premultiplied-alpha 比對)**:每圖層 `composite(
   force=True)` 跟 `cut_sam/` 對應裁圖 PNG 比對——**alpha 通道 20/20 `max_diff=0`**,
   **premultiplied RGB 20/20 `max_diff=0`**(位元級無損)。
   ⚠️ **踩到一個新坑並修正判準(不是新增限制,是驗證方法要跟著 contour 方法調整)**:
   第一次直接比較**straight-alpha RGBA**(chunk53 的原始比法)在全部 20 層都回報
   `max_diff` 高達 247~255,看起來像嚴重回歸。追查後發現:chunk53 是矩形裁切,整張
   crop 永遠 alpha=255,straight RGBA 比對不會踩到任何「alpha=0 處 RGB 未定義」的
   邊界情況;chunk57 是 SAM 遮罩,每個部件現在**真的有 alpha=0 的透明像素**,這些像素
   底下的 RGB 數值在 PNG 檔案與 PSD 重新合成之間本來就沒有保證要一致(視覺上不可見、
   無意義),straight RGBA 比對會被這類「看不見的顏色雜訊」誤判成回歸。改用
   `CLAUDE.md`/`RULES.md` 一貫要求的 **premultiplied-alpha** 比對法(`RGB×alpha/255`)
   後,20/20 `max_diff=0`——證明其實完全無損,上一步的「失敗」是比對方法沒跟著遮罩式
   裁切調整,不是 round-trip 真的壞了。**教訓記錄:凡是引入非矩形/非全不透明的裁切
   結果,像素級 round-trip 驗證一律要用 premultiplied-alpha,不能沿用「straight RGBA
   逐像素比對」這個只在全不透明矩形場景下才安全的捷徑。**
7. **視覺複核已知問題部件維持原狀、無新回歸**:`bodice`(06_bodice.png,選到深色髮絲
   非紅色胸衣)、`sleeve_right`(08_sleeve_right.png,選到紅色胸衣非白紗袖)、
   `hair_front`(02_hair_front.png,選到狐耳非額前瀏海)——三者裁圖內容跟 chunk54 文字
   描述的失敗模式完全吻合,是**已知未解案例的延續呈現**,不是本次新引入的缺陷。
   `head`/`sash_train` 這次同樣被 heuristic 正確攔截(`low_confidence=true`),跟
   chunk54 記錄的攔截結果一致(同一份決策檔、同一組框,理論上必須一致,已驗證確實如此)。
8. **額外誠實觀察(非缺陷,是 SAM 遮罩式裁切的預期特性)**:整份 PSD 攤平 `composite(
   force=True)` 後畫布透明像素比例 `46.2%`(跟 chunk53 矩形版的「100% 不透明、
   AC3_no_orphan 略過」形成對比)。這**不代表遺漏內容**——來源圖是帶大量留白背景/
   版面文字的角色設定圖,SAM 只框住 20 個角色部件本身的緊貼輪廓,原本矩形裁切靠鄰接
   部件互相 bleed 才「意外填滿」的背景/空隙,在遮罩後如實留空,這正是這份 PSD 相對
   chunk53 版本「輪廓更乾淨、bleed 更少」的代價與證據,兩者一致、非回歸。

## 誠實限制

- **仍未解的三個已知案例原樣保留**:`bodice`/`sleeve_right`(chunk48 已測 4 次點提示
  無效,A 類岔路,需使用者裁決:接受現狀/人工摳圖/放棄)、`hair_front`(跟 `head`/
  `fox_ears` 語意邊界大幅重疊,需使用者用 assist viewer 手動確認)。這份 PSD 是
  「skirt 已修正、其餘維持 chunk54 已知狀態」的快照,不是最終定案。
- `head`/`sash_train` 兩個部件的 SAM 分割仍被 heuristic 標記 `low_confidence`
  (fragmented),PSD 裡對應圖層內容不可信,沿用 chunk54 已知結果,本次未處理。
- 這份 SAM-contour PSD(`jiuwei_yanlian_decompose_sam.psd`)跟 chunk53 的矩形版
  (`jiuwei_yanlian_decompose.psd`)是**兩份平行產出**,不是取代關係:矩形版所有部件
  輪廓可靠但有 bleed;SAM 版對 ~16/20 部件輪廓更乾淨,但 `bodice`/`sleeve_right`/
  `hair_front`/`head`/`sash_train` 這 5 個部件的內容不可信賴,使用哪一份要看下游用途
  (若要各部件乾淨輪廓且能接受這 5 個已知案例還要另外處理,選 SAM 版;若要保守但全部
  部件輪廓可靠,選矩形版)。
- 未做第4點 GPT 局部修補(需 API key 授權,同候選17阻塞點,跟 chunk53 相同限制)。
- `tools/mesh_gen/psd_node/node_modules/`、torch/timm/MobileSAM 原始碼與權重皆為本次
  容器內暫存,不預期持久化,下次排程需依上方「執行」步驟2重裝。

## 檔案

- 新增 `tools/mesh_gen/s4_data/chunk57/decision_final.json`(官方決策檔快照,
  chunk53 基準 + `skirt.points`)、`tools/mesh_gen/s4_data/chunk57/cut_sam/`
  (20 張部件 PNG + composite.png + manifest.json)、
  `tools/mesh_gen/s4_data/chunk57/jiuwei_yanlian_decompose_sam.psd`(第二份完整
  20 圖層 PSD,SAM contour)。
- 未修改任何既有 production 代碼(`s4_decompose_cut.py`/`s4_sam_segment.py`/
  `manifest_to_psd.js` 沿用 chunk56 版本,零改動,本次純資料/產出)。
