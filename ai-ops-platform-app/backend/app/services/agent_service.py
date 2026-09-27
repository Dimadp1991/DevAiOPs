"""Agent analysis — LLM (vLLM OpenAI-compatible API)."""

import json
import logging
import re

import httpx

from app.config import settings
from app.models.schemas import AgentAnalysis, Incident

logger = logging.getLogger(__name__)


async def analyze_incident(incident: Incident) -> AgentAnalysis | None:
    """Analyze incident using LLM completion. Returns None if LLM is disabled or fails."""
    if not settings.agent_enabled or not settings.llm_api_url:
        logger.info("LLM agent disabled or llm_api_url not configured.")
        return None

    try:
        return await _llm_analysis(incident)
    except Exception as exc:
        logger.warning("LLM analysis failed: %s", exc)
        return None


async def _llm_analysis(incident: Incident) -> AgentAnalysis:
    context = {
        "alert": incident.alert.model_dump(mode="json"),
        "service": incident.service_info.model_dump(mode="json"),
        "k8s_state": incident.k8s_state.model_dump(mode="json"),
        "telemetry": {
            "metrics": incident.telemetry.metrics,
            "recent_logs": incident.telemetry.recent_logs[-20:],
            "events": incident.telemetry.events[:10],
            "gpu": incident.telemetry.gpu.model_dump(mode="json") if incident.telemetry.gpu else None,
        },
        "knowledge_base": incident.knowledge_base.model_dump(mode="json"),
    }

    system_prompt = (
        "You are an expert SRE AI agent. Analyze the incident context and respond ONLY "
        "with valid JSON matching this schema: "
        '{"root_cause": "string", "confidence": 0.0-1.0, "remediation_steps": ["..."], "reasoning": "string"}'
        " be accurate and concise answer Only in hebrew "
    )
    user_prompt = f"Analyze this Kubernetes incident:\n\n{json.dumps(context, indent=2, default=str)}"

    headers = {"Content-Type": "application/json"}
    if settings.effective_llm_api_key:
        headers["Authorization"] = f"Bearer {settings.effective_llm_api_key}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.llm_api_url.rstrip('/')}/v1/chat/completions",
            headers=headers,
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.6,
                "max_tokens": 1024,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    # Clean markdown formatting if present
    content_clean = content.strip()
    if content_clean.startswith("```"):
        content_clean = re.sub(r"^```(?:json)?\n?", "", content_clean, flags=re.IGNORECASE)
        content_clean = re.sub(r"\n?```$", "", content_clean)

    # Find the opening brace of JSON object
    start_idx = content_clean.find("{")
    if start_idx == -1:
        raise ValueError("LLM response did not contain JSON object '{'")

    try:
        parsed, _ = json.JSONDecoder().raw_decode(content_clean[start_idx:])
    except json.JSONDecodeError:
        json_match = re.search(r"\{[\s\S]*?\}", content_clean)
        if not json_match:
            raise ValueError("Failed to parse JSON from LLM response")
        parsed = json.loads(json_match.group())

    return AgentAnalysis(
        root_cause=parsed.get("root_cause", ""),
        confidence=float(parsed.get("confidence", 0.7)),
        remediation_steps=parsed.get("remediation_steps", []),
        reasoning=parsed.get("reasoning", ""),
    )
