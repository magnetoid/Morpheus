"""GraphQL queries for the agent layer."""

from __future__ import annotations

import strawberry

from core.agents import agent_registry


@strawberry.type
class AgentInfoType:
    name: str
    label: str
    description: str
    audience: str
    icon: str
    scopes: list[str]


@strawberry.type
class AgentRunType:
    id: strawberry.ID
    agent_name: str
    state: str
    user_message: str
    final_text: str
    tool_call_count: int
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    started_at: str
    ended_at: str | None


@strawberry.type
class AgentStepType:
    seq: int
    kind: str
    name: str
    content: str
    arguments: strawberry.scalars.JSON
    output: strawberry.scalars.JSON


@strawberry.type
class AgentCoreQueryExtension:
    @strawberry.field(description='List every agent registered with the platform.')
    def agents(self) -> list[AgentInfoType]:
        return [
            AgentInfoType(
                name=a.name,
                label=a.label,
                description=a.description,
                audience=a.audience,
                icon=a.icon,
                scopes=list(a.scopes),
            )
            for a in agent_registry.all_agents()
        ]

    @strawberry.field(description='Recent agent runs (admin-only).')
    def agent_runs(
        self,
        info: strawberry.Info,
        first: int = 25,
        agent_name: str | None = None,
    ) -> list[AgentRunType]:
        request = getattr(info.context, 'request', None) or (
            info.context.get('request') if isinstance(info.context, dict) else None
        )
        user = getattr(request, 'user', None) if request else None
        if user is None or not getattr(user, 'is_staff', False):
            return []
        from plugins.installed.agent_core.models import AgentRun

        first = max(1, min(int(first or 25), 100))
        qs = AgentRun.objects.all().order_by('-started_at')
        if agent_name:
            qs = qs.filter(agent_name=agent_name)
        return [
            AgentRunType(
                id=strawberry.ID(str(r.id)),
                agent_name=r.agent_name,
                state=r.state,
                user_message=r.user_message,
                final_text=r.final_text,
                tool_call_count=r.tool_call_count,
                prompt_tokens=r.prompt_tokens,
                completion_tokens=r.completion_tokens,
                duration_ms=r.duration_ms,
                started_at=r.started_at.isoformat(),
                ended_at=r.ended_at.isoformat() if r.ended_at else None,
            )
            for r in qs[:first]
        ]

    @strawberry.field(description='Steps of a single run (admin-only).')
    def agent_run_steps(
        self,
        info: strawberry.Info,
        run_id: strawberry.ID,
    ) -> list[AgentStepType]:
        request = getattr(info.context, 'request', None) or (
            info.context.get('request') if isinstance(info.context, dict) else None
        )
        user = getattr(request, 'user', None) if request else None
        if user is None or not getattr(user, 'is_staff', False):
            return []
        from plugins.installed.agent_core.models import AgentStep

        steps = AgentStep.objects.filter(run_id=str(run_id)).order_by('seq')
        return [
            AgentStepType(
                seq=s.seq,
                kind=s.kind,
                name=s.name,
                content=s.content,
                arguments=s.arguments or {},
                output=s.output or {},
            )
            for s in steps
        ]
