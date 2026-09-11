#!/usr/bin/env python3
"""把 spine-motion-skill 打包成可上傳 Cowork 的 `.skill`(zip),並把本 repo 的軌跡工具鏈併進去。

產出佈局(刻意讓 scripts/motion/ 對編輯器的相對路徑與 repo 的 tools/motion/ 相同,
兩種佈局共用同一份程式碼、不必改路徑):

    spine-motion-skill/
      SKILL.md                       ← 原版 + 本次新增的「軌跡工具鏈」章節(additive)
      spine_trajectory_editor.html   ← 單檔零相依編輯器
      scripts/                       ← 原版參考實作(不動)
      scripts/motion/                ← 本 repo tools/motion/ 全套 + spine_anim(曲線內插,自 analyzer 收錄)

用法:
    python3 tools/motion/package_skill.py --base <原版 .skill 或已解壓目錄> --out dist/
    python3 tools/motion/package_skill.py            # 用 --base 預設搜尋路徑
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SKILL_DIRNAME = "spine-motion-skill"

MOTION_FILES = ["spine_world.py", "analyze_trajectory.py", "motion_spec.py", "apply_motion_spec.py",
                "verify_motion.py", "validate_motion_tools.py", "shot_editor.py",
                "js_core_probe.js", "bridge_harness.html", "README.md", "skill_snippet.md"]

# 從 tools/analyzer/spine_anim.py 收錄曲線內插(唯一真相來源),避免套件內另抄一份而漂移
SHIM_HEADER = '''"""曲線內插(緊湊 bezier / stepped / linear)— 自本專案 `tools/analyzer/spine_anim.py`
**原樣收錄**,供 skill 套件離線使用。請勿手改:要改請改 repo 的來源檔再重新打包
(`python3 tools/motion/package_skill.py`)。
"""
'''


def extract_funcs(src_path, names):
    """從 .py 取出指定的 top-level function 原始碼(含 docstring)。"""
    src = open(src_path, encoding="utf-8").read()
    out = []
    for n in names:
        m = re.search(rf"^def {re.escape(n)}\(.*?(?=^\S|\Z)", src, re.S | re.M)
        if not m:
            raise SystemExit(f"在 {src_path} 找不到 def {n}")
        out.append(m.group(0).rstrip() + "\n")
    return "\n\n".join(out)


def find_base(explicit):
    cands = [explicit] if explicit else []
    cands += [
        os.path.join(ROOT, "skills", SKILL_DIRNAME),
        os.path.expanduser("~/.claude/uploads"),
    ]
    for c in cands:
        if not c or not os.path.exists(c):
            continue
        if os.path.isdir(c):
            if os.path.exists(os.path.join(c, "SKILL.md")):
                return ("dir", c)
            # 目錄下找 .skill
            for dp, _, fns in os.walk(c):
                for fn in fns:
                    if fn.endswith(".skill") and "spinemotion" in fn.replace("-", "").replace("_", "").lower():
                        return ("zip", os.path.join(dp, fn))
        elif c.endswith(".skill") or c.endswith(".zip"):
            return ("zip", c)
    raise SystemExit("找不到原版 skill;請用 --base 指定 .skill 檔或已解壓的 spine-motion-skill 目錄")


NEW_SECTION = """
## 軌跡工具鏈：分析 → 曲線編輯 → 回寫驗證（v1.1 新增）

本節把上面第 2–6 步（世界座標取樣 → 分離自身位移 → 量化 → 設計新 timeline → 寫入驗證）工具化，
不必每次重寫腳本；**規則一條都沒放寬**：仍然分析先於修改、只動目標骨骼的 timeline、原版另存供 A/B，
差別是「寫檔前的驗證清單」與「幅度／時間差分開調」由程式強制執行，未全過就不寫檔。

