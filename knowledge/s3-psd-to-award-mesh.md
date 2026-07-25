# S3 端到端:真實 PSD 件 → 生成 mesh → 對照 Award 藝術家 mesh

- **結論**:`robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)經 `psd_slice` 切件 → `generate_mesh_v2(auto)`
  產出的 mesh,**靜態覆蓋率(IoU)全部落在 Award 真實藝術家 mesh 的 ±0.03 內,且頂點數少 40~55%**。
  這是「PSD→件→mesh」pipeline **首次對真實生產標的(有藝術家真值)整合驗收通過**。
- **依據**:`tools/mesh_gen/compare_to_award.py`,`overall_pass=true`(2026-07-25)。
- **信心**:高(靜態覆蓋率);deform 對照見下「真值缺口」。
- **相關階段**:第 2 階段 S3(mesh 生成器)× S4(PSD 切圖)串接。

## 量化結果

| 件 | 藝術家 IoU / 頂點 | 生成 v2 IoU / 頂點 / mode | 差 | pass |
|---|---|---|---|---|
| 光暈 (706×683) | 0.949 / 78 | 0.930 / 35 / delaunay-v1 | −0.019 | ✅ |
| 身體 (379×425) | 0.949 / 98 | 0.961 / 60 / delaunay-v1 | +0.012 | ✅ |
| 左手 (257×215) | 0.981 / 80 | 0.956 / 59 / delaunay-v1 | −0.025 | ✅ |

## 關鍵發現

1. **v2 auto 對 3 個 blobby 件全部正確回退 v1 Delaunay**(長寬比 <1.2、非 row-convex)。
   先前 v1/v2 只在窗簾/陰影(高瘦 strip)上驗過;**這是 auto-routing 對真實非-strip 生產件的首次驗證**
   —— strip 判準(aspect≥1.2 且 row-convex)在真實 blob 上如預期不觸發,回退路徑可用。
2. **少頂點、同覆蓋**:生成 mesh 用 35~60 頂點即達藝術家 78~98 頂點的覆蓋率;藝術家 mesh 密度多來自
   要餵骨權重的內部細分,不是覆蓋率需求。

## 座標校驗(可重用,修正 sess006 note)

- **Award mesh `uvs` = region-local 0..1、v top-down**(非 atlas-page 正規化)。
  校驗法:把 uvs 當 region-local 直接鋪到件 alpha,`v top-down` IoU 0.95~0.98 遠高於 `v-flip` 0.43~0.60
  → 確認朝向。當成 atlas-page 正規化(`u*PW,v*PH` 再減 region 原點)時,uv 落在 region 框內比例≈0 → 排除。
- **修正**:sess006 open note 寫「Award mesh uvs 為 atlas UV,需先轉 region 局部」為**誤判**;
  實測本就是 region-local(與 `validate_against_real.artist_iou` 對 main_draw 的處理一致)。
- `generate_mesh_v2` 產出的 uvs 同為 region-local 0..1、v top-down → 兩者可直接同框比 IoU。

## ⚠️ deform 真值缺口(誠實記錄,下一步的關鍵岔路)

- Award 機器人 3 件皆 **weighted mesh(骨骼驅動)且無 deform timeline**(12 支動畫查無 robot slot 的 deform)。
  變形靠 **bone weights** 攤平的 `[骨數, boneIdx,bindX,bindY,weight,...]`,不是 `deform` 頂點位移。
- 本生成器目前產 **unweighted** mesh。故 `validate_against_real` 的「真實位移場轉移」閘(需 deform timeline)
  **對這 3 件不適用** → 本次只能做**靜態覆蓋率**對照,無法對等比 deform 穩健度。
- 要補上變形對照,須先做 **BBW 自動骨權重(S3 roadmap 未完項)**,把生成 mesh 綁到 Award 對應骨,
  再用同一組骨的 pose 差分做位移對照。這是下一個有價值的 bounded chunk。

## 工具

- `tools/mesh_gen/compare_to_award.py`:`--psd assets/robot_parts.psd --award assets/Award.json`
  → 切件 + 生成 + 靜態覆蓋率並列;`overall_pass` gate(margin 預設 0.03)。
