"""Translate A2A tasks into MetaBaseAgent or MetaAgentTeam executions."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext, SimpleRequestContextBuilder
from a2a.server.context import ServerCallContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskStore, TaskUpdater
from a2a.types import ListTasksRequest, Part, SendMessageRequest, Task, TaskState, TaskStatus
from a2a.utils.errors import InvalidParamsError
from google.protobuf.json_format import MessageToDict
from openjiuwen.core.single_agent.schema.agent_result import Part as NativePart
from openjiuwen.extensions.a2a.a2a_transformer import A2ATransformer

from agentworker.team import TeamEvent, TeamWorker
from meta_agent import AgentEvent, MetaBaseAgent
from meta_agent.errors import MetaAgentError

logger = logging.getLogger(__name__)


class MetaAgentExecutor(AgentExecutor):
    def __init__(self, agent: MetaBaseAgent | TeamWorker, *, durable: bool, digest: str) -> None:
        self.agent = agent
        self.durable = durable
        self.digest = digest
        self.running: dict[str, asyncio.Task[Any]] = {}
        self.paused: dict[str, str] = {}

    def context_digest(self, session_id: str) -> str:
        return (
            self.agent.context_digest(session_id)
            if isinstance(self.agent, TeamWorker)
            else self.digest
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        assert context.message is not None and context.task_id and context.context_id
        task_id, session_id = context.task_id, context.context_id
        updater = TaskUpdater(event_queue, task_id, session_id)
        current = asyncio.current_task()
        assert current is not None
        self.running[task_id] = current
        try:
            saved = context.current_task
            if saved is None:
                await event_queue.enqueue_event(
                    Task(
                        id=task_id,
                        context_id=session_id,
                        status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                        history=[context.message],
                        metadata={
                            "package_digest": self.context_digest(session_id),
                            "durable": self.durable,
                        },
                    )
                )
            await updater.start_work()
            request_id = context.message.message_id
            if not request_id.strip():
                raise MetaAgentError("META_ID_REQUIRED", "A2A messageId is required")
            # Only typed text/answer is accepted. Message metadata cannot supply
            # trusted routing context, permissions, session or request identity.
            query: Any = context.get_user_input()
            metadata = MessageToDict(context.message.metadata)
            pending = (
                saved is not None and saved.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
            )
            if pending and "answer" in metadata:
                query = metadata["answer"]
            if self.durable and pending and isinstance(self.agent, MetaBaseAgent):
                result = await self.agent.resume(
                    session_id=session_id, request_id=request_id, answer=query
                )
                await self._finish(updater, asdict(result))
            else:
                events: AsyncIterator[AgentEvent | TeamEvent]
                if isinstance(self.agent, TeamWorker):
                    previous = None
                    if self.durable and pending:
                        assert saved is not None
                        artifact = next(
                            a for a in saved.artifacts if a.artifact_id == "meta-result"
                        )
                        previous = MessageToDict(artifact.parts[0].data)
                    events = self.agent.stream(
                        query, session_id=session_id, request_id=request_id, previous=previous
                    )
                else:
                    events = self.agent.stream(query, session_id=session_id, request_id=request_id)
                async for event in events:
                    if event.type == "member_result":
                        await updater.add_artifact(
                            [A2ATransformer.to_a2a_part(NativePart(data=event.data))],
                            artifact_id="member-" + event.data["member"],
                            append=True,
                        )
                    elif event.type == "delta":
                        await updater.add_artifact(
                            [Part(text=event.data["content"])],
                            artifact_id="output",
                            append=True,
                        )
                    else:
                        await self._finish(
                            updater, {**event.data, "identity": event.identity.as_dict()}
                        )
        except asyncio.CancelledError:
            await updater.cancel()
            raise
        except Exception as error:
            code = error.code if isinstance(error, MetaAgentError) else "META_A2A_EXECUTION"
            logger.warning("A2A task failed (%s)", code)
            await updater.failed(updater.new_agent_message([Part(text=code)]))
        finally:
            self.running.pop(task_id, None)

    async def _finish(self, updater: TaskUpdater, result: dict[str, Any]) -> None:
        # Replace delta accumulation with the canonical final answer.
        await updater.add_artifact(
            [Part(text=result["output"])], artifact_id="output", append=False, last_chunk=True
        )
        data = A2ATransformer.to_a2a_part(NativePart(data=result))
        await updater.add_artifact([data], artifact_id="meta-result", last_chunk=True)
        message = updater.new_agent_message([data])
        if result["result_type"] == "input_required":
            self.paused[updater.context_id] = updater.task_id
            await updater.requires_input(message)
        elif result["result_type"] == "error":
            self.paused.pop(updater.context_id, None)
            await updater.failed(message)
        else:
            self.paused.pop(updater.context_id, None)
            await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Await agent/team stream cleanup before reporting cancellation.
        running = self.running.get(context.task_id or "")
        if running is not None:
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
        else:
            if isinstance(self.agent, TeamWorker) and context.context_id:
                await self.agent.abort(context.context_id)
                self.paused.pop(context.context_id, None)
            await TaskUpdater(event_queue, context.task_id or "", context.context_id or "").cancel()

    async def aclose(self) -> None:
        tasks = list(self.running.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class WorkerContextBuilder(SimpleRequestContextBuilder):
    """Check continuation identity before the SDK starts changing task state."""

    def __init__(self, executor: MetaAgentExecutor, store: TaskStore) -> None:
        super().__init__()
        self.executor = executor
        self.store = store

    async def build(
        self,
        context: ServerCallContext,
        params: SendMessageRequest | None = None,
        task_id: str | None = None,
        context_id: str | None = None,
        task: Task | None = None,
    ) -> RequestContext:
        if params is not None and not params.message.message_id.strip():
            raise InvalidParamsError("messageId is required")
        if task is not None:
            if task_id in self.executor.running:
                raise InvalidParamsError("Task is already running; query its status")
            if context_id and context_id != task.context_id:
                raise InvalidParamsError("Task belongs to another context")
            context_id = task.context_id
            metadata = MessageToDict(task.metadata)
            if metadata.get("package_digest") != self.executor.context_digest(context_id):
                raise InvalidParamsError("Task requires its original package")
            if metadata.get("durable") != self.executor.durable:
                raise InvalidParamsError("Task requires its original recovery mode")
            if task.status.state != TaskState.TASK_STATE_INPUT_REQUIRED:
                raise InvalidParamsError("Task is not waiting for input; query its status")
            if not self.executor.durable and self.executor.paused.get(context_id) != task_id:
                raise InvalidParamsError("Restarted interaction requires LocalRecovery")
            # The per-request handler has appended this message to task.history.
            if params and any(m.message_id == params.message.message_id for m in task.history[:-1]):
                raise InvalidParamsError("messageId was already used; query the task")
        elif context_id in self.executor.paused:
            raise InvalidParamsError("Continue the pending task using taskId")
        elif context_id and self.executor.durable and isinstance(self.executor.agent, TeamWorker):
            pending_tasks = await self.store.list(
                ListTasksRequest(
                    context_id=context_id, status=TaskState.TASK_STATE_INPUT_REQUIRED, page_size=1
                ),
                context,
            )
            if pending_tasks.tasks:
                raise InvalidParamsError("Continue the pending task using taskId")
        return await super().build(context, params, task_id, context_id, task)
