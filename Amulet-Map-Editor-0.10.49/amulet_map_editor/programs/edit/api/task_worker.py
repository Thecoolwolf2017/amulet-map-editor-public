import queue
import threading
import time
from dataclasses import dataclass, field
from types import GeneratorType
from typing import Any, Callable, Optional

from amulet_map_editor.programs.edit.api.operations.errors import OperationSilentAbort


OperationType = Callable[[], Any]


@dataclass
class Task:
    operation: OperationType
    message: str
    progress: float = 0.0
    result: Any = None
    error: Optional[BaseException] = None
    done: bool = False
    cancelled: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update(self, progress: Optional[float] = None, message: Optional[str] = None):
        with self._lock:
            if progress is not None:
                self.progress = progress
            if message is not None:
                self.message = message

    def cancel(self):
        with self._lock:
            self.cancelled = True


class TaskWorker:
    _shared = None
    _shared_lock = threading.Lock()

    def __init__(self):
        self._queue: "queue.Queue[Task]" = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @classmethod
    def shared(cls) -> "TaskWorker":
        with cls._shared_lock:
            if cls._shared is None:
                cls._shared = cls()
            return cls._shared

    def submit(self, operation: OperationType, message: str) -> Task:
        task = Task(operation=operation, message=message)
        self._queue.put(task)
        return task

    def _run_task(self, task: Task):
        try:
            obj = task.operation()
            if isinstance(obj, GeneratorType):
                while True:
                    if task.cancelled:
                        raise OperationSilentAbort
                    progress = next(obj)
                    if isinstance(progress, (list, tuple)):
                        if len(progress) >= 2:
                            task.update(message=progress[1])
                        if len(progress) >= 1 and isinstance(progress[0], (int, float)):
                            task.update(progress=progress[0])
                    elif isinstance(progress, (int, float)):
                        task.update(progress=progress)
        except StopIteration as e:
            task.result = e.value
        except BaseException as e:
            task.error = e
        finally:
            task.done = True

    def _run(self):
        while True:
            task = self._queue.get()
            try:
                self._run_task(task)
            finally:
                self._queue.task_done()
            time.sleep(0.01)
