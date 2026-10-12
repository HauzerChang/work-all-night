#!/usr/bin/env node
/*
 * live_inspect.js — headless live-runtime harness for spine_inspector.html.
 *
 * Purpose (the unblock): drive the ACTUAL spine-webgl 3.8 runtime in headless Chromium,
 * load the project's real Spine asset, and read LIVE world-space measurements
 * (getState / getMeshData / getMeshBounds / getWorldVertices) from the runtime that
 * Cocos/Spine actually use — i.e. the ground truth the Python evaluators (deform_eval,
 * validate_against_real) only re-implement. Runs fully OFFLINE via the vendored runtime
 * (vendor/spine-webgl-3.8.75.js), so it works in sandboxed/scheduled envs where the
 * spine-webgl CDNs are blocked by egress policy.
 *
 * Usage:
 *   node tools/live_inspect/live_inspect.js [--asset NAME] [--repo DIR] [--exe PATH] [--probe]
 *     --asset  base name of the asset trio under assets/ (default: main_draw -> main_draw.{json,atlas,png})
 *     --repo   repo root (default: two levels up from this file)
 *     --exe    chromium executable (default: autodetect under $PLAYWRIGHT_BROWSERS_PATH)
 *     --probe  also scrub the first animation and print live getMeshBounds over time
 *
 * Requires: node `playwright` + a Chromium build (both pre-installed in the standard
 * research environment; PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers). Exits non-zero with a
 * clear message if either is missing, so callers can fall back to the Python evaluators.
 *
 * Output: a single JSON object on stdout (ok, spine, bones, slots, animations, meshes,
 * hasTexture, [probe]). Intended to be consumed by other tools / the next scheduled run.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

function arg(name, def){ const i = process.argv.indexOf('--'+name); if(i<0) return def;
  const v = process.argv[i+1]; return (v===undefined || v.startsWith('--')) ? true : v; }

const REPO = path.resolve(arg('repo', path.join(__dirname, '..', '..')));
const ASSET = arg('asset', 'main_draw');
const DO_PROBE = !!arg('probe', false);

function findChromium(exeArg){
  if(exeArg && exeArg!==true && fs.existsSync(exeArg)) return exeArg;
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || '/opt/pw-browsers';
  const cands = [];
  try{ for(const d of fs.readdirSync(base)){
    if(d.startsWith('chromium-')) cands.push(path.join(base, d, 'chrome-linux', 'chrome'));
  }}catch(e){}
  cands.push('/opt/pw-browsers/chromium-1194/chrome-linux/chrome');
  return cands.find(p=>fs.existsSync(p));
}

const MIME = { '.html':'text/html', '.js':'text/javascript', '.json':'application/json',
  '.atlas':'text/plain', '.png':'image/png', '.map':'application/json' };

function buildServeDir(){
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'live-inspect-'));
  const link = (src, dst)=>{ try{ fs.symlinkSync(src, path.join(dir, dst)); }
    catch(e){ fs.copyFileSync(src, path.join(dir, dst)); } };
  link(path.join(REPO, 'spine_inspector.html'), 'spine_inspector.html');
  try{ fs.symlinkSync(path.join(REPO, 'vendor'), path.join(dir, 'vendor')); }catch(e){}
  for(const ext of ['json','atlas','png']){
    const p = path.join(REPO, 'assets', ASSET+'.'+ext);
    if(fs.existsSync(p)) link(p, ASSET+'.'+ext);   // the inspector auto-fetches main_draw.* from its own dir
  }
  return dir;
}

function serve(root){
  return new Promise(resolve=>{
    const s = http.createServer((req,res)=>{
      let p = decodeURIComponent(req.url.split('?')[0]);
      if(p==='/') p='/spine_inspector.html';
      const fp = path.join(root, p);
      fs.readFile(fp,(e,buf)=>{
        if(e){ res.statusCode=404; res.end('nf'); return; }
        res.setHeader('Content-Type', MIME[path.extname(fp)]||'application/octet-stream');
        res.end(buf);
      });
    });
    s.listen(0,'127.0.0.1',()=>resolve(s));
  });
}

(async()=>{
  let chromium;
  try{ ({ chromium } = require('playwright')); }
  catch(e){ console.log(JSON.stringify({ok:false, error:'playwright not installed: '+e.message})); process.exit(2); }
  const exe = findChromium(arg('exe'));
  if(!exe){ console.log(JSON.stringify({ok:false, error:'no chromium build found under PLAYWRIGHT_BROWSERS_PATH'})); process.exit(2); }

  const serveDir = buildServeDir();
  const server = await serve(serveDir);
  const port = server.address().port;
  const url = `http://127.0.0.1:${port}/spine_inspector.html`;
  const out = { ok:false, asset:ASSET, runtime:'vendor/spine-webgl-3.8.75.js' };
  const logs = [];
  let browser;
  try{
    browser = await chromium.launch({ executablePath: exe, headless: true,
      args:['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--no-sandbox'] });
    const ctx = await browser.newContext({ viewport:{width:1280,height:800} });
    const pg = await ctx.newPage();
    pg.on('console', m=>logs.push('['+m.type()+'] '+m.text()));
    pg.on('pageerror', e=>logs.push('[pageerror] '+e.message));
    await pg.goto(url, { waitUntil:'load', timeout:30000 });
    await pg.waitForFunction(()=> window.spineTool && window.spineTool.ready && window.spineTool.ready(), { timeout:30000 });
    const st = await pg.evaluate(()=> window.spineTool.getState());
    out.spine = st.spine; out.bones = st.bones; out.slots = st.slots;
    out.animations = st.animations; out.meshes = st.meshes; out.hasTexture = st.hasTexture;
    if(DO_PROBE){
      out.probe = await pg.evaluate(()=>{
        const anims = window.spineTool.listAnimations();
        const results = {};
        const meshes = window.spineTool.getState().meshes;
        for(const a of anims.slice(0,3)){
          window.spineTool.setAnimation(a);
          const dur = window.spineTool.getState().duration || 1;
          const m = meshes[0];
          const row = [];
          for(const f of [0,0.25,0.5,0.75,1.0]){
            window.spineTool.setTime(dur*f);
            let b=null; try{ b=window.spineTool.getMeshBounds(m.slot, m.name); }catch(e){ b={err:String(e)}; }
            row.push({ f, bounds:b });
          }
          results[a] = { dur, slot:m.slot, name:m.name, samples:row };
        }
        return results;
      });
    }
    out.ok = !!(st && st.ready);
  }catch(e){ out.error = String(e && e.stack || e); }
  finally{ if(browser) await browser.close(); server.close(); try{ fs.rmSync(serveDir,{recursive:true,force:true}); }catch(e){} }
  out.logs = logs.filter(l=>!l.includes('ReadPixels'));   // drop benign swiftshader perf warnings
  console.log(JSON.stringify(out, null, 2));
  process.exit(out.ok?0:1);
})();
