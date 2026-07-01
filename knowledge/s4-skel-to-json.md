# S4 — SkelToJson:分層 PSD → 完整 Spine 3.8 skeleton JSON

- **結論**:新 `tools/mesh_gen/skel_to_json.py` 把「切件 + 生 mesh」自動組裝成**可被 Spine runtime
  載入的完整 skeleton JSON**,補齊 pipeline 缺的最後一環(先前只能切件、件→mesh,無法產完整骨架)。
  對真實 `robot_parts.psd` 端到端產出的骨架,**結構與真實生產 spine(Award)逐 slot 吻合**
  (4 條 AC 全過,exit 0)。
- **信心**:高 —— 對真實 PSD 驗證 + 對 Award ground truth parity + 用「讀真實資產的同一 loader」
  重載確認格式有效。**限制**:無實機 Spine runtime 驗(CDN 被政策擋);有效性以結構 schema +
  真實資產 loader round-trip 建立(非渲染級)。
- **階段**:第 2 階段 / S3×S4 pipeline 串接。

## 固化的真實慣例(來自 Award,見 s4-psd-to-spine-real.md)

1. **slot 命名 = `<prefix>/<圖層名>`**;`prefix` 是 **authoring 選擇(美術對件群的命名),未必等於檔名**
   → 工具做成可覆寫參數。**發現**:Award 真值前綴是中文群名 `機器人拆件`,但 repo 檔名為
   `robot_parts.psd` → 用檔名當前綴會 parity 失敗,`--prefix 機器人拆件` 才吻合。
2. **一圖層 ⇄ 一 slot ⇄ 一 attachment(同名)**;**draw order = slots 陣列順序 = PSD z(由下而上)**。
3. **mesh vs region 由呼叫端指定**(美術決定):`--mesh` 列出 mesh 件(Award 分配:光暈/身體/左手),
   其餘 region。mesh 件用覆蓋率驅動 auto-epsilon 生成(承 s3-award-mesh-endtoend.md)。
4. **每件一根骨**,置於件在畫布的世界中心(offset+size/2 → 中心原點、y-up),root 在畫布中心
   → mesh 頂點(件-local 置中)+ 骨骼平移 = 還原原圖版面。
5. **attachment width/height = 件真實像素尺寸**;**+2px 是 atlas packer padding(runtime 產物,非
   authoring)** → 對 Award parity 容忍 ±2px(實測 ours=PSD 尺寸、Award=+2,全數吻合)。

## 輸出格式(Spine 3.8,雷點對齊 CLAUDE.md)

```
skeleton{spine:"3.8.99",width,height,x,y} · bones[root + 每件一根] · slots[draw order]
skins:[{name:"default",attachments:{slot:{name:{...}}}}] · animations:{}
mesh attachment:{type:"mesh",uvs,triangles,vertices,hull,width,height}(unweighted,hull 排最前)
region attachment:{type:"region",x,y,rotation:0,width,height}
```

## 自驗閘(4 AC,無需實機)

| AC | 檢查 | robot_parts 結果 |
|---|---|---|
| AC1 schema | slot→bone/attachment 存在;mesh unweighted+hull+索引+無孤兒;region 尺寸 | ✅ 6 bones/5 slots |
| AC2 roundtrip | 用**讀真實資產的存取路徑**(`skins[0].attachments[slot][name]`)重載 mesh,對件 alpha 跑覆蓋率 | ✅ IoU 0.974~0.980 |
| AC3 layout | 每件骨骼世界中心 == PSD 版面中心(±0.5px) | ✅ |
| AC4 award parity | 對 Award:slot 名存在 + mesh/region 型別吻合 + 尺寸 ±2px | ✅ 5/5 slot 吻合 |

額外獨立驗:寫出檔用 `deform_eval.load_mesh`(讀 main_draw/Award 的同一函式)重載 → 3 mesh
setup 拓樸乾淨、draw order 正確(光暈→右手→頭→身體→左手)。

## 可重現

```
python3 tools/mesh_gen/skel_to_json.py assets/robot_parts.psd --prefix 機器人拆件 \
    -o /tmp/robot_skeleton.json          # 4 AC 全過,overall_pass, exit 0
```

## 端到端 pipeline 現況(第 2 階段能力已串通)

`psd_slice`(PSD→件+manifest,S4 切圖)→ `generate_mesh`(件→mesh,S3)→ **`skel_to_json`
(件→完整 skeleton JSON,本次)**。三段皆有自驗閘且對真實生產標的(robot_parts↔Award)驗證。
**尚缺**:骨架權重/綁定(mesh 目前 unweighted、每件一根骨無層級動作)= S5;動畫 timeline。

## 下一步候選

- **S5 骨架半自動**:目前每件一根骨(平面擺放),無父子鏈/權重。人形 RTMPose/非人形光流分群
  → 關節草案;weighted mesh 綁定。**pivot 是唯一卡死處**(需人微調)。
- 把覆蓋率驅動 auto-epsilon 沉澱進 `generate_mesh` 本體(目前在 validator/assembler 內各有一份)。
- S2 補圖閘 / 骨架閘(純 CPU)。
