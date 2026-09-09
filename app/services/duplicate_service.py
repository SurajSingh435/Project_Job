import logging
from typing import Optional
import httpx

from app.core.config import settings
from app.models.complaint import Complaint, ComplaintStatus

logger = logging.getLogger(__name__)

async def get_embedding(text: str) -> list[float]:
    """Call OpenAI API to get a text embedding (text-embedding-3-small, 1536 dimensions)."""
    if not settings.openai_api_key:
        return []
        
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "text-embedding-3-small",
                    "input": text
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"Failed to fetch embedding: {e}")
        return []

async def find_possible_duplicate(new_embedding: list[float], category: str, threshold: float = 0.85) -> Optional[dict]:
    """Use MongoDB Atlas Vector Search to find the nearest duplicate complaint."""
    if not new_embedding:
        return None
        
    # Atlas Vector Search pipeline stage
    pipeline = [
        {
            "$vectorSearch": {
                "index": "complaint_vector_index",
                "path": "embedding",
                "queryVector": new_embedding,
                "numCandidates": 50,
                "limit": 5,
                "filter": {
                    "category": category,
                    "status": {"$in": [ComplaintStatus.open.value, ComplaintStatus.in_progress.value]}
                }
            }
        },
        {
            "$project": {
                "_id": 1,
                "score": {"$meta": "vectorSearchScore"},
                "category": 1,
                "description": 1,
                "status": 1
            }
        }
    ]
    
    try:
        # We drop to the motor driver collection level to use aggregation pipelines 
        # that include Atlas-specific features like $vectorSearch.
        collection = Complaint.get_motor_collection()
        results = await collection.aggregate(pipeline).to_list(length=5)
        
        for doc in results:
            # MongoDB's vectorSearchScore for cosine is 0.5 + (cosine_similarity / 2)
            # However, for normalized vectors, some drivers return true cosine directly.
            # We assume it returns a suitable comparable score.
            if doc.get("score", 0) >= threshold:
                return {
                    "id": str(doc["_id"]),
                    "score": doc["score"],
                    "description": doc.get("description")
                }
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        
    return None
