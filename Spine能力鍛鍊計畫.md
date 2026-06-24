# Spine 能力鍛鍊計畫

> 從「影片反推需求」到「自主逼近目標」。本文回答你的核心問題：**切圖、補圖、新增/編輯 mesh、骨架設計這些 subagent/skill 還不成熟，該怎麼鍛鍊？**
>
> 結論先講四句：
> 1. **你上次拿到整張未拆圖的根因**，是缺了「從影片反推資產需求」這個上游步驟 —— 不是切圖工具爛，是根本沒先算出「該切成哪些件」。
> 2. **「鍛鍊」一個 LLM 驅動的 agent 不是梯度訓練**，而是給它更好的「程序＋工具＋評估器＋知識庫＋benchmark」。其中**評估器是樞紐**：能自我評分，才能自主迭代收斂。
> 3. **最大的策略槓桿是改「輸入契約」**：能要到分層 PSD，切圖＋補圖兩個最難的問題大半消失（純 CPU 可解）；要不到才走平面圖的硬路。
> 4. **整條鏈唯一真正卡死的環節是「骨架放哪」** —— mesh 拓樸＋權重＋寫 JSON 現實上可全自動，但骨頭位置仍需人或半自動。把人力集中在這裡。

---

## 第一部分：反推框架（影片 → 需求規格）

你的直覺完全正確：**不該從「畫一張圖」出發，該從「影片裡的運動」反推。運動決定一切。**

一個部件之所以要獨立存在，唯一理由是它在影片裡**半獨立地運動**。手臂相對身體轉 → 手臂要獨立件；披風飄動 → 要 mesh；眼睛眨 → 眼皮要獨立件。所以分析運動，就反推出了整份資產需求。

### 四條推導鏈

| 反推出 | 從影片的什麼 | 怎麼算 |
|---|---|---|
| **① 拆件需求** | 哪些區域各自做剛性運動 | 運動分割（光流分群）：一起平移/旋轉的像素 = 同一件 |
| **② 遮擋/補圖需求** | 部件重疊 × 最大位移 | 兩件在 setup 重疊、動畫中分開 → 下層被遮區要補；補多大 = 最大位移 |
| **③ 骨架需求** | 關節位置與運動鏈 | 人形用 pose estimation 抓關節；非人形用運動分群找旋轉中心（pivot） |
| **④ mesh 需求** | 部件是剛性還是非剛性形變 | 運動殘差小 = region 貼圖；殘差大（彎/拉/飄）= mesh + deform/權重 |

### 產出：Asset & Rig Requirement Spec（資產與綁定需求規格）

反推的最終產物是一張表，**它就是「所需的圖片格式」的精確定義** —— 答案永遠不是單張未拆圖，而是：

| 部件 | 類型 | 需補繪? | 綁定骨頭 | pivot 位置 | 運動來源(影片) |
|---|---|---|---|---|---|
| 上臂 | region | 否 | arm_upper_L | 肩關節 | 0.2–0.6s 旋轉 −40° |
| 前臂 | region | 是(被上臂遮) | arm_lower_L | 肘關節 | 跟隨 + 0.4s 揮 |
| 披風 | **mesh**(自由+deform) | 否 | cloth_root + 3 子骨 | — | 全程飄動,非剛性 |
| 軀幹 | region | 是(被雙臂遮) | spine | 髖 | 輕微呼吸 |

> 這份規格是後續所有能力的**共同真相來源**：切圖照它切、補圖照它補、骨架照它搭、mesh 照它貼。沒有它，每個能力都在瞎猜。

---

## 第二部分：「鍛鍊」的真義 —— 為什麼核心是評估器

這些 subagent/skill 是 LLM＋腳本＋SOP 組成的，**不能用資料梯度訓練**。能讓它們變強的只有五件事，我稱為「鍛鍊五件套」：

| 件 | 是什麼 | 為什麼讓能力變強 |
|---|---|---|
| **程序** | 決策規則／SOP／checklist | 把「老手怎麼判斷」寫成可重複步驟 |
| **工具** | 腳本、模型、CLI | 把手工變自動，把不可能變可能 |
| **評估器** ★ | 自動品質閘：產出對不對的可機讀判準 | **樞紐**：沒有它就無法自主迭代——agent 不知道自己對沒對，只能問你 |
| **知識庫** | 模板、案例、反例 | 起手不從零，少踩重複的坑 |
| **benchmark** | 固定測試案例＋量表 | 能衡量「練成沒」，改動有沒有退步 |

