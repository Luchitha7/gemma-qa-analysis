"""Integration test for Multi-Tenant PostgreSQL, Vector RAG, and Dynamic Evaluator."""

import unittest
from src.db.database import init_db, SessionLocal
from src.db.models import Tenant
from src.rag.vector_store import add_policy_chunks, search_policies, delete_tenant_policies


class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.db = SessionLocal()
        cls.tenant_id = "TEST_INTEGRATION_TENANT"
        
        tenant = cls.db.query(Tenant).filter(Tenant.id == cls.tenant_id).first()
        if not tenant:
            tenant = Tenant(id=cls.tenant_id, name="Test Integration Company", description="Automated QA Test")
            cls.db.add(tenant)
            cls.db.commit()
            
    @classmethod
    def tearDownClass(cls):
        delete_tenant_policies(cls.tenant_id)
        tenant = cls.db.query(Tenant).filter(Tenant.id == cls.tenant_id).first()
        if tenant:
            cls.db.delete(tenant)
            cls.db.commit()
        cls.db.close()

    def test_database_and_vector_rag_flow(self):
        # 1. Verify Tenant in DB
        tenant = self.db.query(Tenant).filter(Tenant.id == self.tenant_id).first()
        self.assertIsNotNone(tenant)
        self.assertEqual(tenant.id, self.tenant_id)

        # 2. Add policy to ChromaDB
        policies = [
            {"title": "Escalation Protocol", "content": "When requested, transfer immediately to a supervisor."}
        ]
        add_policy_chunks(self.tenant_id, policies)

        # 3. Retrieve policy via semantic similarity
        hits = search_policies(self.tenant_id, "I need to talk to a supervisor or lead", top_k=1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Escalation Protocol")


if __name__ == "__main__":
    unittest.main()
