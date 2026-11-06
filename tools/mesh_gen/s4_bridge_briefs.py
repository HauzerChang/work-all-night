#!/usr/bin/env python3
"""S4 chunk 306:產生 Codex bridge 任務單(一圖一 .md,依 codex-bridge 協定)+ 每件需補區遮罩。
協定(skill codex-bridge):首行 `images: ref/..`(相對 bridge 根目錄),結尾 `Save the result as \`out/<id>_filled.png\``,
bridge 會固定叫 Codex 讀 briefs/00_style.md → 任務單明寫不適用。
需補區 = 件被遮擋件覆蓋處(已含遮擋件顏色污染)∪ 件輪廓外 R px 內、落在遮擋件下的延伸帶(外推)。
輸出 s4_data/chunk60/bridge/{briefs/todo,ref}/;使用者用 s4_bridge_sync.py 搬到本機 bridge。"""
import json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import inpaint_eval as ie

D = os.path.join(os.path.dirname(__file__), "s4_data/chunk60")
CUT = os.path.join(D, "cut_sam"); B = os.path.join(D, "bridge")
TODO = os.path.join(B, "briefs/todo"); REF = os.path.join(B, "ref")
for p in (TODO, REF): os.makedirs(p, exist_ok=True)

# (part, 遮擋件, 外推帶 px, 材質描述, 類別)
TASKS = [
 ("tails_mass", ["sleeve_left", "sash_train", "hand_left"], 6,
  "蓬鬆的白色狐尾毛,尾端漸層粉紅;毛流方向沿尾巴走向,邊緣是柔軟的毛絮(alpha 漸弱)", "1b 寬鬆閘:動態下不露洞即可"),
 ("skirt", ["belt", "sash_train", "hand_left", "hand_right", "tag_pendant"], 14,
  "深紅色絲質短裙,帶金色暗紋與金邊;布料順著垂墜方向", "1b"),
 ("head", ["hair_front_left", "hair_front_right", "earrings", "choker"], 14,
  "臉頰兩側皮膚與頸部;前髮束下方應是臉側/耳朵/頸側皮膚,脖子底部延伸到頸鏈下方", "1b"),
 ("sleeve_left", ["hand_left"], 14,
  "半透明白紗廣袖,袖口有紅色細繩與金線滾邊;手遮住處應延續紗袖的透明質感與袖口線條", "1b"),
 ("leg_left", ["boot_left", "boot_right", "skirt", "sash_train"], 12,
  "大腿皮膚(淡粉膚色、柔和陰影);靴口上方與裙擺下方的皮膚延伸", "1b"),
 ("leg_right", ["boot_left", "boot_right", "skirt", "sash_train"], 12,
  "大腿皮膚(淡粉膚色、柔和陰影);靴口上方與裙擺下方的皮膚延伸", "1b"),
]
man = json.load(open(os.path.join(CUT, "manifest.json")))
W, H = man["size"]; L = {}
for p in man["parts"]:
    im = ie.load_rgba(os.path.join(CUT, p["file"]))
    f = np.zeros((H, W, 4)); ox, oy = p["offset"]; h, w = im.shape[:2]
    f[oy:oy+h, ox:ox+w] = im; L[p["id"]] = (f, p["file"])
