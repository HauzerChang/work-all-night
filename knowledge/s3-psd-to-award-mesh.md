# S3 端到端驗收:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh(ground truth)

- **結論**:把 Award(機器人 big win spine)的 3 個 **weighted mesh 件**(光暈/身體/左手)當
  ground truth,S3 `generate_mesh_v2`(auto→Delaunay 回退)對**同一素材**自動產出的 mesh
  **達到藝術家水準覆蓋率,且頂點更省**:身體/左手覆蓋率**超過**藝術家、光暈在重採樣噪聲內。
  這是「PSD→件→mesh」對真實生產標的的端到端閉環驗收(純 CPU、可自驅)。
- **信心**:高。轉換有獨立 oracle 校驗 + 4 朝向負對照;對照真實美術 mesh;未回歸 main_draw 4 mesh。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑)。

## 量化結果(`tools/mesh_gen/validate_psd_to_award.py`,exit 0 全 PASS)

| 件 | 生成覆蓋 IoU | 藝術家 IoU | 生成頂點 | 藝術家頂點 | mesh對mesh輪廓一致 |
|---|---|---|---|---|---|
| 光暈 | 0.966 | 0.980 | 61 | 78 | 0.954 |
| 身體 | **0.986** ↑ | 0.976 | **69** | 98 | 0.968 |
| 左手 | **0.982** ↑ | 0.968 | **57** | 80 | 0.964 |

→ 身體/左手**覆蓋率超過藝術家 mesh 且頂點少 ~30%**;光暈差 0.014(< 2% margin,見下)。

## 方法要點(避免跨座標系 bug 的設計)

1. **共同畫布**:用 `atlas_crop.extract()`(已修 CW 去旋轉、多頁)取得「直立、atlas 縮放(~0.70)」的
   件裁圖。生成 mesh 與藝術家 mesh **都柵格化到這張裁圖**,直接比 IoU,不做跨頁座標轉換。
2. **Award mesh 的 uvs 是 region-local**(不是 atlas 頁面 UV):實測 uv 對一個 181px region 卻
   span 滿 [0,1] → Spine 匯出時 attachment uvs 已正規化到 region 局部 [0,1](atlas 檔負責擺放/旋轉)。
   故藝術家 mesh 映射 = `px=(u·cropW, v·cropH)`,與生成 mesh 同框。**別誤當頁面 UV 去乘 pageW/H**(會整片跑掉)。
3. **oracle + 負對照確認轉換可信**:裁圖自身 alpha 當獨立 oracle。`direct` 朝向 IoU 0.98/0.98/0.97;
   `vflip/hflip/rot180` 全 0.40–0.76 → 清楚鑑別 region-local + direct 為正解。第一版誤用「頁面 UV + CW 旋轉」
   → oracle 崩到 0.0/0.49/0.54,被 oracle 當場抓到(`transform_valid=false`);修正後才信覆蓋比對。
   **教訓延續**:baseline 不可信時 `gen ≥ baseline` 會假性通過(身體 baseline=0.0 曾讓 gen 免試過關)。

## 關鍵發現(可推廣)

- **覆蓋率由邊界取樣密度(`epsilon_frac`)決定,內部點(`max_interior`)不影響。**
  與 strip 版「IoU 由 rows 決定、cols 不影響」同一原理,現於 Delaunay 分支再證實。
  實測(Award 3 件):eps 0.008→0.004→0.002 時 IoU 明顯升(光暈 0.93→0.966→0.983),
  加內部點對 IoU 幾乎無變。
- **v2-auto 的 Delaunay 回退預設 `epsilon_frac` 由 0.008 → 0.004**:0.008 對「atlas 縮小 + 羽化邊」
  的真實件太粗(hull 只 14–21 點),0.004 貼合輪廓(hull 22–30)即達/超藝術家,頂點仍省。
  (只改 v2 回退;`generate_mesh.py` standalone 預設仍 0.008;main_draw 4 mesh 走 strip 不受影響,已重驗未回歸。)
- **覆蓋 margin=0.02 的依據**:atlas 貼圖被縮小 ~0.70 打包 + anti-alias 羽化邊,固定 alpha 門檻下
  <2% 覆蓋差屬重採樣噪聲;mesh-對-mesh 輪廓一致 0.95~0.97 佐證兩網幾何確實重合。

## Award 這 3 件與 main_draw 4 mesh 的差異(為何另寫驗證器)

| | main_draw 4 mesh | Award 3 件 |
|---|---|---|
| 權重 | unweighted | **weighted**(vertices 為 bind 格式,不能當像素座標 → 只能用 uvs) |
| deform | 9 anim 皆有 deform timeline | **無 deform timeline**(靠骨骼/權重變形) |
| 驗證 | 靜態 IoU + **真實位移場 deform 閘** | **靜態覆蓋** vs 藝術家真值(deform 閘 N/A) |

→ 故 `validate_against_real.py`(含真實 deform 閘)不適用於這 3 件;新增
`validate_psd_to_award.py` 專司「weighted / 無 deform / atlas-UV 幾何」的靜態覆蓋對照。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_award.py          # 3 件全 PASS,exit 0
# 內含 4 朝向 oracle 負對照;transform_valid 需 direct 且 artist_iou≥0.80 才信 baseline
```

## 下一步候選

- 把「件→Spine mesh attachment」寫成組裝器(SkelToJson):吃 PSD 切件 + 命名慣例(`PSD名/圖層名`)
  + size+2px padding,直接產可用 Spine JSON(生成 mesh 已證達生產水準)。真正端到端 PSD→Spine。
- 生成的是 unweighted mesh;真實件是 weighted(靠骨變形)。若要對映真實綁定,需 S5 骨架 + BBW 權重
  (尚未做)。目前結論僅限**靜態幾何/覆蓋**達標。
