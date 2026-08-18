# S3 端到端驗收 — PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,對**有藝術家真值 mesh 可比**的真實
  生產標的驗收通過。`robot_parts.psd` 的 光暈/身體/左手 三件(在 Award 為 mesh)經 `psd_slice`
  切件 → `generate_mesh_v2`(auto)生成 → 覆蓋 IoU **全部落在藝術家 baseline − 0.02 以內**,
  格式/自洽閘全過。工具:`tools/mesh_gen/compare_to_award.py`(可重現)。
- **信心**:高(對真實生產 mesh 交叉比對 + 負對照確認鑑別力)。
- **階段**:第 2 階段 / S3×S4 整合(里程碑:端到端「PSD→件→mesh」對真實標的)。

## ★ 關鍵更正:Award mesh 的 uvs 是 **region-local**(0..1 over region),不是 atlas UV

先前 log/STATE 記「Award mesh uvs 為 atlas UV,需先轉 region 局部」。**實測推翻**:
用 region-local 假設(`uv * 切件寬高`)還原 Award mesh 多邊形,對切件 alpha 覆蓋 IoU 達
0.948/0.948/0.977,座標完全吻合切件像素空間。若是 atlas UV(頁 2040px、region ~700px),
UV 只會佔頁面約 0.35,不可能出現 0.01–0.99 的近滿 range。
→ **這是標準 Spine JSON 格式**:mesh 的 `uvs` 存 region-local [0,1],runtime 再用 region 的
atlas UV rect 重映到圖集空間。以後讀/寫 Award mesh、做「件→Spine JSON」組裝時直接當 region-local。

## 量化結果(margin=0.02)

| 件 | 切件 alpha | 生成 mode | 生成 v/hull/tri | 生成 IoU | 藝術家 v/hull/tri | 藝術家 IoU | pass |
|---|---|---|---|---|---|---|---|
| 光暈 | 706×683 | delaunay-v1 | 35/16/49 | 0.933 | 78/78/76 | 0.949 | ✅ |
| 身體 | 379×425 | delaunay-v1 | 60/20/97 | 0.966 | 98/40/154 | 0.948 | ✅ |
| 左手 | 257×215 | delaunay-v1 | 59/19/97 | 0.964 | 80/42/116 | 0.977 | ✅ |

## 觀察

1. **三件都近方形**(aspect H/W = 0.97 / 1.12 / 0.84 < 1.2)→ `generate_mesh_v2` auto 模式
   **自動回退 v1 Delaunay**(strip 僅適用高瘦 row-convex 件,如窗簾)。此驗收因此是「v1 對真實
   剛體/weighted 件」的覆蓋能力驗證。
2. **生成 mesh 更精簡卻覆蓋相當**:頂點數約為藝術家的 45–75%(35 vs 78 等),IoU 仍在 baseline
   ±0.02。身體/左手甚至略高於藝術家(藝術家 mesh 在凹處留白換取變形自由度)。
3. **deform 閘不適用**:這三件在 Award **無 deform timeline**,靠 weighted bone 變形而非逐頂點
   deform,故不套 `transfer_deform_check`;此處只驗靜態覆蓋 + 拓樸格式(誠實標註,避免用
   未校準的合成壓力製造假結論)。**生成的是 unweighted mesh;若要進 Award 需另配權重(S5/BBW,待建)。**

## 評估器可信度(負對照)

`身體` 生成 mesh 向重心收縮 0.7 → IoU 由 0.966 掉到 **0.483**(遠低於 baseline−margin),
覆蓋閘可鑑別壞 mesh。評估器已校準。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --out /tmp/robot_parts
python3 tools/mesh_gen/compare_to_award.py            # 3 件全 overall_pass, EXIT 0
```

## 下一步

- **件→Spine JSON 組裝(SkelToJson)**:把 `PSD名/圖層名` 命名、region-local uvs、size+2px、
  mesh/region 分配固化成工具,端到端產出可載入 Spine 的 JSON。生成 mesh 目前 unweighted →
  無 deform 件可直接用;有 deform/骨骼變形的件需接權重(S5)。
- 光暈生成 IoU(0.933)是三件最低(圓形發光邊界羽化)→ 若要逼近藝術家,可試對低 aspect
  但需更貼邊界的件加「輪廓取樣密度」旋鈕(目前 v1 hull 16 點)。
