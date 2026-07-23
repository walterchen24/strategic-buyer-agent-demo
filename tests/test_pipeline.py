from __future__ import annotations

import copy
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.pipeline_core import (
    ContractError,
    INTERNAL_DELIVERABLE_FIELDS,
    build_deliverable,
    load_json,
    merge_channels,
    run_pipeline,
    score_buyers,
    validate_channel,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class PipelineTests(unittest.TestCase):
    def _channels(self):
        return [
            load_json(path)
            for path in sorted((FIXTURES / "agent_outputs").glob("channel_*.json"))
        ]

    def _scored(self):
        return score_buyers(
            merge_channels(self._channels()),
            load_json(FIXTURES / "agent_outputs" / "judgment_scores.json"),
            load_json(FIXTURES / "scoring_matrix.json"),
        )

    def test_pipeline_manifest_preserves_human_gate(self):
        manifest = load_json(ROOT / "pipeline.json")
        stage_ids = [stage["id"] for stage in manifest["stages"]]
        self.assertEqual(stage_ids, ["intake", "research", "scoring", "gate", "deliverable"])
        gate = next(stage for stage in manifest["stages"] if stage["id"] == "gate")
        self.assertEqual(gate["owner"], "human")
        self.assertTrue(gate["hard_stop"])

    def test_channel_requires_reserved_example_domain(self):
        channel = copy.deepcopy(self._channels()[0])
        channel["candidates"][0]["buyer_website"] = "https://real-company.com"
        with self.assertRaises(ContractError):
            validate_channel(channel)

    def test_merge_deduplicates_cross_agent_candidate(self):
        merged = merge_channels(self._channels())
        self.assertEqual(merged["merge_metadata"]["raw_candidate_count"], 4)
        self.assertEqual(merged["merge_metadata"]["deduplicated_candidate_count"], 3)
        self.assertEqual(merged["merge_metadata"]["duplicates_removed"], 1)

    def test_merge_preserves_cross_agent_provenance(self):
        merged = merge_channels(self._channels())
        aster = next(
            row
            for row in merged["buyers"]
            if row["buyer_company_name"] == "Aster Retail Group"
        )
        self.assertEqual(aster["agent_channels"], ["adjacent", "ecosystem"])
        self.assertEqual(len(aster["evidence"]), 3)

    def test_exact_weighted_score_and_tier(self):
        scored = self._scored()
        aster = next(
            row
            for row in scored["scored_buyers"]
            if row["buyer_company_name"] == "Aster Retail Group"
        )
        self.assertEqual(Decimal(aster["composite_score"]), Decimal("8.4"))
        self.assertEqual(aster["buyer_tier"], "Tier 1")

    def test_score_join_mismatch_fails(self):
        judgment = load_json(FIXTURES / "agent_outputs" / "judgment_scores.json")
        judgment["scores"].pop()
        with self.assertRaises(ContractError):
            score_buyers(
                merge_channels(self._channels()),
                judgment,
                load_json(FIXTURES / "scoring_matrix.json"),
            )

    def test_pipeline_stops_at_human_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(FIXTURES, Path(tmp), approve=False)
            self.assertEqual(result["status"], "awaiting_human_approval")
            self.assertFalse((Path(tmp) / "deliverable.json").exists())
            gate = json.loads((Path(tmp) / "gate_review.json").read_text())
            self.assertEqual(gate["decision"], "pending_human_review")

    def test_pending_rerun_removes_prior_deliverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            run_pipeline(FIXTURES, output, approve=True)
            self.assertTrue((output / "deliverable.json").exists())
            run_pipeline(FIXTURES, output, approve=False)
            self.assertFalse((output / "deliverable.json").exists())
            self.assertFalse((output / "deliverable.csv").exists())

    def test_approved_pipeline_creates_deliverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(FIXTURES, Path(tmp), approve=True)
            self.assertEqual(result["status"], "complete")
            self.assertTrue((Path(tmp) / "deliverable.json").exists())
            self.assertTrue((Path(tmp) / "deliverable.csv").exists())

    def test_deliverable_excludes_internal_fields_and_tier_three(self):
        rows = build_deliverable(self._scored())
        self.assertEqual(
            [row["buyer_company_name"] for row in rows],
            ["Aster Retail Group", "Beacon Commerce Holdings"],
        )
        for row in rows:
            self.assertFalse(INTERNAL_DELIVERABLE_FIELDS & set(row))


if __name__ == "__main__":
    unittest.main()
