"""Task Manager — tarefas longas com estado, plano e cancelamento.

Uma Task tem: id, objetivo, estado, plano (passos), progresso, logs, ferramentas
usadas, provedor, resultado, erros e timestamps. Publica eventos no Event Bus
(task.*), que o tracker/UI observam. NÃO executa nada sozinho — o engine dirige
a execução; aqui é só o estado e a orquestração.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aila.core.event_bus import EventBus


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


_TERMINAL = {TaskState.FAILED, TaskState.COMPLETED, TaskState.CANCELLED}


@dataclass(slots=True)
class Step:
    description: str
    status: str = "pending"   # pending | running | done | failed
    result: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"description": self.description, "status": self.status,
                "result": self.result[:400]}


@dataclass(slots=True)
class Task:
    id: str
    goal: str
    state: TaskState = TaskState.PENDING
    plan: list[Step] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    provider: str | None = None
    result: str = ""
    error: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    cancelled: bool = False   # flag cooperativa (checada entre passos)

    @property
    def progress(self) -> float:
        if not self.plan:
            return 0.0
        done = sum(1 for s in self.plan if s.status in ("done", "failed"))
        return round(done / len(self.plan), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "goal": self.goal, "state": str(self.state),
            "progress": self.progress, "plan": [s.to_dict() for s in self.plan],
            "tools_used": self.tools_used, "provider": self.provider,
            "result": self.result[:2000], "error": self.error,
            "logs": self.logs[-30:], "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TaskManager:
    def __init__(self, bus: EventBus | None = None, capacity: int = 50) -> None:
        self.bus = bus
        self._tasks: dict[str, Task] = {}
        self._order: list[str] = []
        self.capacity = capacity

    async def _publish(self, etype: str, task: Task) -> None:
        if self.bus is None:
            return
        try:
            await self.bus.emit(etype, {"id": task.id, "state": str(task.state),
                                        "goal": task.goal[:80], "progress": task.progress},
                                source="tasks")
        except Exception:  # noqa: BLE001 - o bus nunca deve quebrar uma tarefa
            pass

    async def create(self, goal: str) -> Task:
        task = Task(id=uuid.uuid4().hex[:8], goal=goal.strip())
        self._tasks[task.id] = task
        self._order.append(task.id)
        while len(self._order) > self.capacity:            # descarta as mais antigas
            self._tasks.pop(self._order.pop(0), None)
        await self._publish("task.created", task)
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list(self) -> list[Task]:
        return [self._tasks[i] for i in self._order if i in self._tasks]

    async def set_state(self, task: Task, state: TaskState, error: str = "") -> None:
        task.state = state
        task.updated_at = _now()
        if error:
            task.error = error
        await self._publish("task.state", task)

    def log(self, task: Task, msg: str) -> None:
        task.logs.append(f"{_now()} · {msg}")

    async def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None or task.state in _TERMINAL:
            return False
        task.cancelled = True
        await self.set_state(task, TaskState.CANCELLED)
        return True
