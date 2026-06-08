"""Reliable structured LLM output engine."""
from pydantic import BaseModel, ValidationError
from langchain_google_vertexai import ChatVertexAI
from langchain_core.output_parsers import PydanticOutputParser
from typing import Type, TypeVar, Optional
import json

T = TypeVar("T", bound=BaseModel)

class StructuredOutputEngine:
    def __init__(self, max_retries: int = 3):
        self.llm = ChatVertexAI(model_name="gemini-1.5-flash-002", temperature=0)
        self.max_retries = max_retries
        self.stats = {"success": 0, "retry": 0, "fallback": 0, "failure": 0}

    def extract(self, prompt: str, schema: Type[T], context: str = "") -> Optional[T]:
        parser = PydanticOutputParser(pydantic_object=schema)
        format_instructions = parser.get_format_instructions()
        full_prompt = f"{context}\n\n{prompt}\n\n{format_instructions}"
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.llm.invoke(full_prompt).content
                # Clean response
                if "```json" in response: response = response.split("```json")[1].split("```")[0]
                elif "```" in response: response = response.split("```")[1].split("```")[0]
                result = schema.model_validate(json.loads(response.strip()))
                if attempt > 0: self.stats["retry"] += 1
                else: self.stats["success"] += 1
                return result
            except (ValidationError, json.JSONDecodeError, KeyError) as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    full_prompt = f"{full_prompt}\n\nPrevious attempt failed with: {last_error}\nFix the JSON and try again. Return ONLY valid JSON matching the schema."
        self.stats["failure"] += 1
        return None

    def compliance_rate(self) -> float:
        total = sum(self.stats.values())
        failed = self.stats["failure"]
        return (total - failed) / max(total, 1) * 100