```
scripts/motion/analyze_trajectory.py     spine_trajectory_editor.html        scripts/motion/apply_motion_spec.py
      Spine JSON ──► traj.json ──► 拖曲線 / 加刪點 / 延後 L / 幅度 ──► spec.json ──► 新動畫 + V1–V7 / Q1–Q3
```

```bash
# 1) 分析（目標=次級部位骨骼，主體=帶動它的骨骼＝節拍來源）
python3 scripts/motion/analyze_trajectory.py --json <Main.json> --anim <動畫> \\
    --bone <目標骨骼> --body <主體骨骼> --out _spine_analysis/traj.json --csv _spine_analysis/07_對照表.csv

# 2) 編輯（瀏覽器開 spine_trajectory_editor.html，載入 traj.json 或直接載 Main.json）
#    拖藍點改幅度與時間、雙擊加點、Del 刪點；右側旋鈕調延後 L / 幅度 / 各軸幅度。
#    量化面板即時顯示「前 → 後」的幅度、own↔主體相關、相位與**互補的代價**。按「下載 motion spec」。

# 3) 套回 + 驗證（未全過不寫檔）
python3 scripts/motion/apply_motion_spec.py --spec _spine_analysis/<新動畫>.spec.json --write
```

編輯器是**單檔、零外部相依**（不吃 CDN），畫面上的預測經實測與 Spine 裡的結果一致到
0.113px（父體有 scale 動畫）／0.0001px（無縮放）——所以在圖上調到滿意就是最終結果，
不必「改完再產一次圖看」。

### motion spec 契約（`spine-motion-spec/1`）

| 欄位 | 意義 |
|---|---|
| `source` | 來源 JSON / 動畫 / fps / 總長 / 幀數 |
| `target.bone` `target.point` | 目標骨骼與**追蹤點**（見下方「追蹤點」雷點） |
| `body.bone` `body.beats` `body.periodFrames` | 主體骨骼、節拍幀、擺動週期（算相位用） |
| `edit.keys` | **世界座標**的自身位移關鍵幀 `{frame, wx, wy, curve}`（curve = 3.8 緊湊散鍵 /`"stepped"`/ 省略＝線性） |
| `edit.lag` `edit.scale` `edit.scaleX` `edit.scaleY` | 四個旋鈕：延後幀數、整體幅度、各軸幅度（以震盪中心縮放，靜止偏移不變） |
| `edit.resolvedKeys` | 套完旋鈕、處理完迴圈邊界後的關鍵幀（工具已算好） |
| `predicted` | 編輯器預測的世界軌跡（Q1 拿它與實測比，證明「畫的」==「做出來的」） |
| `metrics.before/after` | 幅度、相關、相位的前後對照，可直接抄進回覆 |
| `skill.notes` | 要主動告知使用者的副作用（例如互補導致世界總幅縮小） |

拿到 spec 就知道使用者要調什麼、預期變成怎樣、怎麼驗；不必再從對話裡猜參數。

### 驗證清單（`apply_motion_spec.py` 寫檔前一定跑）

V1 總長不變 · V2 有差異的骨骼只有目標骨骼 · V3 slot timeline 未動 · V4 原動畫未被碰 ·
V5 skins（權重／attachment）未被碰 · V6 其他動畫未被碰 · V7 所有 keyframe 時間 ≤ **原**總長 ·
Q1 世界軌跡 vs 編輯器預測 · Q2 實測自身位移 vs 設計值 · Q3 滯後幀／相關／峰對峰幅度（前 → 後）。

### 三個踩過的坑（比工具本身重要）

1. **`own = actual − rigid` 不夠，要拆三塊。** 對追蹤點 p：`actual = rigid + rotOwn + transOwn`
   （Spine bone local 是 T·R·S，translate 造成的世界位移與 rotate 無關，三者精確可加，實測殘差 <1e-13px）。
   `rigid`＝目標骨骼所有通道歸零後被主體帶著走的運動；`rotOwn`＝自轉帶動 p；`transOwn`＝translate 造成。
   **只有 `transOwn` 能無損寫回 translate 關鍵值**——拿總量回寫會把 rotate 的貢獻重複計入
   （實測 round-trip 後 X 幅度剛好變兩倍，只有做 round-trip 才抓得到）。
