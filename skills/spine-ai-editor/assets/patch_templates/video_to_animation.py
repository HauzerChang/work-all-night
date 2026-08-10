#!/usr/bin/env python3
"""
patch_templates/video_to_animation.py — TEMPLATE

Full pipeline: video file → extracted frames → manual/multimodal pose analysis
→ Spine animation patch.

This script has TWO modes:
  1. EXTRACT: probe a video and extract evenly-spaced frames (no animation generated yet)
  2. PATCH:   given a hand-filled pose spec (derived from looking at frames), produce
              the Spine animation patch

Reason for two-stage: the "look at frames and identify poses" step requires multimodal
vision (Claude reading PNG frames) and cannot be automated in pure Python. So:
  - Stage 1: this script extracts frames
  - Stage 2: Claude (or human) fills in POSE_PER_FRAME below
  - Stage 3: this script generates Spine animation from POSE_PER_FRAME
"""
from __future__ import annotations
import argparse
import copy
import json
import subprocess
from pathlib import Path


# ============================================================================
# CONFIG: video extraction
# ============================================================================

# These are auto-detected if you run with `--probe`
DEFAULT_FRAME_COUNT = 9      # how many frames to extract (8~12 is common)
EXTRACT_FORMAT = "png"        # png or jpg


# ============================================================================
# FILL IN AFTER LOOKING AT FRAMES: pose data
# ============================================================================

ANIM_NAME = "Fg_Main_FromVideo"
DURATION = 2.0   # total animation duration in seconds (often = video duration, or 1 cycle)

# For each extracted frame, record the observed pose.
# Each entry maps bone_name → {timeline_type: value}
# Values are RELATIVE to setup pose (deltas).
#
# Example (after looking at 9 frames of a "wave" video):
POSE_PER_FRAME = [
    # frame 0 @ t=0.0s: 立正
    {
        "main":       {"translate": {"x": 0, "y": 0}},
        "main_arm_L": {"rotate": 0},
    },
    # frame 1 @ t=0.25s: 開始抬手
    {
        "main":       {"translate": {"x": 0, "y": 0}},
        "main_arm_L": {"rotate": -15},
    },
    # frame 2 @ t=0.5s: 揮手頂點
    {
        "main":       {"translate": {"x": 0, "y": -2}},
        "main_arm_L": {"rotate": -45},
    },
    # ... fill in 6~9 more frames
    # 最後一幀通常 = 第一幀（loop seamless）
]

# Time mapping: which video timestamp each frame represents.
# If empty, evenly distribute frames over DURATION.
FRAME_TIMES = []  # e.g. [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

# Slot overrides (same as add_animation.py)
SLOT_OVERRIDES = {
    "arm_L":  {"attachment": [{"name": "arm_L"}]},
    "arm_R":  {"attachment": [{"name": "arm_R"}]},
    "body_up": {"attachment": [{"name": "body_up"}]},
    # ... and hide weapon if needed
}


# ============================================================================
# IMPLEMENTATION
# ============================================================================