**評估器是降低你參與度的關鍵。** 上一版流程慢，就是因為「對不對」這個評估被外包給你。每個能力都必須配一個能自我檢查的評估器，自主迴圈才能收斂。

> 一個重要的方法論啟示（來自 2026 的 SpriteToMesh 研究）：他們試圖用神經網路「直接預測 mesh 頂點位置」**完全不收斂**，因為頂點放哪是「美術決定」、同張圖有無數種合法解。教訓是：**別用 ML 去學那些『沒有唯一正確解』的美術決定**，改用確定性演算法產生「夠用」的結果，再用評估器把關。這正是鍛鍊這些能力的正確姿勢。

---

## 第三部分：四能力的成熟度拆解與鍛鍊方法

每節都附：真正的子問題、現實可用工具（已標 CPU/GPU）、鍛鍊重點、評估器、誠實的限制。

### 3.1 切圖（資產拆件）

**真正的子問題**：不是「怎麼切」，是「先知道該切成哪些件」（=第一部分的反推），再切。盲切只會切出沒用的塊。

**工具現實**（研究結論，2026）：
- **沒有任何純 CPU、開源、單張圖 → 全自動拆件＋補繪的方案。** 真正會拆件的工具全吃 GPU 或付費雲。
- **最乾淨路線 = 改輸入契約：要求分層 PSD**。`psd-tools`（MIT、純 CPU、秒級）逐層導出對位 PNG，零 AI、零 GPU、可完全自動化。
- CPU 半自動：`rembg`(isnet-anime, 去背) + `MobileSAM`(CPU <300ms, 按關節點投點切粗塊)，但**無法補遮擋區**，只到半成品。
- GPU 路線：`See-Through`（SIGGRAPH 2026, 開源, 需 12GB+ VRAM）單圖→24 語意層已補繪 PSD，品質最佳；或商業雲（imagetolayers / God Mode AI，API 不明確、品質有爭議）。

**鍛鍊重點**：把「反推→決定件清單」做成程序；把 psd-tools 抽層、rembg/MobileSAM 粗切包成工具腳本。

**評估器**：把切出的所有件在 setup pose 重新疊合 → 能否還原原圖輪廓（reconstruction test）？各部件的關節點是否落在自己件內？有無破碎/孤兒像素？

**誠實的限制**：平面圖在無 GPU 下做不到「乾淨拆件＋補繪」。這是硬限制，靠改契約（PSD）或借 GPU 繞過，不是靠調 prompt。

### 3.2 補圖（補遮擋區）

**真正的子問題**：補哪裡（由①②反推：重疊×位移自動算出）、補多大、用多重的工具。

**工具現實**（分級降階，多數缺口落在前兩級）：
- **第 0 級**：邊緣外擴 / 像素 clamp + 羽化。縫窄又被前景壓住時根本不用 inpaint，numpy 幾行、瞬時。
- **第 1 級**：OpenCV `cv2.inpaint`(Telea)。純色、平滑漸層小缺口，CPU 毫秒。
- **第 2 級**：**LaMa**(透過 IOPaint, CPU ~2–3 秒/張)。有皺褶/紋理或缺口稍大時的主力，免費、品質好 —— **設為預設「正式」補圖引擎**。
- **第 3 級**：GPU diffusion（Flux Fill/SDXL, ~$0.04–0.05/張）或人工。只在「大缺口需語意腦補新結構」「LaMa 糊掉」「主視覺關鍵件」時升級。

**鍛鍊重點**：把分級降階寫成程序（依缺口性質自動選級）；把 LaMa/IOPaint 接成 CPU 工具。

**評估器**：補完後，在**極端姿態關鍵幀** render → 掃描露出區有無破洞、接縫、色偏、亂編內容。

**誠實的限制**：**沒有 rigging 專用的去遮擋工具**（業界標準其實是美術手畫被遮層，或用渲染順序把洞藏在前景後）。需要真正想像力的大缺口，CPU 解不了，該升級 GPU 或交人工。

### 3.3 mesh（新增/編輯網格）—— 最大的可解鎖點

