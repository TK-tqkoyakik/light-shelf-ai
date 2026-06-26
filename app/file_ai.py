from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .micro_ai import MicroAgentRunner


@dataclass(frozen=True)
class FileItem:
    name: str
    extension: str
    size_bytes: int
    modified: str


def collect_file_items(folder: Path, limit: int = 200) -> list[FileItem]:
    items: list[FileItem] = []
    for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        stat = path.stat()
        items.append(
            FileItem(
                name=path.name,
                extension=path.suffix.lower(),
                size_bytes=stat.st_size,
                modified=str(int(stat.st_mtime)),
            )
        )
        if len(items) >= limit:
            break
    return items


class FileOrganizerAI:
    def __init__(self, runner: MicroAgentRunner | None = None) -> None:
        self.runner = runner or MicroAgentRunner()

    def make_plan(self, folder: Path, pipeline: list[str] | None = None) -> dict:
        items = collect_file_items(folder)
        if not items:
            return {"folders": [], "moves": [], "renames": [], "reason": "整理対象のファイルがありません。"}

        pipeline = pipeline or ["file_sort_planner", "file_sort_reviewer"]
        if pipeline != ["file_sort_planner", "file_sort_reviewer"]:
            raise ValueError(f"ファイル整理で使えない小型AIパイプラインです: {' → '.join(pipeline)}")

        payload = {"files": [item.__dict__ for item in items]}
        plan = self.runner.run_json(pipeline[0], payload)
        review = self.runner.run_json(pipeline[1], {"files": payload["files"], "plan": plan})
        if review.get("approved") is not True:
            raise ValueError(f"チェックAIが整理案を止めました: {review.get('notes', '理由なし')}")
        if review.get("notes") and isinstance(plan.get("reason"), str):
            plan["reason"] = f"{plan['reason']} / チェック: {review['notes']}"
        return plan


def build_prompt(items: list[FileItem]) -> str:
    files_json = json.dumps([item.__dict__ for item in items], ensure_ascii=False, indent=2)
    return f"""
あなたは「フォルダ整理案を作るだけ」の専用AIです。
雑談、質問回答、コード作成、削除、フォルダ外操作、自動実行は禁止です。
ファイル本文は見ていません。ファイル名、拡張子、サイズ、更新日時だけで判断してください。

必ず次のJSONだけを返してください。説明文やMarkdownは禁止です。
{{
  "folders": ["作成するフォルダ名"],
  "moves": [{{"source": "元ファイル名", "destination": "フォルダ名/元ファイル名"}}],
  "renames": [{{"source": "元ファイル名", "destination": "新ファイル名"}}],
  "reason": "短い理由"
}}

ルール:
- 削除は禁止。
- source は必ず一覧にあるファイル名だけ。
- destination は相対パスだけ。
- 絶対パス、..、ドライブ名は禁止。
- フォルダ名とファイル名はWindowsで安全な名前にする。
- 自信がなければ空の配列を返す。

ファイル一覧:
{files_json}
""".strip()


def parse_ai_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AIの返答がJSON形式ではありません。")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("AIの返答がオブジェクトではありません。")
    return data


def format_plan_for_display(plan: dict) -> str:
    lines = ["整理案を作りました。確認してから実行できます。"]
    reason = plan.get("reason")
    if reason:
        lines.append(f"理由: {reason}")

    folders = plan.get("folders", [])
    moves = plan.get("moves", [])
    renames = plan.get("renames", [])

    if folders:
        lines.append("\n作成フォルダ:")
        lines.extend(f"- {name}" for name in folders)
    if moves:
        lines.append("\n移動:")
        lines.extend(f"- {item['source']} → {item['destination']}" for item in moves)
    if renames:
        lines.append("\nリネーム:")
        lines.extend(f"- {item['source']} → {item['destination']}" for item in renames)
    if not folders and not moves and not renames:
        lines.append("変更案はありません。")
    return "\n".join(lines)
