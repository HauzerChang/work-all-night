# vendor/ — offline third-party runtime

## spine-webgl-3.8.75.js
- **What**: Official Spine runtime `spine-webgl.js`, build **3.8.75** (compatible with the 3.8.99 `main_draw` asset; spine-ts runtimes are compatible within a 3.8.x line).
- **Why vendored**: `spine_inspector.html` renders via spine-webgl loaded from a CDN (jsDelivr / esotericsoftware). In sandboxed / scheduled environments those CDNs are blocked by egress policy (HTTP 403), so the inspector could never do a **live, in-browser round-trip** there. Vendoring the runtime lets the inspector (and a headless Chromium harness) run fully offline.
- **Source**: `EsotericSoftware/spine-runtimes` branch `3.8`, path `spine-ts/build/spine-webgl.js`, fetched via anonymous git read.
- **sha256**: 4b108bad314c152bf0ff7a7f56fce5c98073f05a2bfa53e880d6c24b6f7c3aa5
- **License**: Spine Runtimes License (see EsotericSoftware/spine-runtimes LICENSE). Redistributed here only to run the research tool against the project's own Spine assets.
- **Namespace reminder**: WebGL classes live under `spine.webgl.*`; core under `spine.*` (see CLAUDE.md 雷點 #1).
