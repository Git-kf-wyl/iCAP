"""Business-owned native Component and Workflow factory."""

from typing import Any

from openjiuwen.core.workflow import End, Start, Workflow, WorkflowCard, WorkflowComponent


class Echo(WorkflowComponent):  # type: ignore[misc]
    async def invoke(self, inputs: Any, session: Any, context: Any) -> Any:
        return {"message": inputs["query"], "payload": inputs["payload"]}


def build_workflow(context: Any) -> Any:
    graph = Workflow(card=WorkflowCard(id=context.workflow_id, name="Structured echo"))
    graph.set_start_comp(
        "start", Start(), inputs_schema={"query": "${query}", "payload": "${payload}"}
    )
    graph.add_workflow_comp(
        "echo", Echo(), inputs_schema={"query": "${start.query}", "payload": "${start.payload}"}
    )
    graph.set_end_comp(
        "end", End(), inputs_schema={"message": "${echo.message}", "payload": "${echo.payload}"}
    )
    graph.add_connection("start", "echo")
    graph.add_connection("echo", "end")
    return graph
