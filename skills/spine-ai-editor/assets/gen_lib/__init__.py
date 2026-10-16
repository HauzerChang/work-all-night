# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 確定性大獎生成庫(MERGE_PLAN Phase B2/B3/B4)。

對外主要入口:
  from gen_lib.make_beat import generate_bigwin, write_bigwin, generate_idle, DEMO_PARTS, IDLE_DEMO_PARTS
  from gen_lib.pivot_axis import apply_joint_pivots, bone_origins_from_skel   # B3 繞關節 pivot 變換(結構軸)
  from gen_lib.sequence import (compose_bigwin_sequence, crossfade_bigwin_sequence,   # B4 序列組合
                                compose_idle_loop, build_beat_library, write_sequence)
  from gen_lib.mesh import (generate_part_mesh, deform_si_gate,                        # C1 mesh 生成 + 變形自交閘(結構軸)
                            generate_and_gate_part)
  from gen_lib.rig import (infer_limb_tree, infer_joint_pivots, infer_rig,             # C2 rig 自動推斷 + weighted mesh 生成(結構軸)
                           generate_weighted_part_mesh, weighted_deform_gate)

過渡期(B2/B3/B4)import repo 的 tools/analyzer、(C1)tools/mesh_gen、(C2)tools/mesh_gen+tools/rig;E1 會 self-contained bundle。見各 .py docstring。
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
    generate_part_mesh, deform_si_gate, generate_and_gate_part,
    mesh_is_schema_valid, has_real_deform, CURTAIN_DEMO_PARTS, ROBOT_DEMO_PARTS,
)
from .rig import (  # noqa: F401
    infer_limb_tree, infer_joint_pivots, infer_rig, rig_is_schema_valid,
    generate_weighted_part_mesh, eval_generated_weighted, weighted_deform_gate,
    synthetic_limb_chain, synthetic_star, award_robot_struct_parts, load_award_robot_parts,
)
