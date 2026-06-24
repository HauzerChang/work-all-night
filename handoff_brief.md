# Spine 專案交接 Brief（給 code 模式冷啟動）

> 這份是完整參考；快速版見 `CLAUDE.md`。讀完這份，一個全新的 Claude Code session 應能無上下文接手。

## 1. 專案是什麼

把 Spine 2D 角色變成「可程式化編輯、可即時視覺化驗證」的資產。環境：lula slot game、Cocos Creator 3.7.3、Spine 3.8.99。三階段：

1. 可視化檢視/編輯工具（**已完成** → `spine_inspector.html`）。
2. 用工具鍛鍊能力（切圖/補圖/mesh/骨架），每項用工具的視覺＋量化 API 自主驗收。
3. 整合成「2D 原圖 → spine 動畫」pipeline，讓 spine 動畫逼近目標影片。

## 2. 本次 session 產出（檔案）

| 檔案 | 內容 |
|---|---|
| `spine_inspector.html` | 工具本體（單檔，瀏覽器開）。建於官方 spine-webgl 3.8。 |
| `CLAUDE.md` | 精煉專案 context（放 repo 根目錄自動載入）。 |
| `handoff_brief.md` | 本檔，完整交接。 |
| `main_draw_解析報告.md` | 測試資產的完整解析（骨架/slot/mesh/動畫）。 |
| `自主Spine工作流_SOP.md` | 自主迭代工作流（驗收契約、自我驗證、升級政策、旋鈕）。 |
| `Spine能力鍛鍊計畫.md` | 反推框架 + 四能力鍛鍊方法 + S1–S5 路線圖（含 2026 工具研究）。 |
| `main_draw.json` / `main_draw.atlas` | 測試資產（png 在使用者端）。 |

## 3. 測試資產 main_draw

slot「開獎」動畫。28 bones / 40 slots / 1 skin(default) / 9 animations。attachment 74：region×69、mesh×4、clipping×1(root)。

4 個 mesh 全 unweighted：

| slot | region | 控制 bone | 頂點 | 三角 | hull |
|---|---|---|---|---|---|
| image/curtain_left | image/curtain_left | curtain | 21 | 24 | 16 |
| image/curtain_right | image/curtain_right | curtain | 21 | 24 | 16 |
| image/shadow | image/shadow | shadow_L | 12 | 10 | 12 |
| image/shadow2 | image/shadow | shadow_R | 12 | 10 | 12 |

9 支動畫：main_draw_close/comeout/hit/loop/open(2.67s,最長)/main_idle/idle2(deform最細)/idle3/static。窗簾在全部 9 支都有 deform。

## 4. Spine Inspector 工具 + 完整 API

開啟 `spine_inspector.html`，拖入 json+atlas(+png)。沒 png → debug 線框模式（看 mesh 拓樸最佳）。UI：左 bones 樹 + slots/attachments；中 畫布(縮放/平移/debug 線框/頂點疊圖/參考圖)；右 Inspector + 編輯 JSON；下 動畫時間軸。工具列：debug 切換(骨頭/三角/外框/區塊框/裁切)、貼圖、PMA、頂點、置中、日誌。

### window.spineTool（agent 介面，全方法）

- `ready()` → bool
- `loadFromText(jsonText, atlasText, pngDataURL|null)` 程式化載入
- `listAnimations()` → [name]
- `setAnimation(name)` / `play()` / `pause()` / `setTime(t秒)` / `setSpeed(x)`
- `getState()` → `{ready,spine,bones,slots,animations[],current,time,duration,meshes[],debug,hasTexture}`
- `getMeshData(slot,name)` → `{vertices,uvs,triangles,hull,verts,weighted}`（setup 原始資料）
- `getWorldVertices(slot,name)` → `[x,y,...]` **變形後世界座標**（內部先同步 re-pose）
- `getMeshBounds(slot,name)` → `{minX,minY,maxX,maxY,w,h}` **變形後世界包圍盒**（量化驗收指標）
- `setMeshVertices(slot,name,arr)` → 改 mesh 頂點 + 重建，回 bool
- `getSkeletonJSON()` / `applySkeletonJSON(obj)` → 取/換整份 JSON + 重建
- `selectAttachment(slot,name)` / `showVertices(bool)` / `setDebug({drawBones,drawMeshTriangles,drawMeshHull,drawRegionAttachments,drawClipping})`
- `setShowTexture(bool)` / `setPremultipliedAlpha(bool)` / `fit()`
- `screenshot()` → PNG dataURL（canvas 已開 preserveDrawingBuffer）
- `loadReference(dataURL)` / `setReferenceOpacity(0..1)` 目標疊圖比對

**自主驗收範式**：編輯(`applySkeletonJSON`/`setMeshVertices`) → 設姿勢(`setAnimation`/`setTime`) → 量化(`getWorldVertices`/`getMeshBounds`) + 視覺(`screenshot`) → 對照目標(`loadReference`)。

## 5. Spine 3.8 技術雷點（完整）

