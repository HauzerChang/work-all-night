# S3 端到端(PSD→件→mesh)對第二個生產骨架 Award 驗收 — 剛體 blobby mesh

- **結論**:S3 v2 生成器**推廣到第二個真實生產骨架 `Award`(機器人拆件)**成功。
  Award 的 3 個 mesh(光暈/左手/身體)是**加權(bone-driven)、無 deform** 的 blobby 剛體件
  —— 與 main_draw 的 unweighted 直條窗簾/陰影完全不同類型。v2 `auto` 模式**正確選 Delaunay**
  (非 strip),把輪廓簡化 `eps` 由 0.008 收到 **0.002** 後,3 件 IoU 全部**達到或超過藝術家基準,
  且頂點數等於或少於藝術家手做 mesh** → 整合 AC `overall_pass=True`。
- **依據**:對 Award 3 mesh 跑 `validate_against_real.py`(atlas 區塊 = 藝術家 uv 所在座標空間);
  另從 `robot_parts.psd` 端到端切件→生成,自覆蓋 IoU 一致(0.98~0.99)。
- **信心**:高(對藝術家真值逐件比對;PSD 與 atlas 兩個來源交叉一致)。
- **階段**:第 2 階段 / S3+S4 端到端。

## 為何這是新泛化(不是重複 main_draw)

| 面向 | main_draw 4 mesh | Award 3 mesh |
|---|---|---|
| 權重 | unweighted | **weighted(多骨)** |
| 變形來源 | deform timeline(9 anim 全有) | **無 deform,靠骨骼剛體位移** |
| 形狀 | 高瘦直條(窗簾/陰影) | **blobby 團塊**(身體/光暈/手) |
| v2 選模 | strip | **delaunay-v1** |
| 適用閘 | IoU + 真實 deform 轉移 | **IoU only**(deform 閘 N/A) |

→ 首次證明 v2 的 `auto` 選模對「另一類 mesh + 另一份骨架」判斷正確,且 S3 對剛體件也可用。

## 關鍵發現

1. **無 deform 的件,變形閘不適用**:`validate_against_real` 新增 `has_deform()` 偵測;
   無 deform timeline 的 slot 標 `AC_real_deform = N/A (rigid/bone-driven)`,只用 IoU 判定。
   (weighted `vertices` 為變長格式,硬跑 `real_deform_field` 會 shape mismatch 崩 → 先偵測再跳過。)
2. **Delaunay 的 IoU 由 `epsilon_frac`(輪廓簡化容差)決定**。舊預設 0.008 為 main_draw 簡單形狀所調,
   對真實/羽化輪廓**欠取樣**(光暈只剩 14 hull → IoU 0.929 < 藝術家 0.980)。掃描:

   | mesh | 藝術家基準 | eps=.008 | eps=.004 | **eps=.002** | eps=.001 |
   |---|---|---|---|---|---|
   | 光暈(羽化) | 0.9795 | 0.929 ✗ | 0.966 ✗ | **0.983 ✅ (nv73)** | 0.992 (nv92) |
   | 左手 | 0.9681 | 0.960 ✗ | 0.982 ✅ | **0.991 ✅ (nv67)** | 0.996 (nv107) |
   | 身體 | 0.9760 | 0.968 ✗ | 0.986 ✅ | **0.993 ✅ (nv77)** | 0.995 (nv100) |

   - **eps=0.002 是甜蜜點**:3 件全過,且 nv(73/67/77)≦ 藝術家(78/80/98)→ 覆蓋率追平/勝出但更精簡。
   - `epsilon_frac` 相對周長 → **尺度不變**,跨件大小通用;設為 v2 delaunay 分支預設。
   - 羽化邊(光暈)最吃取樣密度:eps 每收一半,IoU 明顯跳升。
3. **PSD→件→mesh 端到端一致**:直接對 `robot_parts.psd` 切出的原尺寸件生成,
   自覆蓋 IoU 0.98~0.99,與 atlas 區塊(0.70 縮小)結果一致 → S4 輸出可無縫餵給 S3。

## 可重現指令

```bash
# 對 Award 3 mesh 端到端整合 AC(atlas 區塊 = 藝術家 uv 空間)
for s in "機器人拆件/光暈" "機器人拆件/左手" "機器人拆件/身體"; do
  python3 tools/mesh_gen/validate_against_real.py \
    --skeleton assets/Award.json --atlas assets/Award.atlas --png assets/Award.png \
    --slot "$s" --name "$s" --gen v2      # 3 件 overall_pass=True
done

# S4→S3 端到端:PSD 切件 → 生成 mesh
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/generate_mesh_v2.py /tmp/robot_parts/00_光暈.png   # delaunay, self-IoU 0.98
```

## 未解 / 待續

- Award mesh 是 **weighted**;目前 S3 生成的是 **unweighted** mesh。若要真正「取代」藝術家的加權 mesh,
  需 S3 的 BBW 權重指派(綁到 Award 的控制骨)+ SkelToJson 寫回 —— 這是把生成 mesh 裝進真實骨架的下一關。
- 頂點預算:eps=0.002 對 ~500px 件產 67~77 頂點(合理);極大/極複雜件可能需上限保護(目前無硬上限)。
