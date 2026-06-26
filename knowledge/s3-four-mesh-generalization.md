# S3 推廣到全部 4 個 mesh — v1 不通用、v2 strip 通用

- **結論**：把整合 AC(`validate_against_real.py`)推廣到 4 個真實 mesh 後,
  **v1(散點 Delaunay)不通用**:靜態 IoU 高(~0.98)但在真實 deform 下會自交;
  **v2(strip,藝術家式直條拓樸)通用**:4 個 mesh 全數 deform 乾淨,調 rows 後 IoU 也全過。
- **依據**:對 `curtain_left / curtain_right / shadow / shadow2` 跑整合 AC(真實 alpha IoU
  + 真實位移場轉移 deform 閘),數據如下表。
- **信心**:高(評估器先以藝術家真值自一致性驗證,4 mesh 全 si=0/flip=0 → 閘可信且具鑑別力)。
- **階段**:第 2 階段 / S3。

## 評估器可信度先驗(關鍵前置)

延續上一輪教訓「評估器本身要被驗證」。動手判好壞前,先把**藝術家自己的 mesh** 餵進
`transfer_deform_check`,4 個全部 si=0 / flip=0 / 乾淨(area 1.13/1.14/0.99/0.98)。
→ 閘忠實重現真實變形姿勢,故對「生成 mesh」的失敗判定可信。
另確認 UV 座標系一致:藝術家 uvs 與生成 uvs 皆為 region 內 0..1,griddata 線性覆蓋
40/41、39/39(僅 1 點落 nearest)→ 轉移非座標系錯位假象。

## v1 vs v2 整合 AC 結果

| mesh | v1 IoU | v1 deform | v2 IoU(rows=10) | v2 deform |
|---|---|---|---|---|
| curtain_left  | 0.980 ✅ | 0 si ✅ | 0.934 ✅(base .918) | 0 ✅ |
| curtain_right | 0.979 ✅ | **19 si ✗** | 0.934 ✅(base .914) | 0 ✅ |
| shadow        | 0.904 ✅ | **64 si ✗** | 0.955 ✅(base .473) | 0 ✅ |
| shadow2       | 0.904 ✅ | **64 si ✗** | 0.955 ✅(base .473) | 0 ✅ |

- v1 過 curtain_left 是**部分運氣**:散點拓樸在大單向拉伸下易產生 sliver 三角翻面/自交;
  curtain_right、shadow 同演算法卻壞 → 證實散點拓樸 deform-fragile。
- deform 閘是**硬約束**(會撕裂貼圖,不可用);IoU 是覆蓋率(對齊藝術家)。
  v2 兩者兼顧 → 定為 deform-bearing mesh 的預設生成器。

## 參數調校發現(可重用)

- **IoU 由 `rows`(邊界取樣密度)決定;`cols` 只加內部頂點,不影響覆蓋率。**
  - 窗簾 rows=8 → IoU 0.911(略低於藝術家基準);rows=10 → 0.934;rows=12 → 0.948…
- **rows=10, cols=3(30 頂點)對 4 個 mesh 全過 IoU 基準 + deform 乾淨** → 已設為 v2 預設。
  接近藝術家精簡度(窗簾 21、陰影 12),换取 deform 穩健裕度,值得。

## 可重現指令

```
for s in "image/curtain_left:image/curtain_left" "image/curtain_right:image/curtain_right" \
         "image/shadow:image/shadow" "image/shadow2:image/shadow"; do
  python3 tools/mesh_gen/validate_against_real.py --slot "${s%%:*}" --name "${s##*:}" --gen v2
done   # 4 個 overall_pass=True
```
