"""agent_mcp background work: one external agent's Janus turn (janus_door.py)."""

from __future__ import annotations

from celery import shared_task


@shared_task(name='agent_mcp.janus_turn', time_limit=420, soft_time_limit=390)
def janus_turn(turn_id: str, message: str) -> str:
    """Run a turn an external agent queued with janus.ask / askJanus."""
    from plugins.installed.agent_mcp.janus_door import run

    return run(turn_id, message)
