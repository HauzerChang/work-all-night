# S3 端到端驗收 — PSD 件 → 生成 mesh → 對照 Award 真實 mesh(ground truth)

- **結論**:把「PSD→切件→S3 `generate_mesh_v2`」串成端到端,對 Award 生產 spine 的 **3 個真實 mesh 件
  (光暈/身體/左手)** 逐件量化對照。生成 mesh 的**覆蓋保真度與藝術家生產 mesh 相當(±1.6% 以內,身體甚至更高)**,
  且只用 **45–74% 的頂點數**。⇒ S3+S4 端到端對真實生產標的驗收通過(里程碑)。
- **信心**:高(對真實 spine ground truth 交叉比對 + 評估器先以藝術家真值自一致確認可信 + Y 向重建無歧義)。
- **階段**:第 2 階段 / S3×S4 串接。

## 量化結果(件-局部像素空間,覆蓋 IoU)

| 件 | 藝術家 verts/tris/hull | 藝術家 cover-IoU vs alpha | 生成 verts/tris | 生成 cover-IoU | 互相 IoU | 頂點比 |
|---|---|---|---|---|---|---|
| 光暈 706×683 | 78 / 76 / 78 | **0.949** | 35 / 49 | 0.933 | 0.918 | 0.45 |
| 身體 379×425 | 98 / 154 / 40 | **0.948** | 60 / 97 | **0.966** ↑ | 0.928 | 0.61 |
| 左手 257×215 | 80 / 116 / 42 | **0.977** | 59 / 97 | 0.964 | 0.957 | 0.74 |

- 生成器對 3 件全用 **delaunay-v1（散點）模式**(`_mode=delaunay-v1`),非 strip:
  這些件長寬比 0.84–1.12(< 1.2 strip 門檻)且非直條 row-convex → v2 auto **正確回退 v1**。
- **v1 對這類「塊狀角色件」覆蓋達藝術家水準**;strip 只適用窗簾類高瘦直條件。

## 評估器可信度(先驗證再下判定)

- 藝術家 mesh 對 alpha 的覆蓋 IoU = 0.949/0.948/0.977(高,符合生產真值預期)→ 重建與量測可信,當基準線。
- **Y 向無歧義**:UV→像素用 `py = uv_y·H`(flip=False)得 0.95;翻轉(flip=True)僅 0.43–0.60 →
  flip=False 決定性勝出,證明 Award mesh uvs 為 region-local、origin 左上,直接乘件尺寸即得像素座標。

## 關鍵發現 / 教訓

1. **端到端閉環成立**:PSD 切件(S4)的 alpha ⇄ 生成 mesh(S3)⇄ 藝術家生產 mesh 三者覆蓋一致。
2. **v1 vs v2 分工釐清**:blobby 角色件(無逐頂點 deform、靠骨骼權重變形)用 v1 散點即可達生產水準;
   v2-strip 是為「大單向拉伸 + 逐頂點 deform」的窗簾類件而設。auto 模式門檻(aspect≥1.2 且 row-convex)分流正確。
3. **⚠️ 覆蓋 IoU ≠ 全部**:藝術家用較多頂點,部分是為 **weighted 骨骼變形的控制密度**(這 3 件在 Award 為 weighted mesh,
   hull<verts 有內部點),不只為靜態覆蓋。本次只驗「靜態覆蓋économy」;**權重/骨骼變形品質未驗**(這 5 件在 Award
   無 deform timeline,故無真實位移場可轉移比對 → deform 閘不適用)。要驗 weighted 變形需另建骨骼綁定閘。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_pieces
# 需件 PNG 路徑對齊 compare_award_mesh.py 內 PIECES(預設 /tmp/robot_pieces/{00_光暈,03_身體,04_左手}.png)
python3 tools/mesh_gen/compare_award_mesh.py
```

## 下一步

- 固化「件→Spine JSON」組裝(SkelToJson):`PSD名/圖層名` 命名 + size+2px padding + mesh/region 分配
  + 生成 mesh 塞入 attachment,端到端產可載入 Spine JSON。
- (較後)weighted mesh 骨骼綁定閘:BBW 權重生成 + 對照 Award weighted 變形(需重現 Spine 骨骼 skinning)。