k = lambda n: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))
comp = cv2.imread(os.path.join(CUT, "composite.png")); cv2.imwrite(os.path.join(REF, "composite.png"), comp)
summary = []
for i, (pid, occs, R, mat, cat) in enumerate(TASKS, 1):
    f, fn = L[pid]; a = f[..., 3] > 128
    occ = np.zeros((H, W), bool)
    for o in occs: occ |= L[o][0][..., 3] > 128
    band = cv2.dilate(a.astype(np.uint8), k(2*R+1)).astype(bool)
    band = cv2.morphologyEx(band.astype(np.uint8), cv2.MORPH_CLOSE, k(9)).astype(bool)
    hole = (band & occ) | (a & occ)
    hole = cv2.morphologyEx(hole.astype(np.uint8), cv2.MORPH_OPEN, k(3)).astype(bool)
    n = int(hole.sum())
    # 遮罩 PNG:白=需補、黑=保留(與件同 460x898 全圖座標)
    cv2.imwrite(os.path.join(REF, f"{pid}_mask.png"), (hole * 255).astype(np.uint8))
    ie.save_rgba(os.path.join(REF, f"{pid}.png"), f)
    # 預覽:件 + 紅色半透明遮罩,給 Codex 與人看
    pv = comp.copy(); pv[hole] = (pv[hole] * 0.4 + np.array([0, 0, 255]) * 0.6).astype(np.uint8)
    cv2.imwrite(os.path.join(REF, f"{pid}_preview.png"), pv)
    ys, xs = np.where(hole); bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if n else None
    brief = f"""images: ref/{pid}.png,ref/{pid}_mask.png,ref/{pid}_preview.png,ref/composite.png

# 任務 {i:02d}:補圖 `{pid}`(Spine 2D 角色部件,{cat})

**briefs/00_style.md 不適用本任務,請忽略。**

## 輸入
- `ref/{pid}.png`:要補的部件,RGBA PNG,{W}x{H},透明背景。這是從整張角色圖 `ref/composite.png` 切出的「{pid}」。
- `ref/{pid}_mask.png`:需補區遮罩(白=需要重繪,黑=必須原樣保留),{n} px,範圍約 x{bbox[0]}–{bbox[2]} / y{bbox[1]}–{bbox[3]}。
- `ref/{pid}_preview.png`:整張圖上用紅色標出需補區,幫你理解該區在角色上的位置。

## 要做什麼
角色動起來時,這個部件被 {"、".join(occs)} 擋住的區域會露出來。請在**遮罩白色區**畫出這個部件在被遮處「本來應該有」的樣子:
- 材質:{mat}。
- 只延續 `{pid}` 本身,**不要**畫進遮擋它的件({"、".join(occs)})的內容。
- 顏色、光影、筆觸要與 `ref/{pid}.png` 既有像素無縫銜接,不留硬邊、不留色塊接縫。
- 部件的外輪廓可以在白色區內自然延伸;白色區之外若本來是透明,就保持透明。

## 硬性要求
1. 輸出 RGBA PNG,尺寸必須是 {W}x{H},座標系與輸入完全相同(不要裁切、不要縮放、不要位移)。
2. **遮罩黑色區的像素(含 alpha)必須與 `ref/{pid}.png` 逐像素相同**;只有白色區可以改。
3. 白色區內補出的像素要有合理 alpha(部件邊緣柔和過渡,不要整塊 255 的硬邊)。
4. 不要加背景、不要加文字、不要改變整體色調。

Save the result as `out/{pid}_filled.png`
"""
    open(os.path.join(TODO, f"{i:02d}_{pid}.md"), "w").write(brief)
    summary.append((pid, n, bbox))
open(os.path.join(B, "README.md"), "w").write("""# Codex bridge 任務包(chunk 306)
由 `s4_bridge_briefs.py` 產生。搬運方式(在你的 Windows 機器上,repo 根目錄):

    python tools/mesh_gen/s4_bridge_sync.py push "C:\\Users\\user\\Desktop\\切圖補圖研究\\bridge"
    # bridge 跑完後(out/ 出現 *_filled.png):
    python tools/mesh_gen/s4_bridge_sync.py pull "C:\\Users\\user\\Desktop\\切圖補圖研究\\bridge"
    git add tools/mesh_gen/s4_data/chunk60/filled && git commit -m "S4: bridge results" && git push

push:複製 `briefs/todo/*.md` → bridge\\briefs\\todo\\,`ref/*` → bridge\\ref\\。
pull:複製 bridge\\out\\*_filled.png → repo `chunk60/filled/`,並帶回 logs 的 run/exit 檔供除錯。
驗收由下次排程執行(`s4_bridge_verify.py`:黑區逐像素不變 + 1b 閘 + 目視蒙太奇)。
""")
json.dump([{"part": p, "hole_px": n, "bbox": b} for p, n, b in summary],
          open(os.path.join(B, "tasks.json"), "w"), ensure_ascii=False, indent=1)
for s in summary: print(s)
