"""GraphQL mutations: invoke an agent end-to-end through the kernel runtime."""

from __future__ import annotations

import strawberry

from core.agents import agent_registry


@strawberry.type
class AgentRunResultType:
    run_id: strawberry.ID
    state: str
    text: str
    tool_call_count: int
    prompt_tokens: int
    completion_tokens: int
    error: str


@strawberry.input
class InvokeAgentInput:
    agent_name: str
    message: str
    conversation_id: str | None = None


@strawberry.type
class AgentCoreMutationExtension:
    @strawberry.mutation(description='Invoke an agent. Synchronous; returns the full run result.')
    def invoke_agent(
        self,
        info: strawberry.Info,
        input: InvokeAgentInput,
    ) -> AgentRunResultType:
        from plugins.installed.agent_core.services import (
            history_for_conversation,
            run_agent,
        )

        if agent_registry.get_agent(input.agent_name) is None:
            return AgentRunResultType(
                run_id=strawberry.ID(''),
                state='failed',
                text='',
                tool_call_count=0,
                prompt_tokens=0,
                completion_tokens=0,
                error=f'Unknown agent: {input.agent_name}',
            )

        request = getattr(info.context, 'request', None) or (
            info.context.get('request') if isinstance(info.context, dict) else None
        )

        # Same posture as the REST twin (invoke_agent_view): audience gate +
        # per-caller rate limit. Without these, this mutation was an
        # unauthenticated, unthrottled LLM-cost surface.
        def _denied(msg):
            return AgentRunResultType(
                run_id=strawberry.ID(''),
                state='failed',
                text='',
                tool_call_count=0,
                prompt_tokens=0,
                completion_tokens=0,
                error=msg,
            )

        agent = agent_registry.get_agent(input.agent_name)
        if agent.audience == 'system':
            return _denied('System agents cannot be invoked via the API.')
        if agent.audience == 'merchant':
            user = getattr(request, 'user', None) if request else None
            if not (user and getattr(user, 'is_authenticated', False) and user.is_staff):
                return _denied('Staff authentication required for this agent.')

        if request is not None:  # no request = trusted internal call
            from core.utils.rate_limit import RateLimitExceeded, check_and_consume  # noqa: PLC0415
            from plugins.installed.agent_core.views import _agent_rate_key  # noqa: PLC0415

            try:
                check_and_consume(
                    key=_agent_rate_key(request), max_per_window=20, window_seconds=60
                )
            except RateLimitExceeded:
                return _denied('Agent rate limit exceeded — try again shortly.')

        history = history_for_conversation(input.conversation_id) if input.conversation_id else None
        try:
            result = run_agent(
                agent_name=input.agent_name,
                user_message=input.message[:10_000],
                customer=getattr(request, 'user', None) if request else None,
                session_key=getattr(getattr(request, 'session', None), 'session_key', '') or ''
                if request
                else '',
                history=history,
                context={'request': request} if request else {},
                conversation_id=input.conversation_id,
            )
        except Exception as e:  # noqa: BLE001
            return AgentRunResultType(
                run_id=strawberry.ID(''),
                state='failed',
                text='',
                tool_call_count=0,
                prompt_tokens=0,
                completion_tokens=0,
                error=str(e),
            )
        return AgentRunResultType(
            run_id=strawberry.ID(result.run_id),
            state=result.state,
            text=result.text,
            tool_call_count=result.tool_calls,
            prompt_tokens=result.trace.prompt_tokens,
            completion_tokens=result.trace.completion_tokens,
            error=result.error or '',
        )