**真正的子問題**：哪些件要 mesh（由④反推）、頂點放哪、密度多少、走「自由 mesh + deform」還是「綁骨權重」。

**工具現實 —— 好消息**：**「生成 mesh 拓樸 + 綁權重 + 寫進 Spine JSON」現實上可純 CPU 全自動、生產可用**（2026 SpriteToMesh 已驗證，每張數秒）：
- alpha → 高品質三角網格：`cv2.findContours` → Douglas-Peucker 簡化 → 多通道 Canny 抓**內部視覺邊界**放點 → Delaunay（`triangle` 或 OpenCV Subdiv2D）→ 用「三角形重心是否在 mask 內」過濾。**關鍵差異**：別像 Spine/Live2D 內建 auto-mesh 只看 alpha 鋪規則格點，要沿內部視覺邊界放點，變形才漂亮。
- 自動權重：**BBW**(Bounded Biharmonic Weights) 是 2D 標準、純 CPU 可行，libigl 有 Python 綁定（注意範例多為 3D、部分綁定有 bug 史，2D 要自己餵三角網格＋骨 handle）。
- 讀寫 Spine 二進位：`SkelToJson`(pip 可裝) 無損把 .skel ↔ JSON。

**這直接移除 spine-ai-editor skill 現在的限制**（「新建 mesh 拓樸/綁骨需 Spine 編輯器」）—— 寫一個 mesh 生成器腳本就能程式化做到。

**Spine JSON mesh 格式坑（生成時必守）**：
- `vertices`：非權重 = `x,y` 對；權重 = 每頂點先寫骨數 n，再 n 組 `bone_index, bindX, bindY, weight`（攤平變長陣列）。
- **weighted 判定**：runtime 看 `len(vertices) > len(uvs)`，絕不能讓非權重 mesh 的 vertices 意外超過 uvs。
- `hull`：殼頂點數，且**殼頂點必須排在 vertices 最前面**。
- bind 座標是 setup pose 下頂點**相對該骨**的座標，不是世界座標。
- 權重每頂點需正規化（和為 1）。

**Spine 是 LBS 不是 ARAP**：Spine runtime 用線性混合蒙皮（權重加權剛體變換），不是 ARAP。ARAP 可當「離線算漂亮 deform 目標」的引擎，把結果寫進 `deform` timeline（逐頂點 offset，不需權重）；走 bone-driven 才需要 BBW 權重。兩條 Spine JSON 都支援。

**評估器**：在極端 deform 幀檢查 —— 三角形有無自交、貼圖有無撕裂、輪廓是否吻合影片目標、頂點數 vs 效能預算。

**誠實的限制**：**頂點「放哪」是啟發式逼近，不保證美術級**（無唯一解，見第二部分）。能做到「夠用、生產可用」，極致細修仍可能要人。

### 3.4 骨架設計 —— 整條鏈唯一卡死的環節

**真正的子問題**：關節在哪、階層怎麼接、**pivot 放哪（最關鍵參數，放錯則旋轉不自然）**。

**工具現實**：
- **人形**：`RTMPose`(CPU 70–90 FPS, SOTA) 首選，`MediaPipe Pose`(CPU 30+ FPS) 輕量備選。直接吐關節點。
- **非人形**（機甲/生物/布料）：人形模型完全無效。CPU 走 **Farneback 稠密光流 + 運動向量分群**找剛性塊與其旋轉中心；有 GPU 則 `CoTracker3`/`TAPIR` 點追蹤品質遠勝。

**鍛鍊重點**：把「運動 → 關節 → pivot」做成半自動程序：自動產骨架草案，人只微調 pivot。

**評估器**：對每根骨單獨旋轉 → 預覽是否像影片那樣繞正確支點轉（pivot 驗證）。

**誠實的限制**：**這是唯一卡死的地方**。SpriteToMesh 也明說「骨架生成是 future work」，BBW/heat 都假設骨頭已存在。所以「單圖/影片 → 全自動 rig」目前做不到 —— 骨架仍需人定義或半自動＋人微調。**這正是你的人力該集中投入之處**（也呼應 SOP 的 A 類岔路）。視角限制：pose estimation 正面準、側面與自我遮擋掉精度。

---

## 第四部分：漸進落地路線（先練什麼）

依「槓桿 ÷ 難度」排序，每步都用 `main_draw`（已解析）和你的機器人案例當 benchmark：