2. **追蹤點預設不能用骨骼原點。** rotate-only 的配件（鈴鐺、耳環）骨骼原點在自轉下完全不動，
   追原點會把跟隨運動量成 0。預設取該骨骼 slot 的 attachment 中心（`--point auto`），spec 會記下它，
   分析／驗證用同一點。
3. **延後前要先移除 loop 尾端的重複 key。** 慣例上 `frame=總長` 的 key 是 `frame=0` 的循環複製，
   延後後兩者取模撞在同一幀，去重會留下錯的曲線（症狀：曲線莫名變線性）。移除後再做 de Casteljau
   邊界切分，實測「延後 L 幀 == 原曲線循環平移 L 幀」誤差 7e-13（任意 L，含非整數）。

### 自我驗收

```bash
python3 scripts/motion/validate_motion_tools.py --json <Main.json> --anim <動畫> \\
    --bone <目標骨骼> --body <主體骨骼>          # 需要 playwright 才跑 A7/A8，否則加 --no-browser
```

A1 三分解可加性 · A2 無損 round-trip · A3 延後 L 幀 · A4 幅度縮放 · A5 負對照（V2/V4/V5/V7 各要抓得到）
· A6 JS↔Python parity · A7 無頭瀏覽器端到端 · A8 viewer 橋接契約。
對兩個真實資產（main_draw、Award）全 PASS。

### 界線（要對使用者說清楚）

- **世界↔local 內插殘差**：關鍵值換算精確（round-trip local 關鍵值誤差 0），但關鍵幀**之間**
  Spine 在 local 內插、編輯器在世界內插；父體有 scale／rotate 動畫時有殘差（實測 0.12px）。要更緊就加密關鍵幀。
- **只動 translate**（rotate 通道 spec 與套用器已支援，UI 尚未接）；mesh／權重／deform／attachment 不碰。
- **靜態擺位不是曲線**：目標的 translate 只有 1 個 key（美術用動畫通道擺件）時沒有可調曲線，
  分析器會警告、旋鈕對它無效——要做跟隨動態得先沿主體節拍加關鍵幀。
- **viewer 即時預覽**（`spine_inspector.html` 的 `openTrajectoryEditor()` / `spine-motion/preview`）
  只驗到 postMessage 契約；畫面真的動起來需在有 spine-webgl（CDN 可達）的環境確認。
- transform 繼承只精確支援 `normal` / `onlyTranslation`，其餘以 normal 近似並列入 warnings。
"""

EXTRA_PITFALLS = """- 真實匯出檔的**第一個 key 會省略 `time`**（＝0），`curve` 也可能省略 `c2/c3/c4`（缺省 0/1/1）——
  自寫取樣器若直接 `k["time"]`／`k["c2"]` 會 KeyError。
- 「keyframe 時間 ≤ 總長」這條檢查要以**原動畫**總長為準：拿新動畫總長比，新加的長 key 會自己把
  總長撐大，檢查變成恆真（動畫被撐長、主體末尾凍結正是退件原因）。
