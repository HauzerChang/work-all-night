# CLAUDE.md — Spine 研究與程式化編輯工具

> 給 Claude Code 的專案 context。這個專案把 Spine 2D 角色變成「可程式化編輯、可即時視覺化驗證」的資產。環境：lula slot game / Cocos Creator 3.7.3 / Spine 3.8.99。

> 🔁 **自驅排程模式**：本 repo 設計為跨多個排程 session 自主推進。
> **每次 session 開頭請依序讀 `RULES.md` → `PLAN.md` → `STATE.md`**(操作守則、路線圖、續跑狀態),
> 再依 `prompts/run.md` 推進一個有界工作塊,結束前更新 `STATE.md`/`log/` 並 commit。
> 機制總覽見 `README.md`。

## 三階段目標

1. **可視化檢視/編輯工具**（已完成，見下方 Spine Inspector）。
2. **用工具鍛鍊能力**：切圖、補圖、新增/編輯 mesh、骨架設計 —— 每項都用工具的視覺化＋量化 API 自主驗收。
3. **整合成 pipeline**：從「2D 原圖 → spine 動畫」，最終讓 spine 動畫逼近目標影片。

## 測試資產 main_draw

- `main_draw.json` + `main_draw.atlas`（+ `main_draw.png` 貼圖；png 目前只在使用者端）。一支 slot「開獎」動畫。
- 規模：**28 bones / 40 slots / 1 skin(default) / 9 animations**；attachment 共 74：region×69、**mesh×4**、clipping×1(root)。
- 4 個 mesh 全 **unweighted**：`image/curtain_left`、`image/curtain_right`（各 21 頂點 / 24 三角 / hull 16），`image/shadow`、`image/shadow2`（各 12 / 10 / hull 12，兩 slot 共用同一張 region）。
- mesh 由動畫的 `deform` timeline 變形；窗簾在 9 支動畫全部有 deform。

## Spine Inspector 工具

- 檔案：`spine_inspector.html`（單檔，瀏覽器開啟）。渲染建於官方 **spine-webgl 3.8**（jsDelivr CDN，內建多來源 fallback）。
- 功能：載入 json+atlas(+png) → 顯示 bones 階層樹、slots/attachments（mesh/region/clipping 標籤）、mesh 拓樸線框（三角/hull/骨頭/裁切可切換）、動畫時間軸 scrub、Inspector 細節、編輯 JSON 重建、頂點編號疊圖、參考圖疊圖、PMA 開關。
- 沒 png 也能用（debug 線框模式，最適合看 mesh 拓樸）。
- 載入路徑：拖檔，或 file input；同目錄有 main_draw.* 時（http 服務下）自動載入。

### Phase-2 API（agent 自主驅動與驗收）— `window.spineTool`

```
ready() · loadFromText(json,atlas,pngDataURL|null)
listAnimations() · setAnimation(name) · play() · pause() · setTime(t) · setSpeed(s)
getState()                       → {ready,spine,bones,slots,animations,current,time,duration,meshes,debug,hasTexture}
getMeshData(slot,name)           → {vertices,uvs,triangles,hull,verts,weighted}（setup 原始）
getWorldVertices(slot,name)      → [x,y,...] 變形後世界座標（同步 re-pose 後計算）
getMeshBounds(slot,name)         → {minX,minY,maxX,maxY,w,h} 變形後世界包圍盒（量化指標）
setMeshVertices(slot,name,arr)   → 編輯 mesh 頂點並重建
getSkeletonJSON() · applySkeletonJSON(obj)   → 取/換整份 JSON 並重建
selectAttachment(slot,name) · showVertices(bool) · setDebug({...})
setShowTexture(bool) · setPremultipliedAlpha(bool) · fit()
screenshot()→dataURL · loadReference(dataURL) · setReferenceOpacity(0..1)
```

驗收迴圈範式：`applySkeletonJSON/setMeshVertices` 編輯 → `setAnimation/setTime` 設姿勢 → `getWorldVertices/getMeshBounds` 量化比對 + `screenshot` 視覺確認。

## ⚠️ Spine 3.8 技術雷點（已踩過，務必記住）

