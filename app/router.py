from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = PROJECT_ROOT / "micro_ai_shelf" / "default" / "tasks"


@dataclass(frozen=True)
class TaskRoute:
    task_id: str
    label: str
    pipeline: list[str]
    reason: str
    mode: str = "pipeline"


class TaskRouter:
    """Tiny resident router that chooses which saved micro AIs to wake up."""

    def __init__(self, task_dir: Path = TASK_DIR) -> None:
        self.task_dir = task_dir
        self.tasks = self._load_tasks()

    def route(self, text: str) -> TaskRoute | None:
        normalized = text.lower()
        best_task: dict | None = None
        best_score = 0
        best_hits: list[str] = []

        for task in self.tasks:
            hits = [word for word in task["keywords"] if word.lower() in normalized]
            score = len(hits)
            if score > best_score:
                best_score = score
                best_task = task
                best_hits = hits

        if best_task is None or best_score == 0:
            return None

        return TaskRoute(
            task_id=best_task["id"],
            label=best_task["label"],
            pipeline=list(best_task["pipeline"]),
            reason=f"入力に {', '.join(best_hits)} が含まれていたため",
            mode=str(best_task.get("mode", "pipeline")),
        )

    def describe_available_tasks(self) -> str:
        if not self.tasks:
            return "使えるタスクAIはまだ登録されていません。"
        labels = " / ".join(task["label"] for task in self.tasks)
        return f"今の棚にあるタスクAI: {labels}"

    def _load_tasks(self) -> list[dict]:
        tasks: list[dict] = []
        for path in sorted(self.task_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self._validate_task(data, path)
            tasks.append(data)
        return tasks

    def _validate_task(self, data: dict, path: Path) -> None:
        required = ("id", "label", "keywords", "pipeline")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"{path} に必須項目がありません: {', '.join(missing)}")
        if not isinstance(data["keywords"], list) or not all(isinstance(item, str) for item in data["keywords"]):
            raise ValueError(f"{path} の keywords は文字列配列にしてください。")
        if not isinstance(data["pipeline"], list) or not all(isinstance(item, str) for item in data["pipeline"]):
            raise ValueError(f"{path} の pipeline は小型AI名の配列にしてください。")
