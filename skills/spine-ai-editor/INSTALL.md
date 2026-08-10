# spine-ai-editor — 安裝指南

## 三條安裝路徑

### 路線 A：裝進現有 plugin（推薦給已有 lula plugin 的人）

直接把整個 `spine_ai_editor_skill/` 目錄複製到 lula plugin 的 skills 目錄：

```
C:\Users\user\AppData\Roaming\Claude\local-agent-mode-sessions\<session>\rpm\plugin_01LnuJi9BGSmtQcmtEnkmFqk\skills\
└── spine-ai-editor/        ← 把本 skill 整個資料夾放這裡（rename SKILL.md 的名字也要保持）
    ├── SKILL.md
    ├── INSTALL.md
    ├── references/
    └── assets/
```

重啟 Cowork session 或重 load skills 後，這個 skill 就會被自動 register。觸發詞請參考 SKILL.md 的 description 欄位。

### 路線 B：打包成 `.skill` 檔給其他人安裝

把整個目錄 zip 起來改副檔名：

```bash
cd outputs/spine_ai_editor_skill
zip -r ../spine-ai-editor.skill .
```

完成後可以拖進 Cowork 介面安裝（會跳 "Save skill" 按鈕）。

### 路線 C：手動讀（不安裝）

如果不裝 skill，遇到 Spine 相關任務時手動 Read 對應的 reference doc：

- 解析 Spine：Read `references/spine_3_8_reference.md`
- 加動畫：Read `references/animation_patch_patterns.md` + assets/patch_templates/add_animation.py
- 結構擴充：Read `references/structural_expansion.md` + assets/patch_templates/add_bone_reparent.py
- 影片轉動畫：Read `references/video_to_spine_pipeline.md` + assets/patch_templates/video_to_animation.py
- Cocos MCP 推送：Read `references/cocos_mcp_push_sop.md`

---

## 結構總覽

```
spine-ai-editor/
├── SKILL.md                              ← 入口頁 + 觸發詞
├── INSTALL.md                            ← 本檔
├── references/                           ← SOP + 資產前處理知識
│   ├── spine_3_8_reference.md           Spine 3.8 JSON 結構快速參考
│   ├── animation_patch_patterns.md      7 種常見動畫 pattern
│   ├── structural_expansion.md          加 bone / reparent / 配件 SOP
│   ├── video_to_spine_pipeline.md       影片/分鏡圖 → 動畫
│   ├── cocos_mcp_push_sop.md            Cocos MCP 9 步推送
│   ├── mesh_pipeline_sop.md            ★資產前處理 pipeline SOP(S2/S3/S4,純 CPU)
│   ├── mesh_findings.md                ★累積研究發現(蒸餾)+ 評估器校準教訓
│   └── psd_contract.md                 ★給美術的 PSD 分層交檔契約
└── assets/
    ├── validator_v0.py                   Spine 3.8 schema + 引用完整性 validator
    ├── patch_templates/
    │   ├── add_animation.py             加動畫範本（無結構變動）
    │   ├── add_bone_reparent.py         結構擴充範本（加 bone/slot/重綁/reparent）
    │   └── video_to_animation.py        影片 pipeline 範本（probe / extract / patch 三 stage）
    └── mesh_gen/                        ★純 CPU 資產前處理工具(整個資料夾一起用)
        ├── requirements.txt             numpy/opencv-python-headless/scipy/triangle/psd-tools
        ├── generate_mesh.py             PNG→mesh(Delaunay;含 target_verts 自適應 epsilon)
        ├── generate_mesh_v2.py          PNG→mesh(strip/auto;預設)
        ├── evaluate_mesh.py             靜態閘(IoU/重心/退化/孤兒/預算/格式)
        ├── deform_eval.py               變形閘(真實位移場轉移)
        ├── psd_slice.py                 分層 PSD→切件+manifest+重組無損自驗
        ├── atlas_crop.py                atlas 切件(多頁+CW derotate)
        ├── evaluate_slicing.py          切圖→重組保真閘
        ├── validate_against_real.py     整合 AC(對真實 deform mesh)
        ├── validate_award_mesh.py       端到端對藝術家真實 mesh
        └── make_test_mask.py / make_test_psd.py   合成 fixture(無真實資產時)
```

---

## 前置需求

| 需求 | 用途 | 必須？ |
|---|---|---|
| Python 3.8+ | 跑 patch 腳本與 validator | ✅ 必須 |
| numpy / opencv-python-headless / scipy / triangle / psd-tools | 資產前處理(S2/S3/S4);`pip install -r assets/mesh_gen/requirements.txt` | 資產前處理必須(純 CPU) |
| ffmpeg | 影片 probe + 抽 frame | 影片流程必須 |
| Cocos Creator MCP（DaxianLee 或同等） | 即時推到 Cocos preview | Cocos 流程必須 |
| Cocos Creator 3.7.3+ | 預覽動畫 | Cocos 流程必須 |

純 JSON 操作（不接 Cocos）只需要 Python，最低門檻。資產前處理(PNG→mesh / PSD 切件)只需 Python + 上列 CPU 套件,**無需 GPU、無需 Cocos**。

---

## 快速測試 skill 是否生效

對著任何 Spine 相關問題說一句包含觸發詞的話，例如：

> 「幫我看一下這個 spine 檔，加一個 idle 變體動畫」

Claude 應該會：
1. 自動讀 SKILL.md
2. 確認是否需要 Parse 第一步
3. 走 reference doc 的 SOP
4. 用 patch template 寫腳本
5. （若有 Cocos MCP）按 9 步推送

如果沒觸發，可以明確要求：「用 spine-ai-editor skill 幫我做 X」。
