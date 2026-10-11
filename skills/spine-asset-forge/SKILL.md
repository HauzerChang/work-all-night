---
name: spine-asset-forge
description: |
  從**分層 PSD** 鍛造出**可直接載入的 Spine 3.8 靜態素材**(skeleton.json + .atlas + .png)。
  純 CPU、無需 Spine editor:自動反推規格 → 切件 → 生 mesh 拓樸 → 打包 atlas → 組 skeleton JSON,
  並附 **round-trip 品質閘**(重建 setup pose == 原 PSD composite)。

  Use when the user wants to:
  (1) 把一份**分層 PSD**(每層一個部位)自動轉成可載入 Spine 的三件組(json+atlas+png);
  (2) 由 PSD 反推**資產/rig 需求規格**(件清單、mesh-vs-region、z 序、pivot 草案);
  (3) 對生成的素材做**客觀驗收**(round-trip premult MAE / 孤兒率 / 未解析 attachment);
  (4) 為軟性/可變形件自動產 **weighted(骨綁)mesh**(`--weighted`,輪廓骨 + heat 權重);
  (5) 建「PSD → Spine 素材」的**自動化產線 / 回歸閘**(CI 式,防改壞)。

  觸發詞:「PSD 轉 spine」「分層圖轉骨架」「生成 spine 素材」「SkelToJson」「組 skeleton.json」
  「PSD 切件」「自動產 mesh 素材」「spine 素材鍛造」「素材 round-trip 驗證」「PSD → 可載入 spine」。

  Requires: Python 3 + numpy + opencv-python-headless + psd-tools + Pillow + triangle + scipy(皆純 CPU)。
  輸入契約:**分層 PSD**(每個部位一層;平面未分層圖無法自動拆件 —— 見「能力邊界」)。
---

# spine-asset-forge

把「一張分層 PSD」鍛造成「可直接拖進 Spine / Cocos 的素材三件組」,全程純 CPU、不開 Spine editor,
且每次產出都有**可量化的 round-trip 驗收**(不是肉眼看對不對)。

> **version: 0.1.0**（2026-10-11）
>
> Changelog：
> - **0.1.0** — 初版,固化本研究 repo 的 `spine-asset-forge` 區塊(達 skill 化門檻:所有核心能力 ≥ L2 GREEN、
>   SkelToJson 端到端達 L3;見 repo `skills/READINESS.md` / `skills/README.md` §3)。
>   對兩個真實 PSD(`robot_parts` 5 件 / `Symbol_Ww` 18 件)round-trip 全 PASS。
>
> **與 `spine-ai-editor` 的關係**:`spine-ai-editor` 的文件明說「mesh 交給 Spine editor」;本 skill 補上這塊空白——
> **從零生出靜態素材**(含 mesh 拓樸)。分工:**forge 從零生素材 → mesh-doctor 把關品質 → spine-ai-editor 讓素材動起來並落地 Cocos**。

---

## 能力邊界(誠實界定)

| 能力 | 成熟度 | 說明 |
|---|---|---|
| 反推分析:分層 PSD → 五段規格 | L2 真值驗收 | 件清單 / mesh-vs-region / z 序 / pivot 草案 / 分鏡先驗 |
| PSD → 各部位件 + manifest | L2 真值驗收 | 無損切件(offset/size/opacity/z),manifest 自驗閘 |
| 件 → mesh 拓樸(strip) | L2 真值驗收 | `generate_mesh_v2`;對 4 真實 mesh deform 乾淨(見 spine-mesh-doctor) |
| **SkelToJson 端到端 round-trip** | **L3 端到端** | robot_parts / Symbol_Ww 皆 PASS,一鍵驗證指令 |
| weighted(骨綁)mesh 產線 | L2 真值驗收 | `--weighted`:輪廓 PCA 軸骨 + heat 權重;結構件 si=0,軟件(光暈)為已知限制 |
| **未涵蓋(輸入契約相依)** | — | **平面未分層圖自動拆件**(CPU 到頂,語意召回 0,需 GPU/人工;本 skill 要求分層 PSD) |
| **未涵蓋(維度)** | — | **animation / weighted deform / pivot rig** 不在本靜態閘內(屬 `spine-anim-forge`,仍 HOLD) |
| **未涵蓋** | — | 貼圖級逐像素視覺瑕疵的美術主觀項 |

