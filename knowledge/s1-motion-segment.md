# S1 塊2 — 運動分群成件(affine 運動模型 EM)

- **結論**:把動態前景依運動分成候選可動件。**樸素 flow-kmeans 不行(把旋轉件拆碎,合成 GT 召回僅
  0.5~0.75、頭 IoU~0.05)**;改用**經典多剛體 affine 運動模型 EM**(每群一組 per-frame affine,依殘差
  指派像素)→ 合成 GT **召回 1.0**(頭 0.999、雙手 0.6~1.0)。方法用**剛綁的 rig 產生已知件合成光流**
  當真值閉環驗證(純 CPU);再套真實舞蹈影片產候選件。
- **信心**:方法高(合成精確真值召回 1.0);真實影片產出為候選(非剛體+複雜舞動,較noisy,誠實標註)。
- **階段**:S1(塊2)。

## 為何 affine-EM 而非 kmeans(關鍵發現)

- 剛體件小角旋轉/平移的每幀光流在像素座標上是 **affine**:`flow=[a·x+b·y+c, d·x+e·y+f]`。
- 樸素 flow-kmeans 用「每像素 flow 值」聚類 → 同一旋轉件的遠端像素 flow 差異大被拆開、
  不同件近 pivot 處 flow 都小被併在一起 → **系統性拆碎**(實測召回 0.5~0.75、頭幾乎抓不到)。
- **affine-EM**:E 步依「該像素 flow 對每群 affine 模型的殘差」指派,M 步對每群 per-frame 最小平方
  重擬 affine → 同件像素被同一 affine 解釋 → 正確聚合。多 seed 取**總殘差最小**(非監督,不看真值)。

## 評估器(每能力必配)— 合成 GT 召回

- 用 `assets/robot_parts_rigged.json` 的件 + pivot,令各件繞自身 pivot 獨立擺動(手臂±16°/頭±9°/
  身體±5°),生成剛體合成光流 + 已知件標籤 → 跑分群器 → 貪婪 IoU 指派算召回。
- **結果:recall 1.0(iou≥0.4)**;頭 0.999、左手 1.0、右手 0.613、身體 0.556、光暈 0.444。
- 這是 S1 首個有精確真值的評估器(舞蹈影片機器人 ≠ robot_parts,不能逐件比,故用合成 GT 驗方法)。

## 真實影片(候選件產出)

- `assets/robot_dance.mp4` → 光流(scale 0.35)→ affine-EM(k=5)→ 候選 motion-coherent 區塊
  (視覺化 `knowledge/figures/s1_segments.png`:粗分出頭頂/左右臂/軀幹-腿等)。
- **誠實限制**:真實舞動含非剛體、透視、整體 sway → 分割較 noisy;k 需人給或加模型選擇;
  精化方向:temporal 平滑、per-frame 模型數自選、以 alpha 前景限定。

## 可重現

```
python3 tools/s1/motion_segment.py           # 合成召回 1.0 + 真實影片候選, exit 0
```

## 下一步(S1 塊3)

把「動態前景定位(塊1)+ 運動分群(塊2)+ 各件運動型態(擺盪軸/振幅/相位)」組成
**Asset & Rig Requirement Spec**(件清單 + 各件運動需求)→ 對接 rig_draft/bind_weights 的骨架,
用運動型態驅動骨骼 → 逼近目標影片。
