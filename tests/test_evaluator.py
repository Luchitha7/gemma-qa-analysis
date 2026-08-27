"""Unit tests for the Dynamic Evaluator mathematical scoring and circuit breakers."""

import unittest
from src.services.dynamic_evaluator import (
    calculate_category_scores,
    check_auto_fail,
    parse_dynamic_ratings
)


class TestDynamicEvaluator(unittest.TestCase):
    def test_weighted_scoring_calculation(self):
        ratings = [
            {"category": "Communication", "name": "Greeting", "rating": "PASS", "score": 100},
            {"category": "Communication", "name": "Tone", "rating": "PASS", "score": 100},
            {"category": "Problem Resolution", "name": "Accuracy", "rating": "FAIL", "score": 0},
            {"category": "Problem Resolution", "name": "Speed", "rating": "PASS", "score": 100}
        ]
        category_weights = {
            "Communication": 0.40,
            "Problem Resolution": 0.60
        }
        
        # Communication average = 100
        # Problem Resolution average = (0 + 100) / 2 = 50
        # Blended = (100 * 0.40) + (50 * 0.60) = 40 + 30 = 70.0
        cat_scores, blended = calculate_category_scores(ratings, category_weights, is_auto_fail=False)
        
        self.assertEqual(cat_scores["Communication"], 100.0)
        self.assertEqual(cat_scores["Problem Resolution"], 50.0)
        self.assertEqual(blended, 70.0)

    def test_auto_fail_instant_zero(self):
        ratings = [
            {"category": "Communication", "name": "Greeting", "rating": "PASS", "score": 100}
        ]
        category_weights = {"Communication": 1.0}
        
        cat_scores, blended = calculate_category_scores(ratings, category_weights, is_auto_fail=True)
        self.assertEqual(blended, 0.0)
        self.assertEqual(cat_scores["Communication"], 0.0)

    def test_check_auto_fail_profanity_trigger(self):
        transcript = "[00:01] Agent: Shut up and listen to me!"
        is_fail, reason = check_auto_fail(transcript, harsh_lines=[], auto_fail_rules=[])
        self.assertTrue(is_fail)
        self.assertIn("Profanity/Discourtesy", reason)

    def test_check_auto_fail_clean(self):
        transcript = "[00:01] Agent: Thank you for calling, I am happy to help."
        is_fail, reason = check_auto_fail(transcript, harsh_lines=[], auto_fail_rules=[])
        self.assertFalse(is_fail)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
