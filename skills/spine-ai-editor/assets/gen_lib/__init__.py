# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 確定性大獎節拍生成庫(MERGE_PLAN Phase B2)。

對外主要入口:
  from gen_lib.make_beat import generate_bigwin, write_bigwin, DEMO_PARTS, SUPPORTED_BEATS

過渡期(B2)import repo 的 tools/analyzer;E1 會 self-contained bundle。見 make_beat.py docstring。
"""
from .make_beat import (  # noqa: F401
    generate_bigwin, write_bigwin, parts_from_psd,
    DEMO_PARTS, SUPPORTED_BEATS,
)
# B3 結構軸:繞關節 pivot 變換(見 pivot_rig.py / references/structural_expansion.md SOP E)。
from .pivot_rig import (  # noqa: F401
    apply_joint_pivots, bone_origins, pivot_delta,
)
