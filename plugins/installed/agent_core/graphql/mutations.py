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
