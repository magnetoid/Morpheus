"""
Versioned prompt registry.

System prompts live as versioned `Prompt` objects so we can A/B them and
roll forward without code changes. Render uses str.format-style `{var}`
placeholders — keep prompts simple, no Jinja.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Prompt:
    name: str
    version: int
    template: str
    description: str = ''

    def render(self, **vars: object) -> str:
        try:
            return self.template.format(**vars)
        except (KeyError, IndexError) as e:
            raise ValueError(f'Prompt {self.name} v{self.version} missing var: {e}') from e


class PromptRegistry:
    def __init__(self) -> None:
        self._prompts: dict[tuple[str, int], Prompt] = {}
        self._latest: dict[str, int] = {}

    def register(self, prompt: Prompt) -> None:
        key = (prompt.name, prompt.version)
        self._prompts[key] = prompt
        self._latest[prompt.name] = max(self._latest.get(prompt.name, 0), prompt.version)

    def get(self, name: str, version: int | None = None) -> Prompt:
        v = version or self._latest.get(name)
        if v is None:
            raise KeyError(f'Unknown prompt: {name}')
        return self._prompts[(name, v)]

    def all(self) -> list[Prompt]:
        return list(self._prompts.values())


prompt_registry = PromptRegistry()
