# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 確定性大獎生成庫(MERGE_PLAN Phase B2/B3/B4)。

對外主要入口:
  from gen_lib.make_beat import generate_bigwin, write_bigwin, generate_idle, DEMO_PARTS, IDLE_DEMO_PARTS
  from gen_lib.pivot_axis import apply_joint_pivots, bone_origins_from_skel   # B3 繞關節 pivot 變換(結構軸)
  from gen_lib.sequence import (compose_bigwin_sequence, crossfade_bigwin_sequence,   # B4 序列組合
                                compose_idle_loop, build_beat_library, write_sequence)
  from gen_lib.mesh import (generate_mesh, mesh_from_region, mesh_schema_errors,       # C1 mesh 生成 + 變形自交閘
                            real_deform_field_for, deform_si_check)

過渡期(B2/B3/B4)import repo 的 tools/analyzer;E1 會 self-contained bundle。見各 .py docstring。
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
from .mesh import (  # noqa: F401
    generate_mesh, mesh_from_region, write_mesh, mesh_schema_errors,
    real_deform_field_for, deform_si_check, CURTAIN_MESHES,
)
