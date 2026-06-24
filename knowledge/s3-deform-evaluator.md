# deform-aware mesh 評估器 + 真實 benchmark — 進度與發現

- **相關階段**:PLAN.md S2(評估器套件)/ S3(mesh 生成器閘);專案第 2 階段。
- **信心**:高。評估器經正向(真實藝術家網格)+ 負向(故意壞網格)雙向驗證。

## 結論

用 Python 重現 Spine unweighted deform,並建立「會變形網格是否壞掉」的自我品質閘
(自交 / 翻面 / 退化 / 面積 / 包圍盒)。用真實 `main_draw` 4 mesh × 9 動畫當 benchmark。

## 產出

- `tools/mesh_gen/deform_eval.py` — Spine deform 重現 + 幾何檢查 + `benchmark_real()` + `stress_field()`。
- 資產:`assets/main_draw.json` / `assets/main_draw.atlas`。

## 關鍵發現

1. **真實 benchmark 全乾淨**:4 個 mesh(curtain_left/right 21v、shadow/shadow2 12v)在 9 支動畫、
   含相鄰幀內插共逐幀取樣下,**0 自交 / 0 翻面 / 0 退化**(`_checker_validated: true`)。
   → 確認「藝術家手做的好網格」在 deform 下的標準 = 完全乾淨,這就是生成器要達到的門檻。
2. **面積變化範圍**:窗簾 open/close 約 1.0–1.14;idle2(飄動最細)約 0.97–1.01。真實 deform 最大頂點
   位移 **~315px**(窗簾全開,346 寬)。→ 校準閘門壓力的依據。
3. **耐變形對比**:對「真實 curtain_left」與「我生成的合成 mesh」施加同一空間位移場,
   **兩者都撐到 400px(>315 真實上限)仍 0 自交** → 生成器的拓樸耐變形度 ≈ 藝術家手做。
4. **檢查器有鑑別力(負對照)**:故意交叉拓樸 → 抓到 self_intersection;頂點翻到對側 → 抓到 triangle_flip。
   非「永遠 pass」。

## 設計重點(供後續沿用)

- deform 在 **attachment-local 空間**逐頂點加 offset 即可判定拓樸正確性,不需控制骨的世界變換,
  也不需 PNG(對照 CLAUDE.md 雷點 #3/#4)。
- sparse deform frame:`offset`(預設0)+ `vertices` 段,補零對齊成全長再加。
- 取樣 = 每 keyframe + 相鄰幀線性內插(substeps),抓變形過程中的瞬時極端。
- `stress_field()` 是空間位移場(依頂點正規化位置施力),可施於任一拓樸 → 公平比較不同 mesh。

## 已知限制 / 下一步

1. **bezier curve easing 未精確重現**:取樣用線性內插(端點正確,中間路徑近似)。對極端瞬時足夠,
   若要精準對齊 runtime 幀,需實作 3.8 緊湊 bezier。
2. **weighted mesh 未支援**:目前只做 unweighted(main_draw 全 unweighted);weighted 需骨變換鏈。
3. **仍待 PNG**:texture 撕裂(UV 層面)目前以幾何自交近似;真實貼圖撕裂驗證需 `main_draw.png`。
4. **生成器耐變形門檻**:建議把「stress_field @ ~315px 下 0 自交/0 翻面」納入 S3 生成器的正式 AC。
