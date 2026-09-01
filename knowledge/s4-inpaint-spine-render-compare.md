# S4 候選16路徑(b):補圖貼回真實 Award spine 場景,headless 動畫截圖比對(2026-09-01,chunk 23)

> 承接 STATE_S4.md/`knowledge/s4-inpaint-1b-lenient-gate.md` 候選16:路徑(a)「幫 1b 加第4個
> 自我參照指標」的兩次具體嘗試(候選18邊界證據延續性、候選20局部高頻能量/方差比)都已排除
> (各自撞到不同的結構性根因)。路徑(b)「把補圖貼回真實 `assets/Award.json/atlas/png`,在
> 真實動畫時間軸上截圖比對」是候選16唯一未嘗試、且不依賴發明新自我參照指標的路徑——本次把它
> 做出來,對一個真實案例(機器人拆件/左手)完整跑通一次。

**結論(單一案例,見下方誠實限制)**:在真實動畫的實際渲染尺度下(這個材質在 900×900 全場景
截圖裡只佔約 70×60px),候選7(vision代理)已知的「高頻細節丟失/奶油糊」瑕疵**確實還在**,
但**不構成一眼可見的接縫/破洞/色差**——要放大 10 倍盯著一塊 32×32px 的小窗格才看得出補丁處
少了一點原本材質的摺痕反光細節。兩個獨立動畫時間點(`Award_Legend_In` t=0.533、
`Award_Legend_Loop` t=0.6)得到同一個結論。這是候選16最初想問的問題(「動態動畫尺度下會不會
穿幫」)的第一手直接證據,比候選7的「靜態單層裁切+人工6x放大」代理更貼近實戰條件。

## 新增工具(`tools/mesh_gen/`,遵守檔案隔離契約)

1. **`atlas_patch.py`** —— `atlas_crop.py` 的逆操作,把補好的 region 貼回 atlas 貼圖頁。
   同一套 xy/size/rotate 幾何規則(見該檔開頭註解),`rotate=true` 用
   `cv2.ROTATE_90_COUNTERCLOCKWISE`(`atlas_crop` 還原用的 CW 之精確反旋轉,純像素重排無插值)。
   **自我驗證**(`--selftest`,不需要 spine 渲染):extract→原封不動貼回→跟原檔整頁逐位元比對,
   對 `robot_parts` 5 個 region(含 `rotate=false` 的左手/頭、`rotate=true` 的身體/光暈/右手)
   全部 `max_diff=0` PASS——證明 `paste_region()` 是 `crop_region()` 的精確逆函式。

2. **`s4_spine_render_harness.html`** —— 新的 headless spine-webgl 渲染 harness,**不可用既有
   `spine_inspector.html`**:它的 `TextureAtlas` textureLoader 固定回傳同一張貼圖
   (`atlas=new spine.TextureAtlas(atlasText, ()=> realTex||placeholder)`,見該檔第283行),
   對單頁 atlas(main_draw)沒問題,但 **Award 是雙頁 atlas**(`機器人拆件/左手`/`頭` 在
   `Award.png`,`光暈`/`右手`/`身體` 在 `Award2.png`)——用 spine_inspector 載入會讓其中一頁
   全部貼錯圖。本 harness 的 textureLoader 依 `TextureAtlas.load()` 傳入的 page 檔名字串分派到
   各自預先載入好的 texture(spine-webgl 原生支援的用法,`page.texture = textureLoader(line)`,
   `line` = page 檔名,同步呼叫,見 spine-webgl.js 原始碼)。也新增 `getPoseBounds()`/
   `setCameraFit()` 供 Python 端跨動畫取樣時間點算相機聯集(見下方「踩到的坑」)。
   只放在 `tools/mesh_gen/`,未改動 `spine_inspector.html`。

