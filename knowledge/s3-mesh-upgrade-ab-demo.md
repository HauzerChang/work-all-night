# 成果發表 A/B — 用研究成果對 main_draw 做「網格升級」最佳化

- **結論**:把研究成果(S3 v2 strip 生成器 + deform 場轉移 + deform 幾何閘)串成一個**端到端最佳化 pipeline**,
  對真實 `main_draw` 的 4 片會變形網格(curtain_left/right, shadow, shadow2)自動升級,產出可在 Spine 預覽器
  對比的 A(原)/B(升級)。B **忠實重現 A 的動畫**(形狀 IoU 0.958~0.986)、**變形更平滑**(邊界轉折角砍半 ~55%)、
  **同級穩健**(全關鍵影格 0 自交 / 0 翻面),且**時間軸/緩動/骨架/其它 36 slot 全不動**。
- **信心**:高(逐格量測 + 結構驗證 + 視覺對照;A/B 皆合法 Spine 3.8 JSON)。
- **階段**:第 2 階段收斂 → 第 3 階段(pipeline 整合)的第一個端到端展示。
- **可重現**:`python3 tools/demo/build_ab_demo.py` → `delivery/{A,B}/`;對照圖 `delivery/verify_ab_deform.png`。

## Pipeline(全自動、無人工調點)

1. **細分**:光柵化「藝術家 mesh 自身的 footprint」(**不是圖檔 alpha**)→ `gen_strip` 直條細分 → 21v/12v→64v/42v。
2. **setup 重採樣**:把原 setup local 當 uv 空間的場,RBF thin-plate 重採樣到新格點(仿射精確、非仿射 warp 平滑細分)。
3. **deform 轉移**:每個 deform 關鍵影格,把原位移場 RBF 平滑重採樣到新拓樸;curve/time 原樣保留。
4. **幾何閘**:每幀 `deform_eval.eval_pose` 驗證;不乾淨 → 該幀退線性(不劣於 A)。

## 三個關鍵踩雷 & 修正(這次新學到)

1. **軟漸層 alpha 不能拿來切網格形狀**:shadow 是半透明漸層,`alpha>8` 閾值只框到密核 → 網格變細(shape IoU 0.45)。
   **修正:改光柵化「藝術家 mesh footprint」當形狀來源**(那才是真正上貼圖的範圍),shadow IoU 0.45→0.97。
   通用教訓:要細分既有 mesh,形狀真值是「該 mesh 自己」,不是原始圖檔 alpha。
2. **shadow2 是非仿射 setup warp**:與 shadow 共用 uvs 但 vertices 被藝術家逐點彎成曲線;
   逐軸線性擬合殘差 14.7px、full 2D 仿射仍 14.2px。**修正:用 RBF thin-plate 把 setup 當 uv 場重採樣**
   (仿射精確、非仿射也忠實),殘差→0。教訓:Spine unweighted mesh 的 vertices↔uvs 可為任意逐點 warp,別假設仿射。
3. **deform 是逐頂點索引綁死拓樸**:換網格 → 所有 deform timeline 失效,必須逐格重建;
   全長 `vertices` 陣列(去掉 sparse offset)+ 保留 curve/time 即合法且時序不變。

## 量化(delivery/README.md 有完整表)

- 忠實度(shape IoU B vs A,最大變形幀):0.985 / 0.986 / 0.974 / 0.958。
- 平滑度(邊界轉折角,9 動畫平均):curtain ~25°→~11°、shadow ~34°→~14°(↓54~59%)。
- 穩健度:全關鍵影格 A/B 皆 0 自交 / 0 翻面。

## 意義

- 這是研究四能力裡「**編輯/新增 mesh**」+「**deform 場轉移**」+「**幾何自評閘**」三者第一次串成**對真實資產的端到端最佳化**,
  且產物是**可直接載入預覽器的合法 Spine 檔**。為第 3 階段(pipeline 化)提供了可複用骨架:
  `既有 mesh → 細分 → setup/deform 場轉移 → 幾何閘 → 回寫 JSON`。
- 適用邊界:針對 **unweighted + deform-timeline** 的網格(布幕/陰影/旗幟類軟布料)。weighted(靠骨權重)網格的
  等價升級需先做權重生成(見 `s3-psd-to-mesh-real.md` 下一步)。
