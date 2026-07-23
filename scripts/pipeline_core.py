from __future__ import annotations

import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


REQUIRED_CANDIDATE_FIELDS = {
    "buyer_company_name",
    "buyer_website",
    "buyer_hq",
    "buyer_persona",
    "strategic_fit_rationale",
    "evidence",
}
SCORE_FIELDS = (
    "strategic_fit",
    "track_record",
    "deployment_urgency",
    "geographic_proximity",
)
INTERNAL_DELIVERABLE_FIELDS = {
    "agent_channels",
    "buyer_tier",
    "composite_score",
    "criterion_scores",
    "evidence",
    "score_note",
}


class ContractError(ValueError):
    """Raised when a stage artifact violates its JSON contract."""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_intake(intake: dict[str, Any]) -> None:
    business = intake.get("business", {})
    constraints = intake.get("constraints", {})
    missing = [key for key in ("name", "industry", "region", "summary") if not business.get(key)]
    if missing:
        raise ContractError(f"intake missing business fields: {', '.join(missing)}")
    if constraints.get("fictional_data_only") is not True:
        raise ContractError("demo intake must require fictional_data_only=true")
    if constraints.get("contact_enrichment_allowed") is not False:
        raise ContractError("demo intake must disable contact enrichment")
    if constraints.get("outreach_allowed") is not False:
        raise ContractError("demo intake must disable outreach")