3. **`s4_award_screenshot_compare.py`** —— 端到端 orchestrator:切 atlas 解析度 region(不是
   PSD 解析度——這才是實際渲染用的貼圖,呼應 `knowledge/s4-psd-to-spine-real.md` 的 atlas 0.70
   縮放發現)→ `inpaint_eval.punch_hole` 挖洞 → `score_candidates`+`select_best`(1b 盲選,
   真實情境無 gt 可用,同 `psd_inplace_patch.py --auto` 的鏈路)→ `atlas_patch` 貼回一份
   `Award.png` 副本 → 組 `orig/`/`patched/` 兩份完整場景目錄(json+atlas+雙頁png)→ 本機
   `http.server` 服務 + 產生一個 Node/Playwright 腳本跑 harness → 截全場景圖 + 用
   `getScreenBox()` 換算出目標 slot 的實際螢幕像素框裁小圖比對(不額外放大,呈現真實播放
   尺度)+ 存一份 6x 放大版供人眼複查。

## 踩到的坑(修正後才可信)

**相機框架:不能只用 setup pose 框相機。** 第一版直接沿用 `spine_inspector.html` 的
`fitView()`(只在 `skeleton.setToSetupPose()` 下算一次骨架包圍盒),對 `Award_Legend_In`
這種「爆衝」動畫(材質瞬間飛出、伴隨粒子/相機震動範圍遠超過站立姿態的包圍盒)會讓相機框架
在動畫中段嚴重偏移,量到明顯不合理的螢幕框(寬度 320~365px 佔畫布 36~40% 寬,某些時間點
高度甚至算出負值,代表世界座標的一角被算到相機視野外)。**修正**:改成兩段式——先用
`orig` 場景跑過全部取樣時間點的 `getPoseBounds()`(每個時間點姿態下的整體骨架包圍盒)取
聯集,relaunch 前用 `setCameraFit()` 把相機固定在這個聯集框(留 15% margin),`orig`/`patched`
兩邊套同一個固定相機才能公平比較,也讓截圖呈現的框架更接近「這段動畫實際會用到的可視範圍」。
修正後 11 個時間取樣點的螢幕框穩定在 60~76px 寬、59~64px 高(唯一例外是動畫剛開始
`scale` timeline 還在 0→1 過渡的極早期幾格,材質本來就還沒长开,框小屬預期)。

## 本次真實案例:機器人拆件/左手

**選材理由**:`左手` 是既有 1a fail(機械紋理,CPU baseline 補不出細節)/1b pass(接縫層級
不突兀)的代表材質,前面多個候選(1/2/7/9/11/18/20)都用它當主要測試對象,結論可與既有證據
直接對照;`rotate=false`(atlas 幾何最簡單,降低本次新工具本身的風險);只在
`Award_Legend_In`/`Award_Legend_Loop`/`Award_Legend_Out` 三支動畫有 attachment timeline
(其餘 9 支動畫此 slot 一律不顯示,setup pose 也無 base attachment)。

**補洞**:atlas 解析度裁切 181×152 → `punch_hole(mode="interior", frac=0.12, seed=0)` →
洞面積佔內容面積 11.3%。**1b 盲選結果**:`nearest` 勝出(`chosen_reason="pass_1b"`,
`alpha_gap=0.0, seam_ratio=0.482, tone_gap=0.764`,三項皆 pass)——跟候選 1b 專用寬鬆閘章節
既有的「身體/左手 CPU baseline 在 1b 下全 pass」結論一致,非新結果。

**渲染驗證(11 個取樣時間點,`Award_Legend_In`×6 + `Award_Legend_Loop`×5)**:

- **多頁貼圖隔離正確**:對整張 900×900 全場景截圖逐像素比對 orig vs patched,差異像素
  **只有 205 px**,精確落在目標 slot 的螢幕框內(bbox 完全對應),場景其他部分(含同頁的
  `頭`、其他頁的 `光暈`/`身體`/`右手` 等 40+ slots)**零差異**——證明 harness 的雙頁貼圖路由
  正確,只動了該動的像素,沒有洩漏到其他 slot/page(這正是 `spine_inspector.html` 做不到、
  必須新建 harness 的原因,見上方)。
- **實際螢幕佔比**:目標 slot 在 900×900 全場景截圖裡只佔約 70×60px(≈0.5~0.6% 畫布面積)——
  這是「相機框住整個 LEGEND WIN 爆衝特效」下的真實佔比,不是候選7那種刻意裁切放大的孤立視角。
- **MAE(洞區螢幕框內,orig vs patched)**:動畫剛開始(材質 scale 0→1 過渡中)為 0(兩邊都
  接近看不見,合理);材質完全长开後穩定在 0.9~1.05(0~255 尺度)——量級很小,量化上就不是
  「一眼突兀」的量級。
