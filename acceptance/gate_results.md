# 驗收時自動閘全套結果(2026-07-03)

- ✅ `python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --eval`
- ✅ `python3 tools/mesh_gen/psd_slice.py assets/Symbol_Ww.psd --eval`
- ✅ `python3 tools/mesh_gen/evaluate_slicing.py`
- ✅ `python3 tools/mesh_gen/validate_psd_to_mesh.py`
- ✅ `python3 tools/mesh_gen/skel_to_json.py --draft /tmp/robot_draft.json --weights --eval`
- ✅ `python3 tools/mesh_gen/pack_atlas.py --eval`
- ✅ `python3 tools/mesh_gen/evaluate_skeleton.py assets/main_draw.json --selftest`
- ✅ `python3 tools/mesh_gen/evaluate_skeleton.py assets/Award.json --selftest`
- ✅ `python3 tools/mesh_gen/validate_draft_vs_award.py`
- ✅ `python3 tools/mesh_gen/validate_weights.py --skeleton acceptance/robot_asset/robot.json`
