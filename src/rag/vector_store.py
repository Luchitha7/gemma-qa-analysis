"""Multi-Tenant Vector Database Store Module.

Uses sentence-transformers (all-MiniLM-L6-v2) for local embeddings with
tenant metadata isolation. Supports persistent JSON storage and ChromaDB.
"""

import os
import json
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer, util
import torch

MODEL_NAME = "all-MiniLM-L6-v2"
_embed_model = SentenceTransformer(MODEL_NAME)

STORE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "vector_data")
os.makedirs(STORE_DIR, exist_ok=True)
STORE_FILE = os.path.join(STORE_DIR, "tenant_policies.json")


def _load_store() -> Dict[str, List[Dict[str, Any]]]:
    if os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_store(store_data: Dict[str, List[Dict[str, Any]]]):
    with open(STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(store_data, f, indent=2, ensure_ascii=False)


def add_policy_chunks(tenant_id: str, policies: List[Dict[str, Any]]):
    """Chunk, embed, and store company policy documents for a specific tenant."""
    if not policies:
        return

    store = _load_store()
    tenant_policies = store.get(tenant_id, [])

    for idx, p in enumerate(policies):
        title = p.get("title", f"Policy {idx+1}")
        content = p.get("content", "").strip()
        if not content:
            continue
        
        # Avoid duplicate titles
        if not any(tp.get("title") == title for tp in tenant_policies):
            tenant_policies.append({
                "title": title,
                "content": content
            })

    store[tenant_id] = tenant_policies
    _save_store(store)
    print(f"[Vector Store] Stored {len(tenant_policies)} policy chunks for tenant '{tenant_id}'.")


def search_policies(tenant_id: str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Retrieve top-k relevant policy chunks for a customer interaction turn filtered by tenant_id."""
    store = _load_store()
    tenant_policies = store.get(tenant_id, [])
    if not tenant_policies:
        return []

    texts = [f"{p['title']}: {p['content']}" for p in tenant_policies]
    policy_embeddings = _embed_model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
    query_embedding = _embed_model.encode(query, convert_to_tensor=True, normalize_embeddings=True)

    sims = util.cos_sim(query_embedding, policy_embeddings)[0]
    ranked_indices = torch.topk(sims, k=min(top_k, len(tenant_policies))).indices.tolist()

    hits = []
    for idx in ranked_indices:
        score = float(sims[idx])
        hits.append({
            "title": tenant_policies[idx]["title"],
            "content": tenant_policies[idx]["content"],
            "similarity": round(score, 3)
        })

    return hits


def get_tenant_policies(tenant_id: str) -> List[Dict[str, Any]]:
    """Retrieve all policy chunks stored for a given tenant."""
    store = _load_store()
    return store.get(tenant_id, [])


def delete_tenant_policies(tenant_id: str):
    """Delete all policy knowledge chunks for a tenant."""
    store = _load_store()
    if tenant_id in store:
        del store[tenant_id]
        _save_store(store)
        print(f"[Vector Store] Deleted all policies for tenant '{tenant_id}'.")


def delete_single_policy(tenant_id: str, title: str):
    """Delete a single policy chunk by title for a tenant."""
    store = _load_store()
    if tenant_id in store:
        store[tenant_id] = [p for p in store[tenant_id] if p.get("title") != title]
        _save_store(store)
        print(f"[Vector Store] Deleted policy '{title}' for tenant '{tenant_id}'.")
