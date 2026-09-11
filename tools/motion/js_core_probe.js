#!/usr/bin/env node
/* 從 spine_trajectory_editor.html 抽出 spine-motion-core 區塊,在 node 執行並吐出數值。
   給 validate_motion_tools.py 做「頁面演算法 vs Python 演算法」逐點比對(parity)。
   用法:node tools/motion/js_core_probe.js <skeleton.json> <anim> <bone> <body> <px> <py> <fps> <spf> */
const fs = require("fs");
const path = require("path");

const CANDIDATES = [
  path.join(__dirname, "..", "..", "spine_trajectory_editor.html"),   // repo: tools/motion/ ・ skill: scripts/motion/
  path.join(__dirname, "..", "spine_trajectory_editor.html"),
  path.join(__dirname, "spine_trajectory_editor.html"),
  process.env.SPINE_TRAJECTORY_EDITOR || "",
].filter(Boolean);
const editorPath = CANDIDATES.find(p => fs.existsSync(p));
if (!editorPath) { console.error("找不到 spine_trajectory_editor.html;可用 SPINE_TRAJECTORY_EDITOR 指定"); process.exit(2); }
const html = fs.readFileSync(editorPath, "utf8");
const m = html.match(/\/\* ==== spine-motion-core BEGIN[\s\S]*?\/\* ==== spine-motion-core END ==== \*\//);
if (!m) { console.error("找不到 spine-motion-core 區塊"); process.exit(2); }
const SMC = eval(m[0] + "; SMC");

const [file, animName, bone, body, px, py, fps, spf] = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(file, "utf8"));
const sk = new SMC.Skel(data);
const anim = data.animations[animName];
const dur = SMC.duration(anim);
const n = Math.max(1, Math.round(dur * (+fps) * (+spf)));
const out = { duration: dur, frames: dur * fps, warnings: sk.warnings, series: [] };
for (let i = 0; i <= n; i++) {
  const t = dur * i / n;
  const s = sk.ownSplit(bone, anim, t, +px, +py);
  const b = sk.worldPos(body, anim, t, null, 0, 0);
  out.series.push({ t, body: b, rigid: s.rigid, rotOwn: s.rotOwn, transOwn: s.transOwn, actual: s.actual });
}
// spec 數學:旋鈕 → 迴圈邊界 → Spine keys
const C = { curve: 0.374, c2: 0.02, c3: 0.636, c4: 0.99 };
const keys = [{ frame: 0, wx: 0, wy: 3, curve: C }, { frame: 6, wx: 1.5, wy: -2, curve: C },
              { frame: 13, wx: -1.5, wy: 4, curve: C }, { frame: 20, wx: 0, wy: 3, curve: null }];
out.spec = {};
for (const [lag, scale] of [[0, 1], [3, 1], [5, 1.15], [13.5, 0.8]]) {
  const kb = SMC.applyKnobs(keys, ["wx", "wy"], { lag, scale, nf: 20 });
  const wr = SMC.wrapCycle(kb, 20, ["wx", "wy"], true);
  out.spec[`${lag}|${scale}`] = {
    wrapped: wr.map(k => ({ frame: k.frame, wx: k.wx, wy: k.wy, curve: k.curve })),
    spine: SMC.toSpineKeys(wr, 30, ["wx", "wy"]),
    samples: Array.from({ length: 81 }, (_, i) => SMC.sampleKeys(wr, ["wx", "wy"], i * 0.25, 20, true)),
  };
}
process.stdout.write(JSON.stringify(out));