def validate_channel(channel: dict[str, Any]) -> None:
    if not channel.get("channel_id") or not channel.get("agent_scope"):
        raise ContractError("channel requires channel_id and agent_scope")
    candidates = channel.get("candidates")
    if not isinstance(candidates, list):
        raise ContractError("channel candidates must be a list")
    for index, candidate in enumerate(candidates):
        missing = sorted(REQUIRED_CANDIDATE_FIELDS - set(candidate))
        if missing:
            raise ContractError(
                f"{channel['channel_id']} candidate {index} missing: {', '.join(missing)}"
            )
        if not candidate["buyer_website"].endswith(".example"):
            raise ContractError(
                f"{candidate['buyer_company_name']}: demo website must use reserved .example"
            )
        evidence = candidate["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ContractError(f"{candidate['buyer_company_name']}: evidence is required")


def merge_channels(channels: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    raw_count = 0
    for channel in sorted(channels, key=lambda item: item["channel_id"]):
        validate_channel(channel)
        for candidate in channel["candidates"]:
            raw_count += 1
            key = candidate["buyer_company_name"].strip().casefold()
            existing = merged.get(key)
            incoming = dict(candidate)
            incoming["agent_channels"] = [channel["channel_id"]]
            if existing is None:
                merged[key] = incoming
                continue

            evidence = sorted(set(existing["evidence"] + incoming["evidence"]))
            channels_seen = sorted(set(existing["agent_channels"] + incoming["agent_channels"]))
            preferred = incoming if len(incoming["evidence"]) > len(existing["evidence"]) else existing
            merged[key] = {
                **preferred,
                "evidence": evidence,
                "agent_channels": channels_seen,
            }

    buyers = sorted(merged.values(), key=lambda item: item["buyer_company_name"].casefold())
    return {
        "buyers": buyers,
        "merge_metadata": {
            "raw_candidate_count": raw_count,
            "deduplicated_candidate_count": len(buyers),
            "duplicates_removed": raw_count - len(buyers),
        },
    }


def score_buyers(
    sourcing: dict[str, Any],
    judgment: dict[str, Any],
    matrix: dict[str, Any],
) -> dict[str, Any]:
    weights = matrix.get("criteria_weights", {})
    if set(weights) != set(SCORE_FIELDS):
        raise ContractError("matrix criteria must exactly match the scoring contract")
    total_weight = sum(Decimal(str(weights[field])) for field in SCORE_FIELDS)
    if total_weight != Decimal("1.0"):
        raise ContractError(f"matrix weights must sum to 1.0, got {total_weight}")

    score_rows = judgment.get("scores")
    if not isinstance(score_rows, list):
        raise ContractError("judgment scores must be a list")
    score_map = {row.get("buyer_company_name"): row for row in score_rows}
    buyer_names = {buyer["buyer_company_name"] for buyer in sourcing["buyers"]}
    if set(score_map) != buyer_names:
        missing = sorted(buyer_names - set(score_map))
        extra = sorted(set(score_map) - buyer_names)
        raise ContractError(f"score join mismatch; missing={missing}, extra={extra}")

    thresholds = matrix["tier_thresholds"]
    tier_1 = Decimal(str(thresholds["tier_1_min"]))
    tier_2 = Decimal(str(thresholds["tier_2_min"]))
    scored = []
    for buyer in sourcing["buyers"]:
        judgment_row = score_map[buyer["buyer_company_name"]]
        criteria: dict[str, int] = {}
        for field in SCORE_FIELDS:
            value = judgment_row.get(field)
            if not isinstance(value, int) or not 1 <= value <= 10:
                raise ContractError(
                    f"{buyer['buyer_company_name']}: {field} must be an integer from 1 to 10"
                )
            criteria[field] = value

        composite = sum(
            Decimal(str(weights[field])) * Decimal(criteria[field]) for field in SCORE_FIELDS
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        tier = "Tier 1" if composite >= tier_1 else "Tier 2" if composite >= tier_2 else "Tier 3"
        scored.append(
            {
                **buyer,
                "criterion_scores": criteria,
                "composite_score": str(composite),
                "buyer_tier": tier,
                "score_note": judgment_row.get("note", ""),
            }
        )

    scored.sort(key=lambda item: (-Decimal(item["composite_score"]), item["buyer_company_name"]))
    return {
        "scored_buyers": scored,
        "scoring_metadata": {
            "criteria_weights": weights,
            "tier_thresholds": thresholds,
            "arithmetic": "decimal half-up",
        },
    }


def build_gate_review(scored: dict[str, Any], approved: bool) -> dict[str, Any]:
    return {
        "decision": "approved" if approved else "pending_human_review",
        "approved_by": "demo_operator" if approved else None,
        "candidate_count": len(scored["scored_buyers"]),
        "candidates": [
            {
                "buyer_company_name": row["buyer_company_name"],
                "buyer_tier": row["buyer_tier"],
                "composite_score": row["composite_score"],
                "score_note": row["score_note"],
            }
            for row in scored["scored_buyers"]
        ],
    }


def build_deliverable(scored: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for buyer in scored["scored_buyers"]:
        if buyer["buyer_tier"] == "Tier 3":
            continue
        row = {
            "buyer_company_name": buyer["buyer_company_name"],
            "buyer_website": buyer["buyer_website"],
            "buyer_hq": buyer["buyer_hq"],
            "buyer_persona": buyer["buyer_persona"],
            "fit_summary": buyer["strategic_fit_rationale"],
            "source_count": len(buyer["evidence"]),
        }
        leaked = INTERNAL_DELIVERABLE_FIELDS & set(row)
        if leaked:
            raise ContractError(f"internal fields crossed deliverable boundary: {sorted(leaked)}")
        rows.append(row)
    return rows


def write_deliverable(output_dir: Path, rows: list[dict[str, Any]]) -> list[Path]:
    json_path = output_dir / "deliverable.json"
    csv_path = output_dir / "deliverable.csv"
    write_json(json_path, {"buyers": rows, "metadata": {"synthetic_demo": True}})
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]) if rows else [],
            lineterminator="\n",
        )
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    return [json_path, csv_path]


def run_pipeline(fixture_dir: Path, output_dir: Path, approve: bool) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    # A new run must never inherit a deliverable created by an earlier approval.
    # This keeps the gate a real boundary even when the same output directory is reused.
    for stale_deliverable in ("deliverable.json", "deliverable.csv"):
        (output_dir / stale_deliverable).unlink(missing_ok=True)
    intake = load_json(fixture_dir / "intake.json")
    validate_intake(intake)
    intake_path = output_dir / "intake.json"
    write_json(intake_path, intake)

    channels = [
        load_json(path)
        for path in sorted((fixture_dir / "agent_outputs").glob("channel_*.json"))
    ]
    if not channels:
        raise ContractError("no bounded-agent channel outputs found")
    sourcing = merge_channels(channels)
    sourcing_path = output_dir / "sourcing_buyers.json"
    write_json(sourcing_path, sourcing)

    scored = score_buyers(
        sourcing,
        load_json(fixture_dir / "agent_outputs" / "judgment_scores.json"),
        load_json(fixture_dir / "scoring_matrix.json"),
    )
    scored_path = output_dir / "scored_buyers.json"
    write_json(scored_path, scored)

    gate = build_gate_review(scored, approved=approve)
    gate_path = output_dir / "gate_review.json"
    write_json(gate_path, gate)
    artifacts = [intake_path, sourcing_path, scored_path, gate_path]

    if not approve:
        manifest = {
            "status": "awaiting_human_approval",
            "stages": {
                "intake": "complete",
                "research": "complete",
                "scoring": "complete",
                "gate": "waiting",
                "deliverable": "blocked",
            },
            "artifacts": [path.name for path in artifacts],
        }
        manifest_path = output_dir / "manifest.json"
        write_json(manifest_path, manifest)
        artifacts.append(manifest_path)
        return {"status": manifest["status"], "artifacts": artifacts}

    deliverable_paths = write_deliverable(output_dir, build_deliverable(scored))
    artifacts.extend(deliverable_paths)
    manifest = {
        "status": "complete",
        "stages": {
            "intake": "complete",
            "research": "complete",
            "scoring": "complete",
            "gate": "approved",
            "deliverable": "complete",
        },
        "artifacts": [path.name for path in artifacts],
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    artifacts.append(manifest_path)
    return {"status": manifest["status"], "artifacts": artifacts}
