"""Regression coverage for recorded Codex subscription usage and cost."""

import importlib.util
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

    def test_go_catalog_estimate_is_not_reported_as_cash(self):
        row = {"input_tokens": 100, "output_tokens": 20, "agent_cost_usd": 0.5}
        self.assertEqual(recorder.case_price(row, "opencode-go/glm-5.3", {}, "omp"),
                         (None, "unreported"))
        self.assertEqual(recorder.token_usage(row)["output_tokens"], 20)

    def test_go_missing_usage_does_not_imply_free(self):
        self.assertEqual(recorder.case_price({}, "opencode-go/glm-5.3", {}, "omp"),
                         (None, "unreported"))
        self.assertTrue(all(value == "unreported" for value in recorder.token_usage({}).values()))


if __name__ == "__main__":
    unittest.main()
