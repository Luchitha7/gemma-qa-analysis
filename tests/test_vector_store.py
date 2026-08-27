"""Unit tests for ChromaDB Multi-Tenant Vector Store."""

import unittest
from src.rag.vector_store import (
    add_policy_chunks,
    search_policies,
    get_tenant_policies,
    delete_tenant_policies
)


class TestVectorStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tenant_a = "test_tenant_alpha"
        cls.tenant_b = "test_tenant_beta"
        
        # Clean up any leftover data
        delete_tenant_policies(cls.tenant_a)
        delete_tenant_policies(cls.tenant_b)

    def tearDown(self):
        delete_tenant_policies(self.tenant_a)
        delete_tenant_policies(self.tenant_b)

    def test_add_and_search_policies(self):
        policies = [
            {"title": "Refund Protocol", "content": "Refunds over $100 require supervisor approval."},
            {"title": "Hold Time Policy", "content": "Never keep a customer on hold for more than 2 minutes."}
        ]
        add_policy_chunks(self.tenant_a, policies)
        
        results = search_policies(self.tenant_a, "customer wants a money refund", top_k=1)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["title"], "Refund Protocol")

    def test_tenant_data_isolation(self):
        policies_a = [{"title": "Alpha Security", "content": "Validate birth date and phone."}]
        policies_b = [{"title": "Beta Security", "content": "Validate account pin number."}]
        
        add_policy_chunks(self.tenant_a, policies_a)
        add_policy_chunks(self.tenant_b, policies_b)
        
        # Tenant A should not find Tenant B policies
        results_a = search_policies(self.tenant_a, "pin number security", top_k=5)
        for hit in results_a:
            self.assertNotEqual(hit["title"], "Beta Security")
            
        # Tenant B search should only find Tenant B
        results_b = search_policies(self.tenant_b, "pin number security", top_k=1)
        self.assertEqual(results_b[0]["title"], "Beta Security")


if __name__ == "__main__":
    unittest.main()
