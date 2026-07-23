from __future__ import annotations

import argparse
from pathlib import Path

from scripts.pipeline_core import run_pipeline


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the synthetic strategic-buyer agent pipeline."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo_output",
        help="Artifact directory (default: demo_output)",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Explicitly approve the synthetic gate and create the deliverable.",
    )
    args = parser.parse_args()

    result = run_pipeline(
        fixture_dir=ROOT / "fixtures",
        output_dir=args.output,
        approve=args.approve,
    )

    print(f"pipeline status: {result['status']}")
    for artifact in result["artifacts"]:
        print(f"artifact: {artifact}")
    if result["status"] == "awaiting_human_approval":
        print("STOP: review gate_review.json, then rerun with --approve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
