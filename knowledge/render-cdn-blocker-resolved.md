# spine_inspector CDN blocker — 以純 CPU 渲染器解決(離線實機驗證)

- **階段**:S2 評估器套件 / 工具基礎建設。
- **信心**:高(setup round-trip MAE 2.7/0.66 ≈ 重現原圖;deform 渲染目視無撕裂)。

## Blocker 背景

排程環境網路政策**擋 jsDelivr / esotericsoftware(403 policy denial)**,spine_inspector.html 的
spine-webgl 3.8 runtime 載不進來。查證:
- jsDelivr、esotericsoftware、GitHub raw 皆 403(代理 noProxy 清單不含)。
- npm registry 可達,但只有 `@esotericsoftware/spine-webgl` **4.x**(與 3.8.99 資產不相容,無 3.8.x)。
- 故「線上載 3.8 runtime」在現網路政策下不可行。

## 解法:純 CPU 貼圖網格渲染器(`tools/mesh_gen/render_mesh.py`)

實機 round-trip 的**真正需求**是「把貼圖依 mesh 貼出來、套 deform 看會不會撕裂」——
這不需要瀏覽器或 spine runtime。逐三角形 UV→頂點仿射映射(cv2.warpAffine + 三角遮罩合成):
- `setup_px(mesh)`:setup 頂點像素座標;`render()` 渲染。
- `deformed_px(mesh, sk, slot, name)`:套真實位移場後渲染(撕裂檢查)。
- **round-trip 正確性**:setup 渲染 vs 原貼圖 MAE(curtain_left 2.67、shadow 0.66,滿分 255)≈ 完全重現。

優點:**離線、純 CPU、可自動化**,排程環境直接能跑;比依賴 CDN+瀏覽器更穩健,
正好補上 deform 閘的「視覺」面(deform 閘給數字、渲染器給圖)。

## 仍開放(若要互動式 HTML 工具離線可用)

`spine_inspector.html` 本身仍需 spine-webgl 3.8 runtime。要讓它離線可用,只有兩條(屬使用者層級):
1. **提供 spine-webgl 3.8 JS 檔**(像 main_draw.png 那樣 commit 進 repo)→ 改 html 載本地檔 vendor。
2. **放寬排程環境網路政策**,把 `cdn.jsdelivr.net` 加入 Allowed domains。

> 對「自動化驗證 pipeline」而言不需要上述任一條——`render_mesh.py` 已涵蓋。互動式 HTML 是人用的加值。
