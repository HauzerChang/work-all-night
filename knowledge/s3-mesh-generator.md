# S3 mesh 生成器 — 進度與發現

- **相關階段**:PLAN.md S3(mesh 生成器);專案第 2 階段(鍛鍊四能力)。
- **信心**:pipeline 端到端在合成資料上已驗證可跑;真實資產驗證待 `main_draw.png`。

## 結論

純 CPU 的「PNG(alpha) → unweighted Spine mesh」最小原型 + 自我品質閘(評估器)已建好並通過全部 AC。
驗證了 `Spine能力鍛鍊計畫.md` 3.3 的核心主張:**mesh 拓樸生成現實上可純 CPU 全自動**。

## 產出(`tools/mesh_gen/`)

| 檔案 | 用途 |
|---|---|
| `AC.md` | 本能力的驗收目標(6 條) |
| `generate_mesh.py` | alpha → findContours → Douglas-Peucker(hull) → Canny 內部邊界+格點補點 → 約束 Delaunay(triangle 'p') → 重心過濾 → Spine JSON mesh |
| `evaluate_mesh.py` | 評估器:IoU / 重心在內 / 退化 / 孤兒 / 預算 / 格式,逐條 pass-fail,回傳機讀 JSON 並以 exit code 表示 overall |
| `make_test_mask.py` | 合成窗簾測試遮罩(無真實 png 時驗證) |

## 第一輪結果(合成窗簾 346×535)

頂點 54(hull 14 + 內部 40)、三角 90,**6 條 AC 全 PASS**:
IoU **0.9895**、重心在內 **100%**、退化 0、孤兒 0、頂點 ≤64、格式正確。
內部點沿褶痕 Canny 邊界分布(非均勻格點),符合「沿內部視覺邊界放點,變形才漂亮」的設計目標。

## 環境

排程容器為臨時,CPU 套件需每次重裝。已驗證可裝:numpy 2.4.6 / opencv 4.13.0 / triangle / scipy 1.17.1。
見 `requirements.txt`。每次排程執行前先 `pip install -r requirements.txt`。

## 已知限制 / 下一步

1. **真實資產未驗**:需 `main_draw.png`(使用者端)才能對 `curtain_left` 真實貼圖驗 IoU 與 deform。
2. **未做 deform 穩健性 AC**:目前只驗 setup 形狀;尚未在「極端 deform 幀」檢查自交/撕裂(需 weighted 或 deform 偏移驅動,屬下一個 chunk)。
3. **未做 BBW 權重**:main_draw 4 個 mesh 全 unweighted,本輪刻意只做 unweighted;weighted + BBW 留待後續。
4. **未接 spine_inspector 實機驗證**:輸出格式已通過靜態檢查(AC4),但尚未在瀏覽器工具用 `setMeshVertices`/`getMeshBounds`/`screenshot` 跑 round-trip(瀏覽器自動化需另設)。
5. **內部點密度/min-dist 尚未對「頂點數 vs 變形品質」做掃描調參**。
