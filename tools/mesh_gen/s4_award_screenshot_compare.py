#!/usr/bin/env python3
"""候選16路徑(b):把補圖結果貼回真實 Award atlas 貼圖,用 headless spine-webgl
在真實動畫時間軸上截圖,跟未補版本比對——回答「動態動畫尺度下會不會穿幫」
(見 STATE_S4.md / knowledge/s4-inpaint-1b-lenient-gate.md 候選16、候選20)。

流程:
  1. 用 atlas_crop 從 assets/Award.png 切出目標 slot 的 atlas-解析度 region(不是 PSD 解析度——
     這才是實際渲染時用的貼圖,見 knowledge/s4-psd-to-spine-real.md 的 0.70 縮放發現)。
  2. inpaint_eval.punch_hole 挖合成洞、score_candidates+select_best 用 1b 盲選(真實情境沒有
     gt 可用 1a 選,呼應既有 psd_inplace_patch.py --auto 的鏈路)。
  3. atlas_patch 把選中的補丁貼回一份 Award.png 副本(只動這一個 region 的像素)。
  4. 組一個可被本機 http.server 服務的 scratch 目錄:orig/、patched/ 兩份完整 json+atlas+雙頁 png,
     外加一份用 curl 抓好的 spine-webgl.js(見下方 VENDOR)與本檔同目錄的
     s4_spine_render_harness.html(多頁 atlas 正確支援,spine_inspector.html 不支援雙頁,見該檔開頭註解)。
  5. 產生並執行一個 Node/Playwright 腳本:對 orig/patched 兩份場景,在目標 slot 實際出現的
     動畫時間點上分別截「全場景圖」+ 記錄該 slot 的螢幕像素框(worldToScreen 換算,見 harness)。
  6. Python 端用全場景截圖裁出 slot 的實際螢幕框(不額外放大,呈現的就是真實播放時的像素大小)
     算 MAE/SSIM,並把裁出的小圖放大存檔供人眼複查(候選7已知「單看數字」不夠,需要 vision 複查)。

不改動 spine_inspector.html / assets/ 既有檔案(只寫一份 patched Award.png 到 scratch)。
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, textwrap
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inpaint_eval as ie
import atlas_patch as ap
from atlas_crop import parse_atlas, crop_region

VENDOR_URL = "https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/3.8/spine-ts/build/spine-webgl.js"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
NODE_PATH = "/opt/node22/lib/node_modules"
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def bgra_to_rgba(im):
    b, g, r, a = cv2.split(im)
    return cv2.merge([r, g, b, a]).astype(np.float64)


def rgba_to_bgra(im):
    r, g, b, a = cv2.split(np.clip(im, 0, 255).astype(np.uint8))
    return cv2.merge([b, g, r, a])


def ensure_vendor_js(cache_dir):
    path = os.path.join(cache_dir, "spine-webgl.js")
    if os.path.exists(path) and os.path.getsize(path) > 100_000:
        return path
    os.makedirs(cache_dir, exist_ok=True)
    subprocess.run(["curl", "-sS", "-o", path, "--max-time", "30", VENDOR_URL], check=True)
    size = os.path.getsize(path)
    if size < 100_000:
        raise SystemExit(f"spine-webgl.js 下載可疑地小({size} bytes),中止")
    return path


def build_patch(slot_name, atlas_path, png_dir, out_dir, seed, frac):
    """步驟1-3:切atlas解析度region→挖洞→1b盲選補丁→貼回一份 page png。回傳
    (patched_page_path, page_filename, chosen_method, chosen_reason, score, hole_frac_of_content)。"""
    os.makedirs(out_dir, exist_ok=True)
    regions = parse_atlas(atlas_path)
    r = regions[slot_name]
    page = r["page"]
    sheet_bgra = cv2.imread(os.path.join(png_dir, page), cv2.IMREAD_UNCHANGED)
    if sheet_bgra.shape[2] == 3:
        sheet_bgra = cv2.cvtColor(sheet_bgra, cv2.COLOR_BGR2BGRA)
    crop_bgra = crop_region(sheet_bgra, r)
    crop_rgba = bgra_to_rgba(crop_bgra)

    holed, mask = ie.punch_hole(crop_rgba, mode="interior", frac=frac, seed=seed)
    content = crop_rgba[..., 3] > 8
    scored = ie.score_candidates(holed, mask, mode="interior")
    chosen, reason = ie.select_best(scored, applicable=True)
    recon_rgba = scored[chosen]["recon"]

    ie.save_rgba(os.path.join(out_dir, "atlas_res_original.png"), crop_rgba)
    ie.save_rgba(os.path.join(out_dir, "atlas_res_holed.png"), holed)
    ie.save_rgba(os.path.join(out_dir, f"atlas_res_patched_{chosen}.png"), recon_rgba)
    with open(os.path.join(out_dir, "candidates_score.json"), "w", encoding="utf-8") as f:
        json.dump({k: v["score"] for k, v in scored.items()}, f, ensure_ascii=False, indent=1,
                   default=lambda o: bool(o) if isinstance(o, np.bool_) else o)

    recon_bgra = rgba_to_bgra(recon_rgba)
    out_page_path = os.path.join(out_dir, page)
    ap.patch(atlas_path, png_dir, slot_name, recon_bgra, out_page_path)

    hole_frac_of_content = float(mask.sum()) / float(content.sum())
    return out_page_path, page, chosen, reason, scored[chosen]["score"], hole_frac_of_content


def assemble_scene(scratch_root, variant, patched_page_path=None, patched_page_name=None):
    """組一份 orig/ 或 patched/ 完整場景目錄(json+atlas+雙頁png全部複製,只有 patched
    才把其中一頁換成補丁版)。回傳目錄路徑。"""
    d = os.path.join(scratch_root, variant)
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(REPO, "assets", "Award.json"), os.path.join(d, "Award.json"))
    shutil.copy(os.path.join(REPO, "assets", "Award.atlas"), os.path.join(d, "Award.atlas"))
    for pg in ("Award.png", "Award2.png"):
        src = os.path.join(REPO, "assets", pg)
        dst = os.path.join(d, pg)
        if variant == "patched" and pg == patched_page_name:
            shutil.copy(patched_page_path, dst)
        else:
            shutil.copy(src, dst)
    return d


NODE_SCRIPT_TMPL = r"""
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CFG = JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'));

