#!/bin/bash
# SessionStart hook — 為排程/web session 準備純 CPU 研究環境。
# 每個雲端容器是全新的,這裡確保 mesh 工具(opencv/triangle/scipy/numpy)就緒。
set -euo pipefail

# 只在遠端(Claude Code on the web / 排程)執行;本機開發略過。
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# 安裝 CPU 依賴(idempotent:已裝則秒過)。
if [ -f requirements.txt ]; then
  python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt
fi

# 讓 tools/mesh_gen(S2-S4)與 tools/analyzer(S1)可直接 import。
echo 'export PYTHONPATH="'"$CLAUDE_PROJECT_DIR"'/tools/mesh_gen:'"$CLAUDE_PROJECT_DIR"'/tools/analyzer:${PYTHONPATH:-}"' >> "$CLAUDE_ENV_FILE"

echo "[session-start] research env ready: $(python3 -c 'import numpy,cv2,triangle,scipy;print("numpy",numpy.__version__,"cv2",cv2.__version__,"scipy",scipy.__version__)')"
