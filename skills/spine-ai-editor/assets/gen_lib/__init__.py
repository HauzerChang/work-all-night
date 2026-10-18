# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 確定性大獎生成庫(MERGE_PLAN Phase B2/B3/B4)。

對外主要入口:
  from gen_lib.make_beat import generate_bigwin, write_bigwin, generate_idle, DEMO_PARTS, IDLE_DEMO_PARTS
  from gen_lib.pivot_axis import apply_joint_pivots, bone_origins_from_skel   # B3 繞關節 pivot 變換(結構軸)
  from gen_lib.sequence import (compose_bigwin_sequence, crossfade_bigwin_sequence,   # B4 序列組合
                                compose_idle_loop, build_beat_library, write_sequence)
  from gen_lib.mesh import (generate_part_mesh, deform_si_gate,                        # C1 mesh 生成 + 變形自交閘(結構軸)
                            generate_and_gate_part)
  from gen_lib.rig import (generate_weighted_part_mesh, generate_and_gate_weighted,    # C2 weighted mesh + rig 自動推斷(結構軸)
                           infer_limb_tree, infer_joint_pivots, rig_from_parts)

**self-contained(E1,2026-10-18)**:生成/評估引擎已逐位元 bundle 進 `gen_lib/_bundled/`
(gen_animations / mesh / rig / pivot 的 repo 來源複本),**不再相依本 research repo 的 `tools/`**;
各 `_wire_repo_tools()` 指向 `_bundled/`。見 `_bundled/README.md` 與各 .py docstring。
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
    generate_weighted_part_mesh, weighted_schema_valid, weighted_deform_gate,
    generate_and_gate_weighted, infer_limb_tree, infer_joint_pivots,
    rig_from_parts, load_award_robot_parts, award_robot_tree,
    make_chain_parts, make_star_parts, WEIGHTED_DEMO_PARTS,
)
