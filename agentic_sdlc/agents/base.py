"""Base agent.

Each agent is a thin, single-responsibility unit: build a prompt, call the LLM
with a stage ``tag``, parse the JSON, and validate it into a typed model. All
the error handling lives here so the concrete agents stay declarative.
"""

from __future__ import annotations

from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import Settings
from ..llm import LLMClient
from ..llm.jsonio import extract_json
from ..logging_config import get_logger

T = TypeVar("T", bound=BaseModel)


class AgentError(RuntimeError):
    pass


class BaseAgent:
    #: Human-readable name used in logs.
    name: str = "agent"

    def __init__(self, llm: LLMClient, settings: Settings,
                 run_id: str | None = None) -> None:
        self.llm = llm
        self.settings = settings
        self.log = get_logger(f"agent.{self.name}", run_id)

    def _complete_model(
        self,
        *,
        system: str,
        user: str,
        tag: str,
        schema: Type[T],
        use_planner: bool = False,
    ) -> T:
        """Call the LLM and parse the response into ``schema``."""
        model = self.settings.planner_model if use_planner else self.settings.model
        raw = self.llm.complete(system=system, user=user, tag=tag, model=model)
        try:
            data = extract_json(raw)
            return schema.model_validate(data)
        except (ValidationError, ValueError) as exc:
            raise AgentError(
                f"[{self.name}] failed to parse/validate model output for "
                f"tag '{tag}': {exc}"
            ) from exc

    def _complete_text(self, *, system: str, user: str, tag: str) -> str:
        return self.llm.complete(system=system, user=user, tag=tag,
                                 model=self.settings.model)
