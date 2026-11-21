"""Regression coverage for recorded Codex subscription usage and cost."""

import importlib.util
import json
import tempfile
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("evals_record", Path(__file__).with_name("evals-record.py"))
assert spec and spec.loader
recorder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorder)


class TerraSubscriptionTest(unittest.TestCase):
    """Terra tokens and reported estimates must not become cash charges."""

    def test_usage_is_preserved_without_cash_cost(self):
        row = {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 7,
               "agent_cost_usd": 9.0, "total_cost_usd": 11.0}
        self.assertEqual(recorder.case_price(row, "openai-codex/gpt-6.1-terra", {}, "omp"),
                         (None, "subscription"))
        self.assertEqual(recorder.token_usage(row)["cache_read_input_tokens"], 7)
        self.assertEqual(recorder.token_usage(row)["reasoning_tokens"], "unreported")

    def test_missing_usage_is_not_zero(self):
        self.assertEqual(recorder.case_price({}, "openai-codex/gpt-6.1-terra", {}, "omp"),
                         (None, "subscription"))
        self.assertTrue(all(value == "unreported" for value in recorder.token_usage({}).values()))

    def test_other_client_does_not_inherit_subscription(self):
        self.assertEqual(recorder.case_price({}, "openai-codex/gpt-6.1-terra", {}, "codex"),
                         (None, "unreported"))

    def test_codex_cli_subscription_keeps_tokens_without_cash(self):
        row = {"input_tokens": 315, "output_tokens": 130, "cache_read_input_tokens": 24448,
               "agent_cost_usd": 0.42, "total_cost_usd": 0.57}
        self.assertEqual(
            recorder.case_price(row, "gpt-6.1-sol", {}, "codex-daily-driver", "subscription"),
            (None, "subscription"),
        )
        usage = recorder.token_usage(row)
        self.assertEqual(usage["uncached_input_tokens"], 315)
        self.assertEqual(usage["cache_read_input_tokens"], 24448)
        self.assertEqual(usage["output_tokens"], 130)

    def test_codex_cli_missing_usage_stays_unreported(self):
        self.assertEqual(
            recorder.case_price({}, "gpt-6.1-sol", {}, "codex-daily-driver", "subscription"),
            (None, "subscription"),
        )
        self.assertTrue(all(value == "unreported" for value in recorder.token_usage({}).values()))

    def test_codex_cli_without_recorded_evidence_is_not_subscription(self):
        row = {"input_tokens": 10, "output_tokens": 2, "agent_cost_usd": 0.5}
        self.assertEqual(recorder.case_price(row, "gpt-6.1-sol", {}, "codex-daily-driver"),
                         (0.5, "reported"))

    def test_go_catalog_estimate_is_not_reported_as_cash(self):
        row = {"input_tokens": 100, "output_tokens": 20, "agent_cost_usd": 0.5}
        self.assertEqual(recorder.case_price(row, "opencode-go/glm-5.3", {}, "omp"),
                         (None, "unreported"))
        self.assertEqual(recorder.token_usage(row)["output_tokens"], 20)

    def test_go_missing_usage_does_not_imply_free(self):
        self.assertEqual(recorder.case_price({}, "opencode-go/glm-5.3", {}, "omp"),
                         (None, "unreported"))
        self.assertTrue(all(value == "unreported" for value in recorder.token_usage({}).values()))

    def test_effective_route_is_preserved_without_a_served_identity_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = root / "bare" / "case" / "00"
            task.mkdir(parents=True)
            (task / "task.json").write_text(json.dumps({
                "success_criteria_results": [],
                "environment_info": {
                    "omp_model": "openai-codex/gpt-6.1-terra",
                    "omp_effective_model": "openai-codex/gpt-6.1-terra",
                    "omp_effective_thinking": "high",
                    "omp_skills_loaded": [],
                },
            }))
            run = {"task_results": [{"variant_id": "bare", "task_id": "case"}]}
            attempt = recorder.run_attempts(root, run, root)[0]
            self.assertEqual(attempt["omp_route"], {
                "effective_model": "openai-codex/gpt-6.1-terra",
                "effective_thinking": "high",
                "skills_loaded": [],
            })


if __name__ == "__main__":
    unittest.main()
