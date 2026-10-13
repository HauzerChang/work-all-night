# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 確定性生成 / 結構變換庫(MERGE_PLAN Phase B)。

對外主要入口:
  from gen_lib.make_beat import generate_bigwin, write_bigwin, DEMO_PARTS, SUPPORTED_BEATS  # B2 大獎節拍生成
  from gen_lib.pivot_about import apply_pivot_about, generate_bigwin_about_pivots           # B3 繞關節 pivot 變換

過渡期(B2/B3)import repo 的 tools/analyzer;E1 會 self-contained bundle。見各模組 docstring。
"""
from .make_beat import (  # noqa: F401
    generate_bigwin, write_bigwin, parts_from_psd,
    DEMO_PARTS, SUPPORTED_BEATS,
)
from .pivot_about import (  # noqa: F401
    apply_pivot_about, generate_bigwin_about_pivots,
)
