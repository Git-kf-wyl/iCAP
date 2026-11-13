"""Public native Checkpointer/Store adapter with atomic, fenced snapshots.

Pickle is the pinned kernel's local state format. The database must be trusted;
checksums detect damage, not malicious replacement. No private kernel state is
read or changed. Native graph snapshots exist at error/interaction boundaries.
"""

from __future__ import annotations

import pickle
from contextvars import ContextVar
from dataclasses import replace
from typing import Any

from openjiuwen.core.common.constants.constant import INTERACTIVE_INPUT
from openjiuwen.core.graph.store import GraphState, Store
from openjiuwen.core.session import InteractiveInput, NodeSession
from openjiuwen.core.session.checkpointer import CheckpointerFactory, CheckpointerProvider
from openjiuwen.core.session.checkpointer.base import Checkpointer

from meta_agent.checkpoint.executor import SideEffectExecutor
from meta_agent.errors import RecoveryConflict


class NativeRun:
    def __init__(
        self,
        executor: SideEffectExecutor,
        child_id: str,
        workflow_id: str,
        input_id: str | None = None,
        subagent_names: tuple[str, ...] = (),
    ) -> None:
        self.executor = executor
        self.child_id, self.workflow_id = child_id, workflow_id
        self.workflow: Any = None
        self.graphs: dict[str, GraphState] = {}
        self.input_id = input_id
        self.agent_state: Any = None
        self.subagent_names = subagent_names
        self.subagent_states: dict[str, Any] = {}
        self.interrupted_subagents: set[str] = set()

    async def load(self, name: str) -> Any:
        guard = self.executor.guard
        await guard.check()
        content = await guard.store.load_checkpoint(guard.scope, self.executor.execution_id, name)
        if content is None:
            return None
        try:
            return pickle.loads(content)
        except Exception as error:
            raise RecoveryConflict(
                "META_CHECKPOINT_CORRUPT", "Cannot decode native checkpoint"
            ) from error

    async def save(self, name: str, value: Any) -> None:
        guard = self.executor.guard
        try:
            content = pickle.dumps(value, protocol=5)
        except Exception as error:
            raise RecoveryConflict(
                "META_CHECKPOINT_ENCODING", "Cannot serialize native state"
            ) from error
        await guard.store.save_checkpoint(guard.current, self.executor.execution_id, name, content)

    async def save_child(self, result: dict[str, Any]) -> None:
        # Commit L2 and its bridge outcome together. A crash before this commit
        # restores the prior L2 and reuses only that snapshot's approval answer.
        if self.agent_state is None:
            raise RecoveryConflict("META_NATIVE_STATE", "Child did not commit native state")
        guard = self.executor.guard
        await guard.store.save_checkpoints(
            guard.current,
            self.executor.execution_id,
            {
                "agent": pickle.dumps(self.agent_state, protocol=5),
                "child_result": pickle.dumps(
                    {"result": result, "input_id": self.input_id}, protocol=5
                ),
                "subagents": pickle.dumps(self.subagent_states, protocol=5),
            },
        )

    def clear_child_answer(self, node_id: str) -> None:
        # A fresh bridge invocation must not reuse the previous question's input.
        node = NodeSession(self.workflow, node_id)
        node.state().update({INTERACTIVE_INPUT: []})
        node.state().commit_cmp()

    def check_session(self, session_id: str, *, agent: bool = False) -> None:
        expected = self.child_id if agent else self.workflow_id
        if session_id != expected and not (agent and self.is_subagent(session_id)):
            raise RecoveryConflict(
                "META_NATIVE_SCOPE", "Native session is outside the leased execution"
            )

    def is_subagent(self, session_id: str) -> bool:
        # Pinned native TaskTool namespaces child sessions under their parent.
        return any(
            session_id == f"{self.child_id}_sub_{name}"
            or session_id.startswith(f"{self.child_id}_sub_{name}_")
            for name in self.subagent_names
        )


NATIVE_RUN: ContextVar[NativeRun | None] = ContextVar("meta_native_run", default=None)


def current_native_run() -> NativeRun:
    run = NATIVE_RUN.get()
    if run is None:
        raise RecoveryConflict("META_NATIVE_CONTEXT", "Native checkpoints require a managed lease")
    return run


class FencedGraphStore(Store):  # type: ignore[misc]
    async def get(self, session_id: str, ns: str) -> Any:
        run = current_native_run()
        run.check_session(session_id)
        await run.executor.guard.check()
        return run.graphs.get(ns)

    async def save(self, session_id: str, ns: str, state: Any) -> None:
        run = current_native_run()
        run.check_session(session_id)
        if run.workflow is None or not isinstance(state, GraphState):
            raise RecoveryConflict("META_NATIVE_STATE", "Missing workflow or invalid graph state")
        # Exception objects can refer to dynamically imported plugin classes.
        # Rescheduling needs node names/status, never old exception instances.
        clean = replace(
            state, pending_node={k: replace(v, exception=[]) for k, v in state.pending_node.items()}
        )
        graphs = {**run.graphs, ns: clean}
        await run.save(
            "workflow",
            {
                "state": run.workflow.state().get_state(copied=True),
                "updates": run.workflow.state().get_updates(),
                "graphs": graphs,
                "input_id": run.input_id,
            },
        )
        run.graphs = graphs

    async def delete(self, session_id: str, ns: str | None = None) -> None:
        raise RecoveryConflict(
            "META_NATIVE_RETENTION", "Runtime checkpoints are retained for explicit recovery"
        )