- **人眼複查(10x 放大目標區域附近 32×32px 窗格,兩個獨立時間點)**:`Award_Legend_In` t=0.533
  與 `Award_Legend_Loop` t=0.6 兩張獨立比較都顯示**同一個模式**——沒有透明殘留、沒有色差、
  沒有硬接縫,補丁區域跟周圍風格融合;唯一看得出的差異是材質中段一道摺痕反光細節在補丁處被
  抹平了一點點(呼應候選7「奶油糊」的同一種瑕疵),但這個程度的模糊在這個實際渲染尺度下
  **不構成視覺上的「穿幫」**——需要刻意放大盯著看才看得出來,正常播放速度/縮放下大機率不會
  被注意到。

## 誠實限制

- **單一案例**:只測了 `左手` 一個材質、一個 seed(0)、一個 frac(0.12)、1b 盲選出的一個
  方法(`nearest`)。候選7已知 `身體`(另一個 1a fail/1b pass 機械紋理材質)也有同類瑕疵,
  本次未驗證其在真實動畫尺度下是否呈現相同的「不明顯」結論——`身體` 在 Award 的實際渲染尺寸
  未知,不能直接套用本次 `左手` 的「佔比小所以不明顯」推論。
- **相機框架是本次的方法論選擇,非遊戲真實相機的直接證據**:用「整段動畫骨架包圍盒聯集
  +15% margin」框相機,是為了讓 orig/patched 公平比較且不被爆衝動畫甩出視野的合理近似,
  但**不確定實際遊戲(lula slot game / Cocos Creator)在正式畫面上用的相機縮放跟這個是否一致**
  ——如果實機把這個特效放得更大(例如全螢幕居中特寫),目標材質的實際佔比會比本次量到的
  0.5~0.6% 更大,「不明顯」的結論就可能不成立,需要拿到真實遊戲畫面的縮放比例才能完全確認。
- **`nearest` 是 1b 盲選的結果,不是唯一可能落地的方法**:若 `psd_inplace_patch.py --auto`
  在其他情境選到 `cv2_telea`/`cv2_ns`,結論是否一致未驗證(候選7的靜態代理裡三者在
  `身體`/`左手` 上表現相近,但未在真實渲染尺度下逐一截圖驗證)。
- 兩個時間點的人眼複查仍是**本次執行者(Claude)的 vision 自評**,不是真人使用者標註——
  跟候選7同樣的誠實限制(RULES.md:「驗證真相來源」對客觀項用 vision 自評是允許的,但主觀
  手感類判斷的最終確認權仍在使用者)。

## 第二個案例:機器人拆件/身體(chunk 24,2026-09-01)——驗證 rotate=true 路徑

`身體` 是 Award atlas 裡另一個已知 1a fail(機械紋理)/1b pass 的材質,選它是因為 atlas
region `rotate=true`(`左手` 是 `rotate=false`)——`atlas_patch.py` 雖然自測過旋轉還原
(`--selftest`),但先前 chunk 23 的端到端渲染驗證只走過 `rotate=false` 這條路,旋轉還原
在真實渲染管線(切→挖洞→補→貼回旋轉頁→spine-webgl 渲染)裡是否也正確,之前沒驗過。

跑法與 chunk 23 相同:`--slot "機器人拆件/身體" --att-name "機器人拆件/身體"`(其餘用預設,
`Award_Legend_In`/`Award_Legend_Loop` 共 11 個時間點,`frac=0.12` interior 洞)。

**結果**:

- **1b 盲選**:`nearest` 勝出(`pass_1b`,`alpha_gap=0.0, seam_ratio=0.63, tone_gap=0.372`
  三項皆 pass,`hole_frac_of_content=0.119`),與 `左手` 同型。
- **旋轉還原路徑驗證通過**:對全部 11 個時間點的全場景截圖(900×900)逐像素比對
  orig vs patched,差異像素(閾值>2)全部落在該 slot 的螢幕框內(如 `Award_Legend_Loop t=0`
  的 414 個差異像素,框座標 x∈[412,481] y∈[382,477] 全部落在框內),0 像素外洩到其他
  slot/頁——`atlas_patch.py` 的旋轉還原在真實 spine-webgl 渲染管線下正確,不只是
  `--selftest` 的靜態自測。
