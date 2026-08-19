# S1 端到端 — 目標圖(分層 PSD)→ 可載入 Spine 素材(SkelToJson)

- **結論**:把前面各能力串成一條 pipeline:`analyze_target`(規格)+ `psd_slice`(切件)+
  `generate_mesh_v2`(mesh 拓樸)→ 打包 atlas + 組 **Spine 3.8 skeleton JSON**。
  對 `robot_parts.psd`(5 件)與 `Symbol_Ww.psd`(18 件)皆產出可載入素材,**round-trip 驗證全 PASS**。
- **信心**:高(round-trip 重建 setup pose == 原 PSD composite,premult MAE 0.03/0.24、0 孤兒、0 未解析 attachment)。
- **階段**:第 2 階段 / S1 → S3+S4 整合(STATE 候選 0a,最高優先項)。
- **工具**:`tools/analyzer/build_spine.py`(產出)、`validate_build.py`(round-trip 閘)。

## 標準指令
```
python3 tools/analyzer/build_spine.py assets/robot_parts.psd            # → specs/robot_parts_spine/
python3 tools/analyzer/validate_build.py assets/robot_parts.psd specs/robot_parts_spine   # PASS → exit 0
```
產出:`skeleton.json` + `skeleton.atlas` + `skeleton.png`(標準 Spine 三件組,可直接載入)。

## 產出結構(Spine 3.8)
- **bones**:`root` + 每件一根 `b_<件名>`(置於件影像中心,y 上翻),parent=root。
- **slots**:每件一個,依 z 升序(由下而上繪製),bound 到自己的 bone。
- **skin default**:mesh 件用 `generate_mesh_v2` 拓樸(vertices/uvs/triangles/hull);region 件用矩形 region。
- **animations**:先留空(setup pose 可載入);分鏡 keyframe 由 #3 規格描述,自動生成屬後續。
- **atlas**:shelf 打包各切件(rotate 全 false),寫 libgdx `.atlas`;mesh uvs 為 region-local(見 s1 分析器發現)。

## Round-trip 驗證(`validate_build.py`)
由**生成的 json+atlas+png** 重建 setup pose(讀 bone 座標 + atlas 取貼圖 + z 序疊合),比對原 PSD composite:

| 標的 | 件數 | bones/slots | 未解析 attach | premult MAE | 孤兒 | 判定 |
|---|--:|---|---|--:|--:|---|
| robot_parts | 5 | 6/5 | 0 | 0.031 | 0.0 | PASS |
| Symbol_Ww | 18 | 19/18 | 0 | 0.236 | 0.0 | PASS |

視覺:`knowledge/figures/s1_build_roundtrip.png`(原圖 vs 由 spine 素材重建,像素級一致)。
mesh/region 分派沿用分析器建議(robot:光暈/身體=mesh,右手/頭/左手=region)。

## 座標約定(builder/validator 必須一致)
影像左上原點 y 向下;Spine root 置畫布左下 y 向上。件中心 (cx,cy) → bone(x=cx, y=H−cy)。
`generate_mesh_v2` 已把頂點置中 + y 上翻,直接吻合 bone 局部座標。

## 誠實界定
- Round-trip 只驗**靜態幾何/貼圖編碼**(素材可用、位置對、atlas 對得上)。**mesh 的變形能力、
  骨骼權重、動畫 keyframe 不在此驗**(mesh 與 region 靜態擺放相同)。
- pivot 目前取件中心;真正的關節 pivot(手肘/肩)需 S5 骨架階段人微調(計畫早已指出 pivot 是唯一卡死處)。
- 動畫尚未生成:setup pose 可載入,但「會動」要接分鏡 keyframe 生成(下一步)。

## 下一步候選
1. **分鏡 → 動畫 keyframe**:把 #3 storyboard(In/Loop/Out 等)轉成 Spine `animations`
   (bone 的 rotate/translate/scale timeline),先做 Loop 呼吸這種可程序生成的。
2. **關節骨架**:件中心 pivot → 依相鄰件關係推關節(hand↔body),供 S5 微調。
3. **平圖輸入串接**:`segment_flat` 的候選(不相連塊)接同一 build_spine 介面(品質受限,見 s1-flat 文件)。
