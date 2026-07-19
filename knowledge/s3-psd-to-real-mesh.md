# S3 端到端:PSD 件 → 生成 mesh → 對照真實生產 spine mesh(里程碑)

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,對**真實生產標的**(Award spine 的機器人 3 個 mesh 件)
  驗收通過。`robot_parts.psd` → `psd_slice` 切出光暈/身體/左手 → `generate_mesh_v2(auto)` →
  **靜態覆蓋率(IoU)全部 ≥ 藝術家真實 mesh baseline − 0.02**,且 0 退化/0 孤兒/形心在遮罩內,
  **並用更少頂點**(35–60 vs 藝術家 78–98)。
- **信心**:高。有真實 ground-truth mesh 交叉比對 + 雙向負對照(跨件、位移)確認閘的鑑別力。
- **階段**:第 2 階段 / S3×S4 端到端(里程碑:從單能力 → 兩能力串接對真實標的)。

## 驗收結果(`validate_psd_mesh.py --gen v2`,exit 0)

| 件 | 生成 v/hull/tri | 生成 IoU | 藝術家 v/hull/tri(weighted) | 藝術家 IoU | gap | pass |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 35 / 16 / 49 | 0.9331 | 78 / 78 / 76 | 0.9486 | −0.0155 | ✅ |
| 機器人拆件/身體 | 60 / 20 / 97 | 0.9660 | 98 / 40 / 154 | 0.9477 | **+0.0183** | ✅ |
| 機器人拆件/左手 | 59 / 19 / 97 | 0.9642 | 80 / 42 / 116 | 0.9768 | −0.0126 | ✅ |

- `mode='auto'` 對這 3 件全選 **delaunay-v1(散點)**,非 strip —— 因為它們是**緊湊團塊**而非細長條
  (窗簾才走 strip)。印證 v2 auto 選模:細長 deform-timeline 件走 strip、緊湊骨驅件走 delaunay。
- 生成 mesh **頂點更省**(35–60 vs 78–98)卻達同等覆蓋;身體件甚至略高於藝術家(散點在凹形邊界貼合更好)。

## 兩個關鍵校正 / 發現(修正先前假設)

### ① Award mesh uvs 是 **region-local [0,1]**,不是 atlas-global(修正 `s4-psd-to-spine-real.md` 的待辦推測)
先前推測「Award mesh uvs 為 atlas UV,需先轉 region 局部」。**量測推翻**:光暈 uv 跨 0.012–0.99;
若為 atlas-global(708px 件 / 2040px 圖集,含 0.70 縮放)只會佔 u≈0.24。故 Spine JSON 的 mesh uvs
存的是**相對來源圖(region)的正規化座標**,runtime 才映射到 atlas。→ 可直接對件 mask 用 `u*W,v*H` 比對,
與 main_draw 同慣例。**無 v 翻轉**(flipv=False 時 artist IoU 0.95/0.95/0.98;翻轉掉到 0.43–0.60)。

### ② 這 3 件是 **weighted(骨驅)mesh、無 deform timeline** → 可信閘 = 靜態覆蓋率,不是 deform 轉移
不同於 main_draw 的 unweighted + 逐頂點 deform-timeline mesh。Award 機器人 mesh 靠骨骼權重變形。
S3 v2 產出的是 **unweighted** mesh,**能匹配靜態拓樸/覆蓋**,但不重現權重綁定(那是 S5 骨架/權重的範疇)。
故此端到端閘只驗「切件→拓樸覆蓋」對真實標的,**deform 閘對這批件 N/A**。
(main_draw 的 deform 閘仍是 unweighted+deform-timeline 情境的正解,見 `s3-four-mesh-generalization.md`。)

## 評估器可信度(負對照,確認鑑別力後才信 pass)

- 正對照(正確配對):0.949 / 0.948 / 0.977。
- 負對照 A(跨件:錯的藝術家 mesh 對錯的 mask):0.48–0.58 → 抓到。
- 負對照 B(生成 uvs 平移 +0.15):0.43–0.60 → 抓到。
- margin 0.02 遠高於雜訊地板(~0.5),閘可信。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --out /tmp/robot_pieces
python3 tools/mesh_gen/validate_psd_mesh.py --gen v2      # 3/3 PASS, exit 0
```

## 下一步候選

- **切件→Spine JSON 組裝(SkelToJson)**:把已固化的真實慣例(`PSD名/圖層名`、size+2px padding、
  region-local uvs、mesh vs region 分配)+ 本次 mesh 生成,寫成端到端「PSD → 可用 Spine JSON」工具,
  用 `evaluate_slicing` / `validate_psd_mesh` 當出廠閘。這會把 S4+S3 從「各自驗證」升成「產出可用資產」。
- 若要驗 weighted 綁定品質,需 S5(骨架/權重)—— 目前 S3 只到 unweighted 拓樸。