- loop timeline 尾端 `frame=總長` 的 key 是 `frame=0` 的複製，重定時前要先移除（見軌跡工具鏈章節）。
"""


def build(base_kind, base_path, out_dir, version):
    tmp = tempfile.mkdtemp(prefix="skillpkg-")
    pkg = os.path.join(tmp, SKILL_DIRNAME)
    if base_kind == "zip":
        with zipfile.ZipFile(base_path) as z:
            z.extractall(tmp)
        inner = os.path.join(tmp, SKILL_DIRNAME)
        if not os.path.exists(inner):
            raise SystemExit(f"{base_path} 內沒有 {SKILL_DIRNAME}/")
    else:
        shutil.copytree(base_path, pkg)

    # --- SKILL.md:additive 更新 ---
    sp = os.path.join(pkg, "SKILL.md")
    md = open(sp, encoding="utf-8").read()
    if "軌跡工具鏈" in md:
        print("SKILL.md 已含軌跡工具鏈章節 → 只更新內容")
        md = md[:md.index("\n## 軌跡工具鏈")]
    # description 補觸發詞
    md = md.replace(
        "分析先於修改、只動時間軸、主體逐 byte 不變是本 skill 的底線。",
        "也涵蓋軌跡工具鏈（軌跡圖表編輯器、motion spec、寫檔前驗證清單）：使用者說「軌跡工具」"
        "「調曲線」「軌跡編輯器」「motion spec」「少來回試錯」時同樣適用。"
        "分析先於修改、只動時間軸、主體逐 byte 不變是本 skill 的底線。", 1)
    # 標準流程指路
    md = md.replace(
        "- 參考實作在本 skill 的 `scripts/`",
        "- **軌跡工具鏈(建議優先用)**:`scripts/motion/` + `spine_trajectory_editor.html`,\n"
        "  把第 2–6 步變成「分析一次 → 網頁上調曲線 → 一行指令套回並自動驗證」,見末節「軌跡工具鏈」。\n"
        "- 參考實作在本 skill 的 `scripts/`", 1)
    # 踩雷清單補三條(原文用全形逗號,故以行首比對而非整行字串)
    m = re.search(r"^- atlas `rotate: true`.*$", md, re.M)
    if m and "第一個 key 會省略" not in md:
        md = md[:m.end()] + "\n" + EXTRA_PITFALLS.strip() + md[m.end():]
    else:
        print("⚠ 未找到踩雷清單錨點(或已補過),跳過")
    md = md.rstrip() + "\n" + NEW_SECTION
    open(sp, "w", encoding="utf-8").write(md)

    # --- 編輯器 ---
    shutil.copy2(os.path.join(ROOT, "spine_trajectory_editor.html"), pkg)

    # --- scripts/motion/ ---
    mdir = os.path.join(pkg, "scripts", "motion")
    os.makedirs(mdir, exist_ok=True)
    for fn in MOTION_FILES:
        shutil.copy2(os.path.join(HERE, fn), mdir)
    # 文件裡的 repo 路徑改寫成套件內路徑(程式碼不改,靠相對路徑相同來相容)
    for fn in ("README.md", "skill_snippet.md"):
        fp = os.path.join(mdir, fn)
        t = open(fp, encoding="utf-8").read()
        t = t.replace("tools/motion/", "scripts/motion/")
        t = t.replace("assets/main_draw.json", "<Main.json>")
        t = t.replace("# tools/motion — ", "# scripts/motion — ")
        open(fp, "w", encoding="utf-8").write(t)
    # 曲線內插:自 analyzer 原樣收錄
    shim = SHIM_HEADER + "\nimport math\n\n\n" + extract_funcs(
        os.path.join(ROOT, "tools", "analyzer", "spine_anim.py"), ["_bezier_y", "_interp"])
    open(os.path.join(mdir, "spine_anim.py"), "w", encoding="utf-8").write(shim)

    # --- 打包 ---
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"spine-motion-skill-v{version}.skill")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fns in sorted(os.walk(pkg)):
            for fn in sorted(fns):
                full = os.path.join(dp, fn)
                z.write(full, os.path.relpath(full, tmp))
    names = zipfile.ZipFile(out).namelist()
    print(f"已打包 {out}（{len(names)} 個檔案, {os.path.getsize(out)/1024:.0f} KB）")
    for n in names:
        print("  ", n)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="原版 .skill 檔或已解壓的 spine-motion-skill 目錄")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--version", default="1.1")
    a = ap.parse_args()
    kind, path = find_base(a.base)
    print(f"基底:{path}（{kind}）")
    build(kind, path, a.out, a.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