(async () => {
  const browser = await chromium.launch({ executablePath: CFG.chromium, headless: true });
  const page = await browser.newPage({ viewport: { width: CFG.canvasSize, height: CFG.canvasSize } });
  const consoleErrors = [];
  page.on('pageerror', e => consoleErrors.push('pageerror: ' + e.message));
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push('console.error: ' + msg.text()); });

  async function loadVariant(variant) {
    await page.goto(`http://127.0.0.1:${CFG.port}/harness.html`, { waitUntil: 'load' });
    await page.waitForFunction(() => window.harness && window.harness.ready(), { timeout: 15000 });
    if (!(await page.evaluate(() => window.harness.runtimeOk()))) {
      throw new Error('spine runtime 未就緒 (spine.webgl.SceneRenderer 缺失)');
    }
    return page.evaluate(([variant, pma]) => {
      const pageMap = { 'Award.png': `${variant}/Award.png`, 'Award2.png': `${variant}/Award2.png` };
      return window.harness.load(`${variant}/Award.json`, `${variant}/Award.atlas`, pageMap, pma);
    }, [variant, CFG.pma]);
  }

  // Probe pass:用 orig 場景跑過全部取樣時間點,取整個骨架世界包圍盒的聯集,
  // 讓相機框住整段動畫(不只 setup pose),orig/patched 兩邊套同一個框才能公平比較。
  const info0 = await loadVariant('orig');
  let union = null;
  for (const sample of CFG.samples) {
    await page.evaluate((n) => window.harness.setAnimation(n), sample.anim);
    await page.evaluate((t) => window.harness.setTime(t), sample.time);
    const b = await page.evaluate(() => window.harness.getPoseBounds());
    if (!b) continue;
    if (!union) union = { x0: b.x, y0: b.y, x1: b.x + b.w, y1: b.y + b.h };
    else {
      union.x0 = Math.min(union.x0, b.x); union.y0 = Math.min(union.y0, b.y);
      union.x1 = Math.max(union.x1, b.x + b.w); union.y1 = Math.max(union.y1, b.y + b.h);
    }
  }
  if (!union) throw new Error('probe pass 拿不到任何有效 pose bounds');
  const camBox = { ox: union.x0, oy: union.y0, sw: union.x1 - union.x0, sh: union.y1 - union.y0 };

  const results = [];
  for (const variant of ['orig', 'patched']) {
    const info = variant === 'orig' ? info0 : await loadVariant(variant);
    await page.evaluate((c) => window.harness.setCameraFit(c.ox, c.oy, c.sw, c.sh, 1.15), camBox);

    for (const sample of CFG.samples) {
      await page.evaluate((n) => window.harness.setAnimation(n), sample.anim);
      await page.evaluate((t) => window.harness.setTime(t), sample.time);
      const hasAtt = await page.evaluate((s) => window.harness.slotHasAttachment(s), CFG.slot);
      const box = await page.evaluate((args) => window.harness.getScreenBox(args[0], args[1]), [CFG.slot, CFG.attName]);
      await page.evaluate(() => window.harness.render());
      const outName = `${variant}__${sample.anim}__${sample.time}.png`;
      await page.locator('#cv').screenshot({ path: path.join(CFG.outDir, outName) });
      results.push({ variant, anim: sample.anim, time: sample.time, hasAttachment: hasAtt, screenBox: box, file: outName, info });
    }
  }
  fs.writeFileSync(path.join(CFG.outDir, 'render_manifest.json'),
    JSON.stringify({ results, consoleErrors, camBox }, null, 1));
  await browser.close();
  console.log('DONE', results.length, 'shots,', consoleErrors.length, 'console errors');
})().catch(e => { console.error('FATAL', e); process.exit(1); });
"""


def run_playwright(scratch_root, out_dir, port, canvas_size, samples, slot, att_name, pma):
    os.makedirs(out_dir, exist_ok=True)
    cfg = {
        "chromium": CHROMIUM, "port": port, "canvasSize": canvas_size,
        "samples": samples, "slot": slot, "attName": att_name, "pma": pma, "outDir": out_dir,
    }
    cfg_path = os.path.join(scratch_root, "cfg.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    script_path = os.path.join(scratch_root, "render.js")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(NODE_SCRIPT_TMPL)

    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                            cwd=scratch_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import time
        time.sleep(0.6)
        env = dict(os.environ, NODE_PATH=NODE_PATH)
        proc = subprocess.run(["node", script_path, cfg_path], cwd=scratch_root, env=env,
                               capture_output=True, text=True, timeout=180)
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(f"render.js 失敗 (exit {proc.returncode})")
    finally:
        srv.terminate()
        srv.wait(timeout=5)
    with open(os.path.join(out_dir, "render_manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def diff_screenshots(out_dir, manifest, pad_px=6):
    """對每個 (anim,time) 配對 orig/patched 截圖,裁出 slot 的螢幕框(留 pad_px 邊界)算 MAE/SSIM。
    這裡的裁切尺寸就是真實動畫尺度下該 slot 實際佔的螢幕像素數,不額外放大。"""
    by_key = {}
    for r in manifest["results"]:
        key = (r["anim"], r["time"])
        by_key.setdefault(key, {})[r["variant"]] = r
    rows = []
    for key, pair in sorted(by_key.items()):
        if "orig" not in pair or "patched" not in pair:
            continue
        o, p = pair["orig"], pair["patched"]
        if not o["hasAttachment"]:
            rows.append({"anim": key[0], "time": key[1], "skipped": "attachment 未顯示於此時間點"})
            continue
        box = o["screenBox"]
        img_o = cv2.imread(os.path.join(out_dir, o["file"]), cv2.IMREAD_UNCHANGED)
        img_p = cv2.imread(os.path.join(out_dir, p["file"]), cv2.IMREAD_UNCHANGED)
        h, w = img_o.shape[:2]
        x0 = max(0, int(box["x0"]) - pad_px); y0 = max(0, int(box["y0"]) - pad_px)
        x1 = min(w, int(box["x1"]) + pad_px); y1 = min(h, int(box["y1"]) + pad_px)
        crop_o = img_o[y0:y1, x0:x1]
        crop_p = img_p[y0:y1, x0:x1]
        mae = float(np.abs(crop_o.astype(np.float64) - crop_p.astype(np.float64)).mean())
        cv2.imwrite(os.path.join(out_dir, f"crop_orig__{key[0]}__{key[1]}.png"), crop_o)
        cv2.imwrite(os.path.join(out_dir, f"crop_patched__{key[0]}__{key[1]}.png"), crop_p)
        # 放大 6x 版本方便人眼複查細節(候選7教訓:單看數字不夠,見 knowledge 檔)
        up_o = cv2.resize(crop_o, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
        up_p = cv2.resize(crop_p, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(os.path.join(out_dir, f"crop6x_orig__{key[0]}__{key[1]}.png"), up_o)
        cv2.imwrite(os.path.join(out_dir, f"crop6x_patched__{key[0]}__{key[1]}.png"), up_p)
        rows.append({"anim": key[0], "time": key[1], "screen_box_px": [x0, y0, x1, y1],
                     "screen_w": x1 - x0, "screen_h": y1 - y0,
                     "canvas_w": w, "canvas_h": h,
                     "area_frac_of_canvas": ((x1 - x0) * (y1 - y0)) / (w * h),
                     "mae_0_255": mae})
    return rows


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--slot", default="機器人拆件/左手")
    ap_.add_argument("--att-name", default="機器人拆件/左手")
    ap_.add_argument("--seed", type=int, default=0)
    ap_.add_argument("--frac", type=float, default=0.12)
    ap_.add_argument("--canvas-size", type=int, default=900)
    ap_.add_argument("--pma", action="store_true", default=True)
    ap_.add_argument("--port", type=int, default=8791)
    ap_.add_argument("-o", "--out-dir", required=True)
    ap_.add_argument("--samples", default=None,
                      help="JSON 檔路徑,內容 [{anim,time},...];預設用內建的 Award_Legend_In/Loop 關鍵時間點")
    args = ap_.parse_args()

    scratch = tempfile.mkdtemp(prefix="s4_award_render_")
    atlas_path = os.path.join(REPO, "assets", "Award.atlas")
    png_dir = os.path.join(REPO, "assets")

    patch_dir = os.path.join(args.out_dir, "patch")
    patched_page_path, page_name, chosen, reason, score, hole_frac = build_patch(
        args.slot, atlas_path, png_dir, patch_dir, args.seed, args.frac)
    print(f"[1/3] 補丁完成:method={chosen} reason={reason} hole/content={hole_frac:.3f}")
    print(f"      1b score: {score}")

    vendor_js = ensure_vendor_js(os.path.join(tempfile.gettempdir(), "s4_spine_vendor"))
    shutil.copy(vendor_js, os.path.join(scratch, "spine-webgl.js"))
    shutil.copy(os.path.join(HERE, "s4_spine_render_harness.html"), os.path.join(scratch, "harness.html"))
    assemble_scene(scratch, "orig")
    assemble_scene(scratch, "patched", patched_page_path, page_name)
    print(f"[2/3] scratch scene 目錄: {scratch}")

    if args.samples:
        samples = json.load(open(args.samples, encoding="utf-8"))
    else:
        samples = (
            [{"anim": "Award_Legend_In", "time": t} for t in [0.0, 0.233, 0.367, 0.533, 0.6, 0.667]] +
            [{"anim": "Award_Legend_Loop", "time": t} for t in [0.0, 0.133, 0.3, 0.6, 0.85]]
        )

    manifest = run_playwright(scratch, args.out_dir, args.port, args.canvas_size, samples,
                               args.slot, args.att_name, args.pma)
    print(f"[3/3] 截圖 {len(manifest['results'])} 張,console errors: {len(manifest['consoleErrors'])}")
    if manifest["consoleErrors"]:
        for e in manifest["consoleErrors"][:10]:
            print("   ", e)

    rows = diff_screenshots(args.out_dir, manifest)
    report = {
        "slot": args.slot, "chosen_method": chosen, "chosen_reason": reason,
        "score_1b": score, "hole_frac_of_content": hole_frac,
        "console_errors": manifest["consoleErrors"], "samples": rows,
    }
    with open(os.path.join(args.out_dir, "compare_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
