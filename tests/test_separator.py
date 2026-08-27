"""Unit tests for the guideline Markdown Criteria and Policy separator."""

import unittest
from src.rag.llm_separator import separate_criteria_and_policies


class TestLLMSeparator(unittest.TestCase):
    def setUp(self):
        self.sample_markdown = """
| CALL LINE ITEMS | DEFINITION |
| --- | --- |
| SOFT SKILL CATEGORY (25%) | |
| Branding and Survey | "Thank you for calling S-NET Communications. My name is _____ how can I help you today?" |
| Hold time and Dead Air | Follow proper hold procedure: Inform the customer, set expectations. |
| TECHNICAL KNOWLEDGE CATEGORY (50%) | |
| Verified customer | Validate name and company. |
| PROCESS KNOWLEDGE CATEGORY (25%) | |
| Case Tagging | Tagged correctly in CRM. |
| AUTO FAIL CATEGORY | |
| Discourtesy | Displayed profanity or rudeness. |
| Call Avoidance | Premature disconnect. |
"""

    def test_separation_categories_and_weights(self):
        result = separate_criteria_and_policies(self.sample_markdown)
        criteria = result.get("criteria", {})
        categories = criteria.get("categories", [])
        
        self.assertEqual(len(categories), 3)
        cat_names = [c["name"] for c in categories]
        self.assertIn("Soft Skills", cat_names)
        self.assertIn("Technical Knowledge", cat_names)
        self.assertIn("Process Knowledge", cat_names)

        weights = criteria.get("category_weights", {})
        self.assertAlmostEqual(weights.get("Soft Skills", 0), 0.25)
        self.assertAlmostEqual(weights.get("Technical Knowledge", 0), 0.50)

    def test_auto_fail_extraction(self):
        result = separate_criteria_and_policies(self.sample_markdown)
        criteria = result.get("criteria", {})
        auto_fails = criteria.get("auto_fail_rules", [])
        
        self.assertGreater(len(auto_fails), 0)
        af_names = [af["name"] for af in auto_fails]
        self.assertTrue(any("Discourtesy" in name or "Avoidance" in name for name in af_names))

    def test_rag_policy_extraction(self):
        result = separate_criteria_and_policies(self.sample_markdown)
        policies = result.get("company_policies", [])
        
        self.assertGreater(len(policies), 0)
        titles = [p["title"] for p in policies]
        self.assertTrue(any("S-NET" in t for t in titles))


if __name__ == "__main__":
    unittest.main()