def probe_video(video_path: Path) -> dict:
    """Get video duration / fps / dimensions."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,r_frame_rate,duration,codec_name",
        "-show_entries", "format=duration,size",
        "-of", "json",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def extract_frames(video_path: Path, out_dir: Path, count: int, duration: float) -> list[Path]:
    """Extract N evenly-spaced frames from video to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(count):
        t = (duration / (count - 1)) * i if count > 1 else 0
        # Force leading zero (bc -> .5 problem workaround)
        t_str = f"{t:.3f}"
        out_path = out_dir / f"frame_{i:02d}_t{t_str}s.{EXTRACT_FORMAT}"
        cmd = [
            "ffmpeg", "-y",
            "-ss", t_str,
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(out_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[warn] frame {i} extraction failed: {result.stderr[:200]}")
        else:
            frames.append(out_path)
    return frames


def build_animation_from_poses() -> dict:
    """Convert POSE_PER_FRAME → Spine animation timelines."""
    n_frames = len(POSE_PER_FRAME)
    if n_frames < 2:
        raise RuntimeError("Need at least 2 frames to build animation")

    # Compute frame times
    if FRAME_TIMES:
        times = FRAME_TIMES
    else:
        times = [DURATION * i / (n_frames - 1) for i in range(n_frames)]

    # Collect all bone names mentioned across frames
    all_bones = set()
    for frame_pose in POSE_PER_FRAME:
        all_bones.update(frame_pose.keys())

    # Build per-bone timelines
    bone_timelines = {}
    for bone_name in all_bones:
        bone_timeline = {}

        # Collect each timeline type that appears
        types_seen = set()
        for frame_pose in POSE_PER_FRAME:
            if bone_name in frame_pose:
                types_seen.update(frame_pose[bone_name].keys())

        for timeline_type in types_seen:  # "rotate", "translate", "scale"
            keyframes = []
            for i, frame_pose in enumerate(POSE_PER_FRAME):
                if bone_name in frame_pose and timeline_type in frame_pose[bone_name]:
                    value = frame_pose[bone_name][timeline_type]
                    kf = {"time": times[i]}
                    if timeline_type == "rotate":
                        kf["angle"] = value
                    elif timeline_type == "translate":
                        if isinstance(value, dict):
                            kf.update(value)
                        else:
                            kf["y"] = value  # shorthand: just y
                    elif timeline_type == "scale":
                        if isinstance(value, dict):
                            kf.update(value)
                    keyframes.append(kf)
            bone_timeline[timeline_type] = keyframes

        bone_timelines[bone_name] = bone_timeline

    return {
        "slots": copy.deepcopy(SLOT_OVERRIDES),
        "bones": bone_timelines,
    }


def patch_spine(spine_json_path: Path, overwrite: bool = False) -> dict:
    data = json.loads(spine_json_path.read_text())

    if ANIM_NAME in data["animations"] and not overwrite:
        raise RuntimeError(f"{ANIM_NAME} already exists")

    bone_names = {b["name"] for b in data["bones"]}
    for frame_pose in POSE_PER_FRAME:
        for bn in frame_pose:
            if bn not in bone_names:
                raise RuntimeError(f"Bone {bn!r} not in skeleton")

    data["animations"][ANIM_NAME] = build_animation_from_poses()
    spine_json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return {
        "animation_added": ANIM_NAME,
        "duration_s": DURATION,
        "frames_used": len(POSE_PER_FRAME),
        "bones_animated": sorted(set().union(*(p.keys() for p in POSE_PER_FRAME))),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="Inspect video metadata")
    p_probe.add_argument("video", help="Video file path")

    p_extract = sub.add_parser("extract", help="Extract frames from video")
    p_extract.add_argument("video", help="Video file path")
    p_extract.add_argument("--out", required=True, help="Output dir for frames")
    p_extract.add_argument("--count", type=int, default=DEFAULT_FRAME_COUNT)
    p_extract.add_argument("--duration", type=float, help="Override duration (default = video duration)")

    p_patch = sub.add_parser("patch", help="Apply POSE_PER_FRAME to spine.json")
    p_patch.add_argument("spine_json", help="Path to spine .json")
    p_patch.add_argument("--overwrite", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "probe":
        info = probe_video(Path(args.video))
        print(json.dumps(info, indent=2))

    elif args.cmd == "extract":
        info = probe_video(Path(args.video))
        duration = args.duration or float(info["format"]["duration"])
        frames = extract_frames(Path(args.video), Path(args.out), args.count, duration)
        print(json.dumps({
            "extracted": len(frames),
            "duration_s": duration,
            "frames": [str(f) for f in frames],
        }, indent=2))
        print("\n[next] Look at each frame, fill in POSE_PER_FRAME in this script,")
        print("       then run: python video_to_animation.py patch <spine.json>")

    elif args.cmd == "patch":
        result = patch_spine(Path(args.spine_json), overwrite=args.overwrite)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
