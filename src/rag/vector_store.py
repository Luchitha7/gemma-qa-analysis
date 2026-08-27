import os
from typing import List, Dict, Any, Optional
import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_embed_model = SentenceTransformer(MODEL_NAME)

_default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "vector_data", "chromadb")
STORE_DIR = os.getenv("CHROMA_PERSIST_DIR", _default_dir)
os.makedirs(STORE_DIR, exist_ok=True)

# Initialize ChromaDB Persistent Client
chroma_client = chromadb.PersistentClient(path=STORE_DIR)
collection_name = "tenant_policies"

def get_collection():
    return chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"} # Use cosine similarity
    )

def add_policy_chunks(tenant_id: str, policies: List[Dict[str, Any]]):
    """Chunk, embed, and store company policy documents into ChromaDB for a specific tenant."""
    if not policies:
        return

    collection = get_collection()
    
    # Check what already exists to avoid duplicates
    existing_docs = collection.get(
        where={"tenant_id": tenant_id}
    )
    existing_titles = [m.get("title") for m in existing_docs.get("metadatas", []) if m]

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for idx, p in enumerate(policies):
        title = p.get("title", f"Policy {idx+1}")
        content = p.get("content", "").strip()
        if not content:
            continue
            
        if title not in existing_titles:
            doc_id = f"{tenant_id}_{title.replace(' ', '_')}_{idx}"
            text = f"{title}: {content}"
            emb = _embed_model.encode(text).tolist()

            ids.append(doc_id)
            documents.append(text)
            embeddings.append(emb)
            metadatas.append({
                "tenant_id": tenant_id,
                "title": title,
                "content": content
            })
            existing_titles.append(title)

    if ids:
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        print(f"[Vector Store] Stored {len(ids)} policy chunks for tenant '{tenant_id}' in ChromaDB.")


def search_policies(tenant_id: str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Retrieve top-k relevant policy chunks from ChromaDB for a customer interaction turn."""
    collection = get_collection()
    
    query_emb = _embed_model.encode(query).tolist()
    
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k,
        where={"tenant_id": tenant_id}
    )
    
    hits = []
    if results["metadatas"] and results["metadatas"][0]:
        for i, meta in enumerate(results["metadatas"][0]):
            score = results["distances"][0][i] if "distances" in results and results["distances"] else 0.0
            hits.append({
                "title": meta["title"],
                "content": meta["content"],
                "similarity": round(1.0 - score, 3) # Chroma returns distance for cosine (1 - cos_sim)
            })
            
    return hits


def get_tenant_policies(tenant_id: str) -> List[Dict[str, Any]]:
    """Retrieve all policy chunks stored for a given tenant."""
    collection = get_collection()
    results = collection.get(where={"tenant_id": tenant_id})
    return results.get("metadatas", [])


def delete_tenant_policies(tenant_id: str):
    """Delete all policies for a given tenant."""
    collection = get_collection()
    collection.delete(where={"tenant_id": tenant_id})
    print(f"[Vector Store] Deleted all policies for tenant '{tenant_id}'.")