| 步驟 | 做什麼 | 為何先做 | 環境 |
|---|---|---|---|
| **S1 反推分析器** | 影片 → Asset & Rig Requirement Spec | 補上最缺的上游，根治「整張未拆圖」 | 人形 CPU 可行;非人形 CPU 光流 |
| **S2 評估器套件** | 為四能力各寫自我品質閘 | 樞紐:沒它自主迴圈無法收斂 | 純 CPU(含我的 vision 比對) |
| **S3 mesh 生成器** | SpriteToMesh 式拓樸 + BBW 權重 + SkelToJson 讀寫 | 最大具體解鎖,純 CPU 可全自動 | 純 CPU |
| **S4 切圖＋補圖** | PSD-first 契約 + CPU 半自動 fallback;補圖分級降階 | 高頻需求,先把 CPU 能解的部分自動化 | CPU 為主,大缺口/平面圖升 GPU |
| **S5 骨架半自動** | 運動 → 關節草案 → 人微調 pivot | 唯一卡死環節,做到半自動already大勝 | 人形 CPU;非人形 CPU/GPU |

> 順序邏輯：先有「需求規格(S1)」和「能自評(S2)」，後面三個能力才有對的目標和自主收斂的能力。先衝 mesh 生成器(S3) 因為它純 CPU、收益大、又能立刻拆掉現有 skill 的限制。

---

## 第五部分：兩條輸入軌（誠實的策略分叉）

| | Track A：分層 PSD 源 | Track B：平面/AI 生成圖（如機器人影片） |
|---|---|---|
| 切圖 | psd-tools 純 CPU 秒解 | 需 GPU(See-Through) 或 CPU 半自動妥協 |
| 補圖 | 多半不需要(層本就完整) | 分級降階,大缺口需 GPU/人工 |
| 適用 | 能控制美術交付時 | 只有成品圖/AI 生成時 |
| 建議 | **能要 PSD 就要 —— 最大槓桿** | 要不到才走;接受品質與 GPU 成本 |

**最重要的單一建議**：把「交付分層 PSD」變成資產規範。研究顯示無 GPU 下平面圖自動拆件＋補繪基本做不到；但只要源是分層的，整個 CPU pipeline 就通了。**改契約比硬攻演算法划算得多。**

---

## 附：成熟度量表（怎麼判斷「練成沒」）

| 能力 | 練成的判準（benchmark 通過條件） |
|---|---|
| 反推分析器 | 對機器人影片，自動產出的件清單 ≈ 人工判斷的件清單(召回率) |
| 切圖 | 重組還原原圖輪廓;關節點落在件內;0 孤兒像素 |
| 補圖 | 極端姿態幀 0 破洞/0 明顯接縫 |
| mesh | 極端 deform 0 自交/0 撕裂;頂點數在效能預算內;輪廓吻合 |
| 骨架 | 每骨單獨旋轉 pivot 正確;整體動作疊影片相似度達標 |

---

## 來源

研究自三個並行 subagent，主要依據：
- SpriteToMesh（2026-02，程式化 PNG→mesh pipeline）: https://arxiv.org/abs/2602.21153 ・ SkelToJson: https://github.com/BastienGimbert/SkelToJson
- Spine JSON / mesh 官方格式: http://en.esotericsoftware.com/spine-json-format ・ http://en.esotericsoftware.com/spine-meshes
- 切圖：See-Through (SIGGRAPH 2026) https://github.com/shitagaki-lab/see-through ・ psd-tools https://github.com/psd-tools/psd-tools ・ rembg https://github.com/danielgatis/rembg ・ MobileSAM https://docs.ultralytics.com/models/mobile-sam
- 補圖：LaMa https://github.com/advimman/lama ・ IOPaint(CPU) https://github.com/Sanster/IOPaint ・ Open-World Amodal Completion (CVPR 2025) https://github.com/saraao/amodal
- 權重/變形：BBW https://igl.ethz.ch/projects/bbw/ ・ libigl Python https://libigl.github.io/libigl-python-bindings/ ・ triangle https://github.com/drufat/triangle
- 動作擷取：RTMPose https://arxiv.org/pdf/2303.07399 ・ MediaPipe Pose ・ CoTracker https://github.com/facebookresearch/co-tracker ・ TAPIR https://deepmind-tapir.github.io/
