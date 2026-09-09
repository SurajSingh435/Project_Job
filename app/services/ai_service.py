import logging
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

class TriageResult(BaseModel):
    corrected_category: Literal["plumbing", "electrical", "security", "other"]
    urgency: Literal["low", "medium", "high", "critical"]
    clean_title: str = Field(..., max_length=200)
    reasoning: str

async def triage_complaint(description: str, submitted_category: str) -> dict:
    default_result = {
        "corrected_category": submitted_category,
        "urgency": "medium",
        "clean_title": description[:100] + ("..." if len(description) > 100 else ""),
        "reasoning": "AI triage unavailable"
    }

    if not settings.openai_api_key:
        return default_result

    prompt = f"""
    You are an AI assistant for a resident complaint management system.
    Please triage the following complaint.
    
    Submitted category: {submitted_category}
    Complaint description: {description}
    
    Return strict JSON with the following schema:
    - "corrected_category": must be one of: "plumbing", "electrical", "security", "other".
    - "urgency": must be one of: "low", "medium", "high", "critical".
    - "clean_title": a short, human-readable title summarizing the issue (max 200 chars).
    - "reasoning": one sentence explaining the urgency choice.
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that outputs only JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            triage_data = TriageResult.model_validate_json(content)
            
            return {
                "corrected_category": triage_data.corrected_category,
                "urgency": triage_data.urgency,
                "clean_title": triage_data.clean_title,
                "reasoning": triage_data.reasoning
            }
            
    except (httpx.RequestError, httpx.HTTPStatusError, ValidationError, KeyError) as e:
        logger.warning(f"AI triage failed: {e}")
        return default_result

from typing import Optional
from datetime import datetime, timezone

class NLSearchResponse(BaseModel):
    category: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[str] = None

async def parse_nl_search(query: str) -> dict:
    if not settings.openai_api_key:
        return {}
    
    today = datetime.now(timezone.utc).date().isoformat()
    prompt = f"""
    Extract search filters from the following query: "{query}"
    Today's date is: {today}
    
    Return strict JSON with these keys:
    - "category": (string or null) the category mentioned. Must be one of: "plumbing", "electrical", "security", "road", "water", "other", or null.
    - "status": (string or null) the status mentioned. Must be one of: "open", "in_progress", "resolved", or null.
    - "date_from": (string or null) ISO 8601 date string if a time range is specified (e.g. "2023-10-01T00:00:00Z"). If "last 7 days", calculate 7 days ago based on today's date.
    """
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that outputs only JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            parsed = NLSearchResponse.model_validate_json(content)
            
            return {
                "category": parsed.category,
                "status": parsed.status,
                "date_from": parsed.date_from
            }
    except Exception as e:
        logger.warning(f"NL Search parsing failed: {e}")
        return {}