> ⚠️ **輸入契約是硬邊界**:本 skill 要**分層 PSD**(每部位一層)。若只有平面合成圖,平圖自動拆件在無 GPU 下
> 語意召回 0(誠實負結果,見 repo `knowledge/`),請先取得分層 PSD。

## 用法

### 主線:PSD → 可載入 Spine 素材 + 驗收(一鍵)
```bash
# 1) 鍛造素材(產 skeleton.json + skeleton.atlas + skeleton.png 到 <out>/)
python3 assets/build_spine.py <layered.psd> --out <out_dir>

# 2) round-trip 驗收(重建 setup pose == 原 PSD composite);PASS → exit 0
python3 assets/validate_build.py <layered.psd> <out_dir>
```

### 軟性/可變形件要 weighted(骨綁)mesh
```bash
python3 assets/build_spine.py <layered.psd> --weighted --out <out_dir>
# 另用 spine-mesh-doctor 的 weighted 變形閘量化骨綁品質
```

### 只想看反推規格(不生素材)
```bash
python3 assets/analyze_target.py <layered.psd>     # 五段規格:件/mesh-vs-region/z序/pivot/分鏡先驗
```

## 產出結構(Spine 3.8)

- **bones**:`root` + 每件一根 `b_<件名>`(置於件影像中心,y 上翻),parent=root。
- **slots**:每件一個,依 z 升序(由下而上繪製),bound 到自己的 bone。
- **skin default**:mesh 件用 `generate_mesh_v2` strip 拓樸(vertices/uvs/triangles/hull);region 件用矩形 region。
- **atlas**:shelf 打包各切件(rotate 全 false),libgdx `.atlas`;mesh uvs 為 region-local。
- **animations**:**留空**(setup pose 可載入;動畫屬 `spine-anim-forge`,本 skill 不含)。

## 判讀(validate_build round-trip)

| 指標 | 意義 | 門檻 |
|---|---|---|
| `premult_rgb_mae` | 由產出 json+atlas+png 重建 setup pose vs 原 PSD composite 的 premult RGB 平均誤差 | < 3.0 |
| `alpha_mae` | alpha 通道平均誤差 | 低 |
| `orphan_ratio` | 原圖有不透明像素但重建無覆蓋(漏件/錯位) | < 0.01 |
| 未解析 attachment | json 引用但 atlas/skin 找不到 | 必須 0 |

> 真實基準:robot_parts(5 件)MAE 0.031 / 0 孤兒;Symbol_Ww(18 件)MAE 0.236 / 0 孤兒,皆 `overall_pass: true`。

## ⚠️ Spine 3.8 / 產線地雷(本 skill 已內建處理)

1. **座標約定 builder/validator 必須一致**:影像左上原點 y 下;Spine root 畫布左下 y 上;件中心 (cx,cy) → bone(x=cx, y=H−cy)。
2. **mesh uvs 為 region-local**(非 atlas-global);`generate_mesh_v2` 已置中 + y 上翻,直接吻合 bone 局部座標。
3. **PMA**:重建與打包的 premultiply 要一致(對齊 Cocos `Premultiplied Alpha`),否則發光/半透明區 MAE 飆高。
4. **weighted mesh**:`vertices.length !== uvs.length`;hull 頂點排最前;bind 為骨局部座標;每頂點權重和=1(見 spine-mesh-doctor references)。

## 回歸 / 維護

升版前跑(於本研究 repo):`python3 tools/check_readiness.py`。對應區塊 `spine-asset-forge` 須全 GREEN。
曾 GREEN 轉 RED = 迴歸,擋升版。新能力須 ≥ L2 GREEN 才可加入(MINOR bump)。
詳見 `references/pipeline.md`(座標/atlas/round-trip 數學與產出契約)。
