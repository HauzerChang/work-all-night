# SkelToJson — 切件 → 可載入 Spine 3.8 資產集（S4→S3 端到端組裝）

- **結論**：把已對真實生產檔（Award）驗證過的慣例固化成寫出工具 `tools/mesh_gen/skel_to_json.py`：
  `psd_slice` 的 manifest（各件 PNG + offset/size/z/opacity）→ 產出**可載入的整組
  `<name>.json + .atlas + .png`**。對 2 份真實 PSD（`robot_parts` 5 件、`Symbol_Ww` 18 件）
  端到端自驗 **5 條 AC 全過**，切回各件 alpha-IoU **= 1.0（無損 round-trip）**。
- **信心**：高（兩份真實生產 PSD + 端到端 round-trip + 結構完整性閘 + 對照 Award 結構慣例）。
- **階段**：第 2 階段 / S4→S3 銜接（把切圖 S4 + mesh S3 串成「件→Spine JSON」）。

## 固化的慣例（全部來自 Award 真值，見 s4-psd-to-spine-real）

1. **命名**：slot = attachment = atlas region = `<PSD檔名(去副檔名)>/<圖層名>`（namespace 前綴；
   Award 用中文 PSD 名「機器人拆件」當前綴，本工具用實際檔名 `robot_parts`）。
2. **一件 → 一 slot → 一 bone（置於該件中心）→ 一 attachment（置中於 bone）**。
   座標換算：PSD（y-down、原點左上）件中心 (l+w/2, t+h/2) → Spine bone (cx−W/2, H/2−cy)；
   region attachment x=y=rotation=0（置中即世界位置正確）；mesh 頂點已是「件中心為原點、y 上翻」對齊 bone。
3. **draw order = PSD z（由下而上）**。
4. **mesh vs region**：`--mesh <圖層名>` 的件用 S3 `generate_mesh_v2(auto)` 生成 mesh attachment，
   其餘 region。對 robot 跑 光暈/身體/左手=mesh（與 Award 分配一致）、右手/頭=region。
5. **skin 為 array 形式** `[{"name":"default","attachments":{...}}]`（對齊 Award 3.8.99）；`spine":"3.8.99"`。

## 打包 atlas（簡單 shelf，無損）

- shelf packer（高的先放、超寬換層），**+2px gap = padding**，**無旋轉、無縮放**。
- 生產 packer 的 ~0.70 縮放與旋轉是**省記憶體的打包細節，非正確性所需** → 本工具從略，
  保持 attachment width/height = **真實件尺寸**、region 尺寸與之吻合（最簡單且自洽）。
- 同時用 PIL 合成 sheet PNG（原始件貼入），使三檔成為可載入整組。

## 自驗閘（5 AC，`--verify`）

| AC | 檢查 | robot / symbol |
|---|---|---|
| AC0 完整性（可載入性） | slot.bone 存在、mesh 三角索引在頂點界內、uvs/tris 長度整除 | PASS |
| AC1 結構/命名 | bones=件+1、slots/skin keys == `<psd>/<layer>` 全集 | PASS（6骨5slot / 19骨18slot） |
| AC2 attachment 尺寸 | width/height == 件 size | PASS |
| AC3 atlas region | 每 attachment 有對應 region 且尺寸吻合 | PASS |
| AC4 端到端 round-trip | 從產出 atlas+png 切回各件 alpha-IoU vs 原件 ≥0.99 | **min_iou = 1.0** |

## 範圍限制（誠實標註）

- 產出的 rig 是**中性骨架**：每件一根置中 bone、無階層綁定、**mesh 為 unweighted**、region rotation=0、
  無動畫（`animations:{"animation":{}}` 空殼）。即「位置正確、可載入、可在 inspector 檢視」的起點,
  **非**含骨骼動畫/權重的成品。
- **自動配權（BBW）與骨架階層/pivot 屬 S5**；本工具只負責「件 + S3 mesh → 結構正確的 Spine JSON」。
- 無法在此環境用 spine-webgl 實機載入確認（CDN 被網路政策擋）；以結構完整性 + 端到端 round-trip 替代。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py  assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/skel_to_json.py /tmp/robot_parts/manifest.json -o /tmp/robot_skel \
        --name robot --mesh 光暈 身體 左手 --verify     # 5 AC 全過,EXIT 0
python3 tools/mesh_gen/skel_to_json.py /tmp/sym_parts/manifest.json -o /tmp/sym_skel --verify  # region-only,PASS
```

## 下一步

- **自動配權**：給生成 mesh 配骨權（bone-distance / heat / BBW），讓件可被骨骼驅動（S3→S5 銜接）。
- **骨架階層/pivot**：S5 唯一卡死處（人微調）；可先做「運動→關節草案」再人工調 pivot。
- 若取得離線 spine-webgl，做實機載入 + inspector round-trip 視覺確認（目前 CDN blocked）。
