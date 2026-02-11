"""OpenAI LLM client for structured output."""

from __future__ import annotations

import asyncio

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


class LLMService:
    """Wrapper around ChatOpenAI with structured output support."""

    def __init__(self, api_key: str, model: str, *, timeout_seconds: float = 60.0) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.chat = ChatOpenAI(
            api_key=api_key, model=model, temperature=0, timeout=self.timeout_seconds
        )

    async def structured(
        self,
        messages: list[BaseMessage],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Get structured output from LLM."""
        chain = self.chat.with_structured_output(output_schema)
        try:
            return await asyncio.wait_for(
                chain.ainvoke(messages), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"OpenAI request timed out after {self.timeout_seconds:.0f}s"
            ) from e