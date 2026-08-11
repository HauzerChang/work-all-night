# S3 端到端驗收 — PSD 件 → 生成 mesh → 對照 Award 真實(藝術家)mesh

- **結論**:用 `robot_parts.psd` 的 3 個 mesh 件(光暈 / 身體 / 左手,在生產 spine `Award` 中為 mesh)
  跑 `generate_mesh_v2`(auto→v1 Delaunay),與 Award **藝術家 mesh 在同一份 PSD 切件 alpha、
  同一種 coverage-IoU 定義**下比較:**3 件全 overall_pass**。生成 mesh 覆蓋保真與藝術家相當
  (±2% 內),且**頂點數約為藝術家的一半**。這是「PSD→件→mesh」對真實生產標的的端到端閉環驗收。
- **信心**:高(對真實生產件 + 藝術家 ground truth 交叉比對;正/負對照皆確認評估器可信)。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:合成/main_draw → 真實生產件端到端)。

## ★ 關鍵座標發現(本次新知,寫進契約)

`Award.json` 的 mesh **`uvs` 是 region-local 正規化**(0..1 覆蓋該件本身),**不是** atlas-page 正規化;
y 與影像同向(top-down,**不需翻轉**)。證據:
- uv 範圍近乎 0..1(光暈 x 0.012..0.990),但件在 page 只占一小塊 → 不可能是 page 正規化。
- 藝術家 mesh 三角以 `(u·partW, v·partH)` 填在 **PSD 切件 alpha** 上:flip=False IoU 0.948~0.977;
  flip=True 全 <0.61 → 方向確認。

**推論(可直接用)**:藝術家 mesh 幾何可**直接**疊回 PSD 切件座標,無需碰 atlas/derotate/page-uv。
→ 「藝術家 mesh」與「生成 mesh」得以在**同一份 alpha** 上用**同一種 IoU** 比較(真 apples-to-apples)。
(注意:這 3 件為 **weighted mesh**,`vertices` 是變長 bind 格式、`len(vertices)!=len(uvs)`;
要拿它的**幾何**請用 `uvs`,不要 reshape `vertices`。)

## ★ deform 閘為何不適用這 3 件

Award 這 3 件**無 deform timeline**、且為 **weighted mesh**(靠骨骼/權重變形,非逐頂點 deform)。
→ `deform_eval.real_deform_field` 沒有真實位移場可轉移 → 本閘**只做靜態覆蓋保真 + 網格有效性**,
不對這些件下 deform 判定。(對照:`main_draw` 4 件為 unweighted + 有 deform,才由
`validate_against_real` 跑真實位移場 deform 閘。)

## 量化結果(`compare_psd_vs_award.py`,budget=64,margin=0.02)

| 件 | 生成 v / 三角 / hull | 藝術家 v / 三角 / hull | 生成 IoU | 藝術家 IoU | Δ | pass |
|---|---|---|---|---|---|---|
| 光暈 | 35 / 49 / 16 | 78 / 76 / 78 | 0.9331 | 0.9486 | −0.016 | ✓ |
| 身體 | 60 / 97 / 20 | 98 / 154 / 40 | 0.9660 | 0.9477 | **+0.018** | ✓ |
| 左手 | 59 / 97 / 19 | 80 / 116 / 42 | 0.9642 | 0.9768 | −0.013 | ✓ |

- 3 件皆 `AC_valid`(格式 OK / 0 退化 / 0 孤兒)、`AC_budget`(≤64,且遠少於藝術家)。
- 光暈的藝術家 mesh **hull=78=全頂點**(純外周扇形三角,無內部格點);我方 v1 用少量內部點即達近似覆蓋。
- **v2 auto 對這 3 件都走 v1 Delaunay**:長寬比 <1.2(光暈 0.97 / 身體 1.12 / 左手 0.84)不觸發 strip
  → 近方形件本來就該用 v1;strip 是為窗簾這種高瘦、單向拉伸件準備的。

## 評估器可信度(先校準再判定,方法論再實踐)

- **正對照**:藝術家 mesh 自身 coverage-IoU 0.948~0.977(真值自一致,高)。
- **負對照**:把生成 mesh 對重心縮 30% → IoU 由 ~0.95 掉到 ~0.48(drop≈0.47),遠低於基準
  → 閘能抓「覆蓋不足」,pass 判定可信(未過鬆)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切件
python3 tools/mesh_gen/compare_psd_vs_award.py                                    # 端到端閘, exit 0 = PASS
```

## 對後續的意義 / 下一步

- **S3+S4 端到端在真實生產件上成立**:PSD 切件 → 生成 mesh 已能達到藝術家等級的覆蓋保真、
  更省頂點。缺的是 **weighted-deform 級**的驗證(這些件靠骨骼權重動,需 bone binding 才能比變形手感)。
- 固化「件→Spine mesh attachment」組裝(SkelToJson):把 region-local uvs=`(x/W, y/H)`、
  y-up 置中 vertices、hull-first 的產出格式,加上 `PSD名/圖層名` slot 命名 + size+2px padding,
  即可端到端吐一份可載入 Spine JSON。(候選下一 chunk)
- weighted 綁定(把生成 mesh 綁到 Award 骨架、比對變形)需要 bone/skin 綁定演算法(BBW),屬 S3 進階。
