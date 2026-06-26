"""
ACU - Agente Cognitivo Universal
Autonomous Cognitive Universal Agent Orchestrator
"""

__version__ = "1.0.0"
__author__ = "RevoxeTech AI"
__description__ = "Autonomous Cognitive Universal Agent with ReAct Pattern"

__all__ = ["ACUAgent", "get_agent"]


def __getattr__(name):
    """Load agent exports lazily to avoid heavy imports for lightweight modules."""
    if name in __all__:
        from src.agent.agent_loop import ACUAgent, get_agent

        exports = {
            "ACUAgent": ACUAgent,
            "get_agent": get_agent,
        }
        return exports[name]
    raise AttributeError(f"module 'src' has no attribute {name!r}")
