# S3 mesh 生成器 — 驗收目標 (Acceptance Criteria)

> 依 RULES.md「先定可檢查的 AC」。本工作塊:PNG(alpha) → unweighted Spine mesh,純 CPU,可自評。
> 對應 PLAN.md S3 完成條件的最小可驗證版本(先不做 BBW 權重)。

| 編號 | 檢查項 | 量測方式 | 門檻(預設) |
|---|---|---|---|
| AC1 | 輪廓吻合 | 把生成 mesh 三角形全部填滿成遮罩,與來源 alpha 算 IoU | IoU ≥ 0.95 |
| AC2a | 三角形落在形狀內 | 每個三角形重心是否在 mask 內 | ≥ 99% |
| AC2b | 無退化三角形 | 面積≈0 的三角形數 | = 0 |
| AC2c | 無孤兒頂點 | 每個頂點至少被一個三角形使用 | 0 孤兒 |
| AC3 | 頂點數預算 | 總頂點數 | ≤ budget(預設 64) |
| AC4 | Spine 格式正確 | unweighted(len(vertices)==2*nv==len(uvs))、hull 頂點排最前、triangles 索引在範圍內 | 全部通過 |

> 主觀品質(變形手感是否漂亮)不在此自評範圍,留待有真實資產 + 使用者審查(SOP L2)。
> 真實驗證需 `main_draw.png`(使用者端);本輪先用合成測試遮罩驗證 pipeline 端到端可跑。