class FencedCheckpointer(Checkpointer):  # type: ignore[misc]
    async def pre_workflow_execute(self, session: Any, inputs: Any) -> None:
        run = current_native_run()
        run.check_session(session.session_id())
        if session.workflow_id() != run.workflow_id:
            raise RecoveryConflict("META_NATIVE_SCOPE", "Unsupported independent nested workflow")
        run.workflow = session
        saved = await run.load("workflow")
        if saved is not None:
            if not isinstance(saved, dict) or set(saved) != {
                "state",
                "updates",
                "graphs",
                "input_id",
            }:
                raise RecoveryConflict("META_CHECKPOINT_CORRUPT", "Invalid workflow snapshot")
            if not isinstance(saved["graphs"], dict) or not all(
                isinstance(s, GraphState) for s in saved["graphs"].values()
            ):
                raise RecoveryConflict("META_CHECKPOINT_CORRUPT", "Invalid graph snapshot")
            session.state().set_state(saved["state"])
            run.graphs = saved["graphs"]
            if isinstance(inputs, InteractiveInput) and saved["input_id"] != run.input_id:
                if inputs.raw_inputs is not None:
                    session.state().update_and_commit_workflow_state(
                        {INTERACTIVE_INPUT: inputs.raw_inputs}
                    )
                for node_id, value in inputs.user_inputs.items():
                    node = NodeSession(session, node_id)
                    prior = node.state().get(INTERACTIVE_INPUT)
                    node.state().update(
                        {INTERACTIVE_INPUT: [*(prior if isinstance(prior, list) else []), value]}
                    )
                session.state().commit()
            session.state().set_updates(saved["updates"])

    async def post_workflow_execute(self, session: Any, result: Any, exception: Any) -> None:
        # graph.save already committed graph position and workflow state together.
        # In particular, native cancellation calls this hook with an empty result;
        # it must not erase the last durable checkpoint or commit partial state.
        await current_native_run().executor.guard.check()
        if exception is not None:
            raise exception

    async def pre_agent_execute(self, session: Any, inputs: Any) -> None:
        if NATIVE_RUN.get() is None:
            from meta_agent.team.recovery import TEAM_RECOVERY

            if team := TEAM_RECOVERY.get():
                await team.restore(session, inputs, team=False)
                return
        run = current_native_run()
        run.check_session(session.session_id(), agent=True)
        if run.is_subagent(session.session_id()):
            saved = run.subagent_states.get(session.session_id())
        else:
            run.subagent_states = await run.load("subagents") or {}
            saved = await run.load("agent")
        if saved is not None:
            if not isinstance(saved, dict):
                raise RecoveryConflict("META_CHECKPOINT_CORRUPT", "Invalid agent snapshot")
            session.state().set_state(saved)
        if inputs is not None:
            session.state().update({INTERACTIVE_INPUT: [inputs]})

    async def post_agent_execute(self, session: Any) -> None:
        if NATIVE_RUN.get() is None:
            from meta_agent.team.recovery import TEAM_RECOVERY

            if team := TEAM_RECOVERY.get():
                await team.persist(session, team=False)
                return
        run = current_native_run()
        run.check_session(session.session_id(), agent=True)
        await run.executor.guard.check()
        state = session.state().get_state(copied=True)
        if run.is_subagent(session.session_id()):
            run.subagent_states[session.session_id()] = state
        else:
            run.agent_state = state

    async def interrupt_agent_execute(self, session: Any) -> None:
        await self.post_agent_execute(session)

    async def pre_agent_team_execute(self, session: Any, inputs: Any) -> None:
        from meta_agent.team.recovery import TEAM_RECOVERY

        if team := TEAM_RECOVERY.get():
            await team.restore(session, inputs, team=True)
            return
        raise RecoveryConflict("META_TEAM_UNSUPPORTED", "Team recovery is not enabled")

    async def post_agent_team_execute(self, session: Any) -> None:
        from meta_agent.team.recovery import TEAM_RECOVERY

        if team := TEAM_RECOVERY.get():
            await team.persist(session, team=True)
            return
        raise RecoveryConflict("META_TEAM_UNSUPPORTED", "Team recovery is not enabled")

    async def session_exists(self, session_id: str) -> bool:
        if NATIVE_RUN.get() is None:
            from meta_agent.team.recovery import TEAM_RECOVERY

            if team := TEAM_RECOVERY.get():
                return await team.exists(session_id)
        run = current_native_run()
        if run.is_subagent(session_id):
            return session_id in run.subagent_states
        if session_id not in {run.workflow_id, run.child_id}:
            raise RecoveryConflict("META_NATIVE_SCOPE", "Native session is outside the lease")
        return await run.load("agent" if session_id == run.child_id else "workflow") is not None

    async def release(self, session_id: str) -> None:
        if NATIVE_RUN.get() is None:
            from meta_agent.team.recovery import TEAM_RECOVERY

            if TEAM_RECOVERY.get() is not None:
                return  # Team handoff retains its outer harness envelopes.
        raise RecoveryConflict("META_NATIVE_RETENTION", "Closing an agent retains recovery state")

    def graph_store(self) -> Any:
        return FencedGraphStore()


@CheckpointerFactory.register("meta_local_recovery")
class FencedCheckpointerProvider(CheckpointerProvider):  # type: ignore[misc]
    async def create(self, conf: dict[str, Any]) -> FencedCheckpointer:
        return FencedCheckpointer()
