# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 確定性大獎生成庫(MERGE_PLAN Phase B2/B3/B4)。

對外主要入口:
  from gen_lib.make_beat import generate_bigwin, write_bigwin, generate_idle, DEMO_PARTS, IDLE_DEMO_PARTS
  from gen_lib.pivot_axis import apply_joint_pivots, bone_origins_from_skel   # B3 繞關節 pivot 變換(結構軸)
  from gen_lib.sequence import (compose_bigwin_sequence, crossfade_bigwin_sequence,   # B4 序列組合
                                compose_idle_loop, build_beat_library, write_sequence)
  from gen_lib.mesh_gen import (generate_mesh, generate_and_gate,   # C1 deform-aware mesh 生成 + 自交閘
                                deform_gate, real_deform_field, crop_region)

過渡期(B2/B3/B4/C1)import repo 的 tools/analyzer、tools/mesh_gen;E1 會 self-contained bundle。見各 .py docstring。
"""
from .make_beat import (  # noqa: F401
    generate_bigwin, write_bigwin, generate_idle, parts_from_psd,
    DEMO_PARTS, IDLE_DEMO_PARTS, SUPPORTED_BEATS,
)
from .pivot_axis import (  # noqa: F401
    apply_joint_pivots, bone_origins_from_skel,
)
from .sequence import (  # noqa: F401
    compose_bigwin_sequence, crossfade_bigwin_sequence, compose_idle_loop,
    build_beat_library, seal_sequence, write_sequence, STANDARD_BIGWIN_ORDER,
)
from .mesh_gen import (  # noqa: F401
    generate_mesh, generate_and_gate, deform_gate, real_deform_field,
    crop_region, mesh_schema_ok, setup_clean,
)
