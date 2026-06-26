"""Agent runtime helpers shared by API routes."""

from typing import Optional

from fastapi import FastAPI, HTTPException


async def get_initialized_agent(
    api: FastAPI, domain: str, persona: str, session_id: Optional[str] = None
):
    """Return an initialized agent or raise an HTTP 503."""
    agent = await api.state.agent_provider(domain=domain, persona=persona)
    if getattr(agent, "system_prompt", None):
        return agent

    initialized = await agent.initialize(session_id=session_id)
    if not initialized:
        raise HTTPException(
            status_code=503,
            detail="No se pudo inicializar el agente ACU",
        )
    return agent
