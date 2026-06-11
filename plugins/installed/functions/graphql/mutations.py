"""GraphQL mutations for the Functions plugin."""

from __future__ import annotations

import json

import strawberry

from api.graphql_permissions import (
    PermissionDenied,
    has_scope,
    require_authenticated,
)


@strawberry.type
class FunctionRunOutput:
    success: bool
    output_json: str
    duration_ms: int
    error: str


@strawberry.input
class TestRunFunctionInput:
    source: str
    capabilities_csv: str = ''
    input_json: str = '{}'
    timeout_ms: int = 200


@strawberry.type
class FunctionsMutationExtension:
    @strawberry.mutation(description='Test-run a function source without persisting anything.')
    def test_run_function(
        self,
        info: strawberry.Info,
        input: TestRunFunctionInput,
    ) -> FunctionRunOutput:
        from plugins.installed.functions.runtime import (
            FunctionError,
            FunctionExecutionError,
            execute,
        )

        require_authenticated(info)
        if not has_scope(info, 'write:functions'):
            raise PermissionDenied('write:functions scope required')

        try:
            payload = json.loads(input.input_json or '{}')
        except json.JSONDecodeError as e:
            return FunctionRunOutput(
                success=False,
                output_json='null',
                duration_ms=0,
                error=f'Invalid input_json: {e}',
            )

        capabilities = [c.strip() for c in input.capabilities_csv.split(',') if c.strip()]
        try:
            result = execute(
                source=input.source,
                input=payload,
                capabilities=capabilities,
                timeout_ms=max(10, min(input.timeout_ms, 2000)),
            )
        except (FunctionError, FunctionExecutionError) as e:
            return FunctionRunOutput(
                success=False,
                output_json='null',
                duration_ms=0,
                error=str(e),
            )

        try:
            output_json = json.dumps(result.output, default=str)
        except (TypeError, ValueError) as e:
            return FunctionRunOutput(
                success=False,
                output_json='null',
                duration_ms=result.duration_ms,
                error=f'Output not JSON-serializable: {e}',
            )

        return FunctionRunOutput(
            success=True,
            output_json=output_json,
            duration_ms=result.duration_ms,
            error='',
        )
