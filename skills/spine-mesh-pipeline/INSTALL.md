# 安裝 / 在 cowork / chat 啟用

這個 skill 是**自包含**的:`SKILL.md` + `tools/`(可跑的 Python)+ `references/`(蒸餾知識)+ `requirements.txt`。
把整個 `spine-mesh-pipeline/` 資料夾放到 Claude 會掃描 skills 的位置即可。

## 三種安裝方式

### A. 專案內(這個 repo 打開時就有)
本資料夾已在 repo 的 `skills/` 下。若要讓 Claude Code 在此專案自動載入,建立軟連結或複製到專案 skills 目錄:
```bash
mkdir -p .claude/skills
ln -s ../../skills/spine-mesh-pipeline .claude/skills/spine-mesh-pipeline   # 或直接 cp -r
```

### B. 使用者層級(所有 session / cowork / chat 都可用)
```bash
cp -r skills/spine-mesh-pipeline ~/.claude/skills/spine-mesh-pipeline
```
下次任何 Claude Code session(含 cowork)開始時就會列進可用 skills。

### C. claude.ai 網頁版 chat / cowork
在網頁的 **Skills** 設定上傳這個資料夾(壓成 zip 或依網頁指示)。上傳後,對話中提到觸發詞
(「PNG 轉 mesh」「PSD 切件」「mesh 會不會撕裂」…)就會自動套用。

## 相依套件

```bash
pip install -r requirements.txt
```
內容:`numpy`、`opencv-python-headless`、`scipy`、`triangle`、`psd-tools`。**純 CPU,無需 GPU、無需 Cocos。**

## 驗證安裝成功

```bash
cd tools
python3 make_test_mask.py                       # 造合成窗簾遮罩 -> /tmp 或當前目錄
python3 generate_mesh_v2.py <剛造的遮罩>.png -o /tmp/m.json
python3 evaluate_mesh.py /tmp/m.json <遮罩>.png  # 印出逐條 AC,exit 0 = 全過
```
能跑出 mesh JSON + 評估 pass 即代表工具鏈就緒。

## 與 spine-ai-editor 的分工

- **spine-mesh-pipeline(本 skill)**:生「乾淨資產」—— 從 PNG/PSD 產 mesh 與切件,並量化驗收(IoU/變形/重組保真)。
- **spine-ai-editor**:把資產「組進 spine JSON、改動畫、擴充骨架、推 Cocos 預覽」。

典型合流:`psd_slice`(切件)→ `generate_mesh_v2`/`generate(target_verts=)`(產 mesh)→ `evaluate_mesh`/`deform_eval`(驗收)
→ 交給 spine-ai-editor 的 SkelToJson / patch 工具組進 spine 並推 Cocos。

## 上游(完整研究記憶)

此 skill 是 `work-all-night` 自驅研究 repo 的打包快照。要看完整 log、未蒸餾 knowledge、真實測試資產
(main_draw / Award / 真實 PSD),或延續研究,回該 repo 讀 `RULES.md → PLAN.md → STATE.md`。
`tools/` 為上游 `tools/mesh_gen/` 的快照;若上游有更新,重新複製即可。
