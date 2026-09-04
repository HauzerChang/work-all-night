#!/usr/bin/env node
/**
 * S4 拆解流程第3點:manifest.json + 各件 PNG → .psd。
 *
 * 讀 psd_slice.py 相容格式的 manifest(見 knowledge/s4-psd-contract.md):
 *   {"source","size":[W,H],"parts":[{"name","z","opacity","offset":[l,t],"size":[w,h],"file"},...]}
 * 依 parts 陣列順序(z 由小到大 = 由下而上)組成多圖層 PSD,用 ag-psd 的 writePsd()。
 *
 * 不用 node-canvas(這個環境沒有 pangocairo,native build 會失敗)——ag-psd 的
 * Layer.imageData 接受純 {data,width,height} 像素陣列,不需要真的 Canvas 物件,
 * 改用 pngjs(純 JS)解 PNG 拿 RGBA buffer 直接塞進去。
 *
 * Usage: node manifest_to_psd.js <manifest.json> <layer_dir> <out.psd>
 */
const fs = require('fs');
const path = require('path');
const { PNG } = require('pngjs');
const { writePsd } = require('ag-psd');

function readPng(filePath) {
  const buf = fs.readFileSync(filePath);
  const png = PNG.sync.read(buf);
  return { data: new Uint8Array(png.data), width: png.width, height: png.height };
}

function main() {
  const [, , manifestPath, layerDir, outPath] = process.argv;
  if (!manifestPath || !layerDir || !outPath) {
    console.error('Usage: node manifest_to_psd.js <manifest.json> <layer_dir> <out.psd>');
    process.exit(1);
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const [W, H] = manifest.size;

  const children = manifest.parts.map((p) => {
    const filePath = path.join(layerDir, p.file);
    const imageData = readPng(filePath);
    if (imageData.width !== p.size[0] || imageData.height !== p.size[1]) {
      throw new Error(
        `size mismatch for ${p.file}: manifest says [${p.size}], PNG is ` +
        `[${imageData.width},${imageData.height}]`
      );
    }
    const [left, top] = p.offset;
    return {
      name: p.name,
      left, top,
      right: left + imageData.width,
      bottom: top + imageData.height,
      opacity: p.opacity != null ? p.opacity : 255,
      imageData,
    };
  });

  const psd = { width: W, height: H, children };
  const buffer = writePsd(psd);
  fs.writeFileSync(outPath, Buffer.from(buffer));
  console.log(JSON.stringify({
    written: outPath, size: [W, H], layers: children.length,
    names: children.map(c => c.name),
  }, null, 2));
}

main();
