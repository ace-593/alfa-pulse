import json
import tempfile
import unittest
from pathlib import Path

from bank_knowledge import build_handoff, load_index, search_verified_excerpts

INDEX = Path(__file__).parents[1] / "bank_evidence_index.json"


class BankKnowledgeTests(unittest.TestCase):
    def test_real_index_has_two_reviewed_excerpts(self):
        index = load_index(INDEX)
        self.assertEqual(len(index["human_checked_excerpts"]), 2)

    def test_search_rate_returns_quote_and_source(self):
        result = search_verified_excerpts("ставка", ["monetary_policy"], index_path=INDEX)
        self.assertEqual(result["igor_handoff_status"], "bank_excerpts_available")
        self.assertTrue(result["retrieved_bank_excerpts"])
        excerpt = result["retrieved_bank_excerpts"][0]
        self.assertTrue(excerpt["short_exact_quote"])
        self.assertTrue(excerpt["source_url"].startswith("https://"))
        self.assertGreaterEqual(excerpt["page"], 1)

    def test_unknown_topic_does_not_invent_bank_opinion(self):
        result = search_verified_excerpts("supply chain logistics", ["logistics"], index_path=INDEX)
        self.assertEqual(result["igor_handoff_status"], "requires_bank_document_review")
        self.assertEqual(result["retrieved_bank_excerpts"], [])
        self.assertTrue(result["queries_to_bank_corpus"][0]["candidate_only_not_found_evidence"])

    def test_handoff_contract(self):
        result = build_handoff("U_TEST", "NEWS_TEST", "потребление", ["macroeconomy"], index_path=INDEX, news_is_demo=True)
        self.assertEqual(result["schema_version"], "P1.1")
        self.assertEqual(result["company_id"], "U_TEST")
        self.assertIn("retrieved_bank_excerpts", result)
        self.assertIn("queries_to_bank_corpus", result)

    def test_invalid_index_raises(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text(json.dumps({"documents": "not-a-list"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_index(path)


if __name__ == "__main__":
    unittest.main()