1. **命名空間**：WebGL 在 `spine.webgl.*`（SceneRenderer/GLTexture/AssetManager/ManagedWebGLRenderingContext）；核心在 `spine.*`（Skeleton/SkeletonJson/TextureAtlas/AtlasAttachmentLoader/Vector2/MixBlend/MixDirection）。
2. **setup attachment 多為 null**：靠動畫 attachment timeline 控制顯示。`skeleton.getAttachment(slotIndex, name)` 會 fallback 到 defaultSkin；`slot.data.attachmentName` 可能是 null（別直接餵給 getAttachment，會丟 "attachmentName cannot be null")。
3. **deform 受 attachment gating**：DeformTimeline 只在 slot 當前 attachment == timeline attachment 時套用。
4. **取變形後座標的正確步驟**：`setToSetupPose()` → `anim.apply(skel,0,time,true,[],1,spine.MixBlend.setup,spine.MixDirection.mixIn)` → `updateWorldTransform()` → `att.computeWorldVertices(slot,0,att.worldVerticesLength||uvs.length,out,0,2)`。**這是同步的**；別依賴 render loop 的非同步 pose（會讀到上一幀舊姿勢）。
5. **PMA**：對齊 Cocos `Premultiplied Alpha`。`gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, pma)`（建貼圖前）要與 `drawSkeleton(skeleton, pma)` 一致，否則發光/半透明區糊成死亮色。
6. **weighted mesh**：判定 `vertices.length !== uvs.length`。weighted 格式 `[骨數, idx,bindX,bindY,weight, ...]` 攤平；hull 頂點排最前；bind 是 setup 下相對骨座標；權重每頂點和=1。
7. **緊湊 bezier**：`{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}` 散鍵；`"stepped"`/`"linear"` 特例。
8. **SceneRenderer 用法**：`new spine.webgl.SceneRenderer(canvas, gl)`；每幀 `gl.viewport` + `renderer.camera.viewportWidth/Height/position` 設好 → `begin()` → `drawSkeleton(skel,pma)` (需貼圖) → `drawSkeletonDebug(skel,pma,[])` (線框,旗標在 `renderer.skeletonDebugRenderer`) → `end()`。OrthoCamera viewport = 顯示的世界寬高，置中於 position。
9. **工具產檔**：data: URL 不能 navigate（被拒）；超長 Write/Edit 內容會被截斷 → 大檔用 bash+python 組裝。`document.open/write` 會清掉瀏覽器 extension 的 content script（自動化會失聯）。

## 6. 兩次遞迴的結果（已驗證）

**遞迴 1｜頂點級檢視 + 世界座標 API**（AC 全過）：加 `getWorldVertices` + 頂點編號疊圖。驗證：21 點顯示、API 回 21 點、跨時間座標差 138。**抓到並修掉**：2D 疊圖 canvas 遮住 GL 畫布（→ 改 HTML div 標籤）、setTime 後讀舊姿勢（→ 同步 re-pose）、getAttachment 為 null（→ 從 skin 取）。

**遞迴 2｜編輯→量化驗證迴圈**：加 `setMeshVertices` + `getMeshBounds` + force-show。驗證：AC1 編輯 round-trip（頂點 5→65 保留）✓；AC2 包圍盒隨時間 507×574→645×616 ✓；AC3 force-show 在「動畫主動隱藏該 mesh 的極端時點」仍渲染不出（受 clipping/deform 長度交互）——**已知限制**，不影響一般檢視（正常渲染無 regression，18539 px 確認）。

## 7. 自主工作流 SOP（摘要）

六階段：Intake → **Acceptance Spec(驗收契約)** → Decompose → **Build-Verify Loop(自我驗證,核心)** → Escalation → Review → Delivery。驗證閉環在 AI 端（render→截圖→對照→評分→調整）。介入只三種：開頭定契約、無法自決岔路、里程碑。自主程度旋鈕 L1/L2/L3（預設 L2）。完整見 `自主Spine工作流_SOP.md`。

## 8. 能力鍛鍊計畫（摘要）

**反推框架**：分析影片運動 → 反推 ①拆件(運動分割) ②遮擋補圖(重疊×位移) ③骨架(關節/pivot) ④mesh(剛性 vs 非剛性) 的需求規格。產出 Asset & Rig Requirement Spec。

**鍛鍊 = 程序 + 工具 + 評估器 + 知識庫 + benchmark**；評估器是樞紐（能自評才能自主迭代）。別 ML「無唯一解的美術決定」（SpriteToMesh 證明神經網路預測頂點不收斂），改用確定性演算法 + 評估器。

**S1–S5 路線**（依槓桿）：S1 反推分析器 → S2 評估器套件 → S3 mesh 生成器(純 CPU 可全自動：cv2.findContours+多通道 Canny+Delaunay+BBW 權重+SkelToJson) → S4 切圖(PSD-first/psd-tools)+補圖(分級:邊緣外擴→cv2.inpaint→LaMa→GPU/人工) → S5 骨架半自動(人形 RTMPose/MediaPipe；非人形 Farneback 光流+運動分群)。

**唯一卡死**：骨架放哪（pivot）仍需人/半自動。**最大策略槓桿**：要到分層 PSD（無 GPU 平面圖自動拆件+補繪基本做不到）。完整含來源見 `Spine能力鍛鍊計畫.md`。

## 9. 建議的排程 routines（第二/三步接續）

- 用 `slot-game-research` skill 每日產出 slot 產品分析（已可）。
- S3 mesh 生成器原型：純 CPU、收益最大、能立刻拆掉「新建 mesh 需 Spine editor」限制 —— 建議第一個動手做的能力。
- 每輪能力開發都套 SOP：先定 AC，用 spineInspector 的 `getWorldVertices/getMeshBounds/screenshot` 自我驗收。

## 10. 開放項 / R3 候選

- force-show 在 clipping/動畫隱藏時點徹底做對。
- 「deform 位移向量疊圖」（每頂點 setup→current 連線，做新表情最直觀）。
- 貼圖/PMA 視覺驗證需 `main_draw.png`（使用者端）。
- mesh 生成器（S3）落地。
