import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.agents.prompt import build_report_prompt
from app.schemas.spot_on import TravelReport

logger = logging.getLogger(__name__)


class BudgetAgent(BaseAgent):
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            timeout = self.deps.settings.agent_budget_timeout
            return await self.with_timeout(
                self._run(state), timeout_seconds=timeout
            ) or {
                "travel_report": {},
                "agent_statuses": {self.agent_id: "failed"},
                "warnings": ["BudgetAgent timed out"],
            }
        except Exception as e:
            self.logger.error("BudgetAgent failed: %s", e, exc_info=True)
            return self._failed_result(str(e))

    async def _run(self, state: dict[str, Any]) -> dict[str, Any]:
        qctx = state.get("query_context", {})
        main_results = state.get("main_results", {})
        constraints = state.get("constraints", {})

        destination = qctx.get("destination_city", constraints.get("destination", ""))
        departing_date = qctx.get("departing_date", constraints.get("departing_date", ""))
        returning_date = qctx.get("returning_date", constraints.get("returning_date"))
        stay_nights = qctx.get("stay_nights")

        data_text = self._format_results(main_results)

        system_prompt = build_report_prompt(
            destination=destination,
            departing_date=departing_date,
            returning_date=returning_date,
            stay_nights=stay_nights,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Travel data:\n\n{data_text}"),
        ]

        try:
            report = await self.deps.llm.structured(messages, TravelReport)
            report_dict = report.model_dump()

            self.logger.info(
                "BudgetAgent completed: budget=%s",
                report.total_estimated_budget,
                extra={"run_id": state.get("runId")},
            )

            final_output = {
                **main_results,
                "constraints": constraints,
                "references": state.get("references", []),
                "report": report_dict,
            }

            return {
                "travel_report": report_dict,
                "final_output": final_output,
                "status": "done",
                "agent_statuses": {self.agent_id: "completed"},
            }
        except Exception as e:
            self.logger.error("BudgetAgent LLM call failed: %s", e, exc_info=True)
            final_output = {
                **main_results,
                "constraints": constraints,
                "references": state.get("references", []),
            }
            return {
                "travel_report": {},
                "final_output": final_output,
                "status": "done",
                "agent_statuses": {self.agent_id: "failed"},
                "warnings": [f"BudgetAgent LLM failed: {e}"],
            }

    @staticmethod
    def _format_results(main_results: dict[str, list[dict[str, Any]]]) -> str:
        """Format main_results into a structured text block for LLM input."""
        sections: list[str] = []

        for category, items in main_results.items():
            if not items:
                continue
            section_lines = [f"## {category.replace('_', ' ').title()} ({len(items)} items)"]
            for item in items:
                clean = {k: v for k, v in item.items() if v not in (None, "", [], {})}
                section_lines.append(json.dumps(clean, indent=2))
            sections.append("\n".join(section_lines))

        return "\n\n".join(sections)