1. **命名空間**：WebGL 類別在 `spine.webgl.*`（`SceneRenderer`/`GLTexture`/`AssetManager`/`ManagedWebGLRenderingContext`）；核心在 `spine.*`（`Skeleton`/`SkeletonJson`/`TextureAtlas`/`AtlasAttachmentLoader`/`Vector2`/`MixBlend`/`MixDirection`）。寫成 `spine.SceneRenderer` 會 undefined。
2. **setup attachment 多為 null**：此資產靠動畫的 attachment timeline 控制顯示，setup pose 下很多 mesh/region 不顯示是正常。
3. **deform 受 attachment gating**：`DeformTimeline.apply` 只在「slot 當前 attachment == timeline 的 attachment」時套用。要拿到變形後座標，attachment 必須在 `apply()` 當下 active。
4. **取變形後世界座標**：先同步 `skeleton.setToSetupPose()` → `anim.apply(skel,0,time,true,[],1,spine.MixBlend.setup,spine.MixDirection.mixIn)` → `updateWorldTransform()`，再 `attachment.computeWorldVertices(slot,0,n,wv,0,2)`。`slot.getAttachment()` 為 null 時改 `skeleton.getAttachment(slot.data.index, name)` 從 skin 取。
5. **Premultiplied Alpha**：要對齊 Cocos 的 `Premultiplied Alpha`。建貼圖時 `gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, pma)` 必須與 `drawSkeleton(skeleton, pma)` 的 pma 一致，否則發光/半透明區糊成死亮色。
6. **weighted mesh 判定**：`vertices.length !== uvs.length`（unweighted = 頂點數×2）。weighted 是 `[骨數, boneIdx,bindX,bindY,weight, ...]` 攤平變長格式；**hull 頂點必排在 vertices 最前**；bind 座標是 setup pose 下相對該骨的座標；權重每頂點和為 1。
7. **緊湊 bezier**（3.8 特色）：`{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}` 散鍵，不是 array。`"stepped"`/`"linear"` 為特例。
8. **工具產檔注意**：data: URL 不能拿來 navigate；超長 Write/Edit 內容會被工具截斷 —— 大檔組裝改用 bash+python 寫入。

## 工作流程慣例（自主 SOP）

每個任務：先定**可檢查的驗收目標(AC)** → 實作 → **自我驗證**（截圖／讀世界座標／量包圍盒，不靠肉眼）→ 只在「無法自決的岔路 / 超迭代預算卡關 / 里程碑」找人。自主程度預設 L2。詳見 `自主Spine工作流_SOP.md`。

## 能力路線圖（第二/三步）

反推框架：**分析目標影片的運動 → 反推出 拆件/遮擋補圖/骨架/mesh 的需求規格**（運動決定一切；不是先畫一張圖）。

待建能力（依槓桿排序）：

- **S1 反推分析器**：影片 → Asset & Rig Requirement Spec（最缺的上游，根治「整張未拆圖」）。
- **S2 評估器套件**：四能力各自的自我品質閘（樞紐：沒它無法自主收斂）。
- **S3 mesh 生成器**：SpriteToMesh 式拓樸（findContours+多通道Canny+Delaunay）+ BBW 權重 + SkelToJson 讀寫 —— **純 CPU 可全自動，最大解鎖點**。
- **S4 切圖＋補圖**：PSD-first 契約（psd-tools 純CPU）；補圖分級降階（邊緣外擴→OpenCV→LaMa→GPU/人工）。
- **S5 骨架半自動**：人形 RTMPose/MediaPipe，非人形光流+運動分群；pivot 仍需人微調（唯一卡死環節）。

最大策略建議：**能要到分層 PSD 就要**（無 GPU 下平面圖自動拆件+補繪基本做不到；PSD 讓整條 CPU pipeline 通）。詳見 `Spine能力鍛鍊計畫.md`。

## 同目錄參考文件

- `handoff_brief.md` —— 完整交接（API 全參考、兩次遞迴結果、SOP/計畫摘要、建議 routines）
- `main_draw_解析報告.md` · `自主Spine工作流_SOP.md` · `Spine能力鍛鍊計畫.md`
- `spine_inspector.html` —— 工具本體

## 待續 / 開放項

- R3 候選：把 force-show 在「動畫隱藏該 mesh / clipping」時點徹底做對；或加「deform 位移向量疊圖」（做新表情最直觀）。
- 貼圖（PMA）相關視覺需 `main_draw.png`（在使用者端）才能完整驗。
- 後續以排程 routines 接續 S1→S5。
