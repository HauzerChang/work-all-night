# S4 下游:切件 → 完整可載入 Spine 資產(SkelToJson + AtlasPack)

- **結論**:把 S4 切件接到「組裝」,端到端產出**完整 Spine 3.8 資產**(skeleton JSON + .atlas + PNG),
  其 setup pose == PSD 平面 composite 佈局。對 `robot_parts.psd`(機器人 5 件)全自動產出並多重自驗通過。
- **信心**:高(位置解析式 round-trip 0px + 光柵重建 MAE 0.031 且視覺正確 + atlas 用真實 Spine atlas
  讀取程式碼裁回 MAE 0 + JSON↔atlas 一致)。⚠️ **未**在真正的 Spine runtime 載入(CDN 被擋、無 headless
  spine loader)—— 驗證止於結構/幾何/光柵層級,見下方「誠實邊界」。
- **階段**:第 2 階段 / S4 下游組裝(里程碑:PSD→件→**完整資產**閉環)。
- **工具**:`tools/mesh_gen/skel_to_json.py`、`tools/mesh_gen/pack_atlas.py`。

## SkelToJson(`skel_to_json.py`)— 切件 → Spine JSON

固化 `s4-psd-to-spine-real.md` 揭示的真實慣例:
- slot 命名 `<namespace>/<圖層名>`(Award namespace = 「機器人拆件」);一圖層⇄一 slot⇄一 attachment。
- mesh/region 由 spec 指定(`--mesh-parts`);mesh 用 `generate_mesh_v2` 生成、region 用矩形。
- **座標**:Spine y-up、原點在 PSD 畫布中心。件中心 px `(l+w/2, t+h/2)` → world `(cx-W/2, H/2-cy)`,
  bone 放此處、**rotation=0**(還原平面佈局)。unweighted mesh 頂點已以件影像中心置中 → 落回原位。

**四條 AC 全過**(robot 5 件):

| AC | 方法 | 結果 |
|---|---|---|
| 位置 round-trip | 解析式重建每 attachment **影像框**(bone±w/2,h/2)→ 轉回 PSD px 比 offset/size | worst 中心 **0.0px** / 尺寸 **0.0px** |
| 結構有效 | 每 slot 有合法 bone、skin 有對應 attachment、JSON 可序列化 | ✅ 6 bones / 5 slots |
| mesh 格式 | 每 mesh 過 evaluate_mesh 格式/孤兒/退化 | ✅ 3 mesh |
| 光柵重建 | 由 **skeleton 位置**(非 manifest)重合成各件 → 對 PSD composite premult-MAE | **0.031**(視覺完美還原機器人) |

★ 關鍵設計:位置 AC 量的是**影像框**(件的來源影像被放回哪),**不是 mesh 頂點外接框**——後者是
alpha 輪廓形狀,本就 ≤ 矩形框(初版誤用它 → 身體「誤差 47px」假性失敗)。mesh 與 region 皆以
width/height 為影像框、置中於 bone,故兩者位置檢查一致且皆 0px。

## AtlasPack(`pack_atlas.py`)— 切件 → .atlas + sheet

- 簡單 shelf(架式)打包:高度遞減擺列、超寬換行、件間 padding;**rotate:false**(最單純,
  region size = 件原始尺寸 → 正規化 uv 直接對應)。輸出格式與真實 Spine atlas 逐欄一致
  (xy/size/orig/offset:0,0/index:-1)。region 名 = skel_to_json 的 attachment 名。
- **驗收**:用**同一支** `atlas_crop.extract`(平時讀真實 Spine/Award atlas 的程式碼)從產出的
  atlas+png 裁回每 region → 對源切件比對 → **worst MAE = 0.0**(打包無損、可被標準工具讀回)。

## 完整資產整合
- `robot.json` + `robot.atlas` + `robot.png` 三件齊。**JSON↔atlas 一致性**:5 個 attachment 全在 atlas
  找到對應 region,且 attachment width/height == atlas region size(全 match)。
- ⇒ 端到端 `PSD → 切件(S4)→ mesh(S3)+ 組裝 + 打包 → 完整 Spine 3.8 資產`,setup pose 還原原圖。

## ⚠️ 誠實邊界(未做/限制)
1. **未在 Spine runtime 實載**:CDN(jsDelivr)被網路政策擋、無 headless spine loader。驗證止於
   結構有效 + 幾何 round-trip(0px)+ 光柵重建(MAE 0.031,視覺正確)+ atlas 可被真實-atlas 讀取碼讀回(MAE 0)。
   這是強驗證但非「Spine 引擎載入通過」。取得離線 spine-webgl 或 headless 瀏覽器後可補實載驗。
2. **setup pose = 平面佈局(rotation 0)**:Award 生產檔的 region 有非零 rotation / 骨階層 / 擺姿——
   那是**綁定/擺姿(S5)**決策,不在本工具。本資產是「平面 setup」正確起點,綁定前的中繼態。
3. **mesh 邊緣覆蓋**:光柵重建用**整件矩形**貼圖驗**位置**(與 mesh 覆蓋率解耦)。若真以 mesh 渲染,
   邊緣覆蓋 = S3 已量的 IoU(~0.96);差額在 mesh 輪廓外的透明羽化邊,見 `s3-psd-to-award.md`。

## 可重現
```
python3 tools/mesh_gen/skel_to_json.py --out /tmp/robot_asset/robot.json \
        --render /tmp/robot_setup_recon.png --eval          # 4 AC 全過,exit 0
python3 tools/mesh_gen/pack_atlas.py --out-atlas /tmp/robot_asset/robot.atlas \
        --out-png /tmp/robot_asset/robot.png --eval          # 無損 MAE 0,exit 0
```

## 下一步候選
- **實載驗**:取得離線 spine-webgl / headless 瀏覽器 → 把完整資產載入,確認 runtime 接受(補上誠實邊界①)。
- **S5 骨架/綁定**:平面 setup → 加骨階層、pivot、posed rotation(唯一卡死環節,人力集中處)。
- **weighted mesh + BBW**:mesh 目前 unweighted;要對 Award 這類 weighted 件驗變形需 BBW 權重(依賴骨架)。
