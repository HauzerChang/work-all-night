# S2 補圖閘 — 真實遮擋自監督 benchmark 校準

- **結論**:`evaluate_inpaint.py` 完成。GT-free 三準則(破洞/局部化接縫/Laplacian 紋理)+
  GT 模式(premult MAE)。以 **robot_parts 真實圖層互遮**(右手 10.7%/頭 12.9%/身體 3.2%/光暈 72.3%
  被上層蓋住,而美術圖層**畫全** → 天然自監督真值)校準:**正對照(GT)4 件全過、
  三種負對照(黑洞/平色/噪聲)GT-free 全抓到**,CALIBRATION PASS。
- **信心**:高(真實生產美術 + 正負對照分離度實測;閾值非拍腦袋)。
- **階段**:第 2 階段 / S2(補圖閘,S2 四閘之三;剩骨架閘同日完成)。
- **工具**:`tools/mesh_gen/evaluate_inpaint.py`(`--bench` 一鍵重現)。

## 準則設計(兩次迭代後的定版與理由)

| AC | 測量 | 抓什麼 | 閾值(校準值) |
|---|---|---|---|
| AC1_hole | closure(alpha) 內卻 alpha=0 的洞區比率 | 沒補(黑洞=1.0) | ≤0.02 |
| AC2_seam | **局部化接縫比**:邊界線(±1px)梯度 / 緊鄰兩側(2~4px)梯度 | 接縫(平色 2.3~3.8) | ≤2.0(GT max 1.87) |
| AC3_texture | 洞內 **Laplacian** / 遠處參考帶,**僅上限** | 亂填(噪聲 ≥1.70) | ≤1.3(GT max 0.93) |
| AC4_fidelity(GT 模式) | 洞區 premult MAE vs 真值 | 補得不像 | ≤12 |

**迭代教訓(第一版兩個 miscalibration,當場被正對照抓出)**:
1. **AC3 下限誤殺平滑內容**:光暈是漸層,洞內梯度天生低(GT tex=0.046)→ 下限會把 GT 判死。
   平色填充改由 AC2 抓 → AC3 只設上限。
2. **seam 用「遠處參考帶」不穩**:身體的洞恰在機械細節區,GT 自己 seam=1.26 與噪聲 1.17 重疊。
   改**局部化**(邊界線 vs 緊鄰兩側):GT 的邊界只是內容中任意一條線 → ≈1;
   平色填充的截斷筆觸在邊界形成梯度脊 → 2.3~3.8,**無真值也抓得到平色填充**(意外收穫)。
3. **Sobel 分不開噪聲與密集細節**(1.07 vs 1.10),**Laplacian 分得開**(0.93 vs 1.70):
   自然筆觸是線狀、iid 噪聲是斑點,二階導對斑點遠更敏感。

## cv2 級補繪的實測定位(降階鏈證據)

| 件 | telea MAE | 判定 |
|---|---|---|
| 光暈(平滑) | 10.0 | ✅ cv2 級夠用 |
| 身體(3.2% 遮擋) | 20.5 | ❌ 需升級 |
| 頭(12.9%) | 24.2 | ❌ 需升級 |
| 右手(10.7%) | 31.4 | ❌ 需升級 |

→ 量化證實計畫的補圖降階鏈:**cv2 只夠平滑區/小洞;細節區大洞要 LaMa/GPU/人工**。
閘的 fid_tol=12 正確編碼這個分界。另 cv2 對 alpha 通道的重建也不完美(右手 ns 殘洞 2%,AC1 邊緣抓到)。

## 已知局限
- GT-free 模式 = **災難閘**(破洞/硬接縫/亂填);「補得像不像」需 GT(benchmark)或人眼。
  平滑區的平色填充 GT-free 抓不到 —— 但那本來就是降階鏈 level-0 的合法手段。
- 閾值校準自 robot_parts(單一美術風格);換風格資產建議先跑 `--bench` 式正負對照再信。

## 可重現
```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 先切件
python3 tools/mesh_gen/evaluate_inpaint.py --bench                                # 24 列校準表
python3 tools/mesh_gen/evaluate_inpaint.py --cand X.png --hole M.png [--gt G.png] # 生產用
```