- **實際螢幕佔比**:目標 slot 在這個相機框架下約佔全場景 79×107px(≈1.0~1.1% 畫布面積),
  比 `左手` 的 0.5~0.6% 大約兩倍(材質本身在 atlas 裡尺寸更大)。
- **人眼複查(6x 放大,兩個時間點 `Award_Legend_In t=0.6`、`Award_Legend_Loop t=0.6`)**:
  同一種瑕疵模式——材質右側肩甲/面板一道鋸齒狀機械分件線在補丁處被抹平成一塊圓潤的
  高光色塊,細節比周圍原有的尖銳分件輪廓更「奶油糊」,呼應候選7/chunk23 已知的高頻細節
  丟失。**但在實際渲染尺寸(裁切未放大版,79×107px)人眼複查,兩張圖看起來幾乎一致**,
  瑕疵在這個尺寸下不構成一眼可見的穿幫——與 `左手` 的結論同型,即使該材質實際佔比是
  `左手` 的近兩倍,結論依然成立。
- console 有 1 個 `404 Failed to load resource`,與渲染結果無關(常見瀏覽器背景請求,如
  favicon),不影響任何截圖/量化結果。

**結論**:候選16路徑(b)對第二個材質(`身體`,rotate=true)複驗成功——(1) `atlas_patch.py`
的旋轉還原在真實 spine-webgl 渲染管線下正確(不只是靜態自測);(2)「CPU baseline 補丁有已知
高頻細節丟失瑕疵、但在真實動畫渲染尺度下不構成一眼可見穿幫」這個結論可攜到第二個材質,即使
該材質實際螢幕佔比是 `左手` 的近兩倍。未改動任何既有 production 代碼(`s4_award_screenshot_compare.py`
本身已經是通用的,只是換了 `--slot`/`--att-name` 參數重跑)。

## 下一步(候選16,若要再推進)

- ✅ ~~擴大到 `身體`(rotate=true,驗證 atlas_patch 的旋轉還原路徑在真實渲染管線下也正確)~~
  chunk 24 已完成,見上方。
- 擴大到 `光暈`(平滑材質,理論上 CPU 補圖在 1a 都能過,預期這裡的差異會更小)。
- 若能取得真實遊戲對這個特效的實際顯示縮放比例(UI 設計稿或遊戲截圖),重算相機框架驗證
  「佔比小所以不明顯」這個結論在正式畫面尺度下是否依然成立——`身體` 的 1.0~1.1% 佔比已經
  比 `左手` 大,若真實遊戲把特效再放大,結論可能在某個佔比門檻後翻盤,目前兩個案例都還沒
  找到那個門檻。
- 目前的相機聯集只用了 11 個離散時間取樣點,若動畫在取樣點之間有更劇烈的甩動,聯集框可能
  不夠寬——可以考慮用更密集的取樣或直接對整段動畫做逐 frame 掃描來算聯集(成本更高)。

## 重現

```
python3 tools/mesh_gen/atlas_patch.py --selftest assets/Award.atlas assets/ <scratch>/atlas_selftest \
    "機器人拆件/左手" "機器人拆件/身體" "機器人拆件/光暈" "機器人拆件/右手" "機器人拆件/頭"

python3 tools/mesh_gen/s4_award_screenshot_compare.py -o <scratch>/out
# 產出 <scratch>/out/compare_report.json(含 1b 分數、每個時間點的 MAE/螢幕框)、
# orig__*.png/patched__*.png(全場景)、crop_*/crop6x_*(裁切/放大版供人眼複查)。
```

vendor `spine-webgl.js`(3.8 官方 build)透過 `raw.githubusercontent.com` 下載到本機快取
(`/tmp/s4_spine_vendor/`),`cdn.jsdelivr.net`/`esotericsoftware.com` 在本容器網路政策下被擋
(403,同候選4/17 已知的網路政策模式)——不影響結論,只是取得 runtime 的來源不同於
`spine_inspector.html` 內建的 CDN 清單。截圖/裁切圖屬一次性驗收證據,不納入版控,需要重看時
用上面指令重現。
