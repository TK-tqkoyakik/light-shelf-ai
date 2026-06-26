from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


WINDOWS_FORBIDDEN = set('<>:"\\|?*')


class FileOperationExecutor:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.log_dir = self.root / ".light_ai_logs"

    def validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        folders = self._validate_folder_list(plan.get("folders", []))
        moves = self._validate_operations(plan.get("moves", []), allow_nested_destination=True)
        renames = self._validate_operations(plan.get("renames", []), allow_nested_destination=False)
        reason = plan.get("reason", "")
        if not isinstance(reason, str):
            reason = ""
        return {"folders": folders, "moves": moves, "renames": renames, "reason": reason[:200]}

    def apply_plan(self, plan: dict[str, Any]) -> str:
        plan = self.validate_plan(plan)
        undo_entries: list[dict[str, str]] = []

        for folder_name in plan["folders"]:
            folder_path = self._safe_destination(folder_name)
            folder_path.mkdir(exist_ok=True)
            undo_entries.append({"type": "mkdir", "path": str(folder_path)})

        for op in plan["renames"]:
            source = self._safe_source(op["source"])
            destination = self._safe_destination(op["destination"])
            self._move(source, destination)
            undo_entries.append({"type": "move", "source": str(destination), "destination": str(source)})

        for op in plan["moves"]:
            source = self._safe_source(op["source"])
            destination = self._safe_destination(op["destination"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            self._move(source, destination)
            undo_entries.append({"type": "move", "source": str(destination), "destination": str(source)})

        self._write_log({"applied_at": datetime.now().isoformat(timespec="seconds"), "undo": undo_entries})
        return f"実行しました。フォルダ作成 {len(plan['folders'])} 件、移動 {len(plan['moves'])} 件、リネーム {len(plan['renames'])} 件。"

    def undo_last(self) -> str:
        logs = sorted(self.log_dir.glob("undo-*.json"))
        if not logs:
            return "取り消し履歴がありません。"
        latest = logs[-1]
        data = json.loads(latest.read_text(encoding="utf-8"))
        entries = list(reversed(data.get("undo", [])))
        count = 0
        for entry in entries:
            if entry.get("type") == "move":
                source = Path(entry["source"])
                destination = Path(entry["destination"])
                if self._is_inside_root(source) and self._is_inside_root(destination) and source.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source), str(destination))
                    count += 1
            elif entry.get("type") == "mkdir":
                path = Path(entry["path"])
                if self._is_inside_root(path) and path.exists() and path.is_dir():
                    try:
                        path.rmdir()
                        count += 1
                    except OSError:
                        pass
        latest.rename(latest.with_suffix(".undone.json"))
        return f"直前の操作を取り消しました。復元 {count} 件。"

    def _validate_folder_list(self, folders: Any) -> list[str]:
        if not isinstance(folders, list):
            raise ValueError("folders は配列である必要があります。")
        return [self._validate_relative_path(item, allow_nested=False) for item in folders]

    def _validate_operations(self, operations: Any, allow_nested_destination: bool) -> list[dict[str, str]]:
        if not isinstance(operations, list):
            raise ValueError("moves/renames は配列である必要があります。")
        validated: list[dict[str, str]] = []
        for item in operations:
            if not isinstance(item, dict):
                raise ValueError("操作はオブジェクトである必要があります。")
            source = self._validate_relative_path(item.get("source"), allow_nested=False)
            destination = self._validate_relative_path(item.get("destination"), allow_nested=allow_nested_destination)
            self._safe_source(source)
            self._safe_destination(destination)
            validated.append({"source": source, "destination": destination})
        return validated

    def _validate_relative_path(self, value: Any, allow_nested: bool) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("パスが空です。")
        value = value.strip().replace("\\", "/")
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or ":" in value:
            raise ValueError(f"危険なパスを拒否しました: {value}")
        if not allow_nested and "/" in value:
            raise ValueError(f"この操作ではサブフォルダ指定できません: {value}")
        for part in path.parts:
            if part in ("", ".", "..") or any(char in WINDOWS_FORBIDDEN for char in part):
                raise ValueError(f"Windowsで危険な名前を拒否しました: {value}")
        return value

    def _safe_source(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not self._is_inside_root(path):
            raise ValueError(f"対象フォルダ外のsourceを拒否しました: {relative}")
        if not path.is_file():
            raise ValueError(f"sourceファイルが存在しません: {relative}")
        return path

    def _safe_destination(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not self._is_inside_root(path):
            raise ValueError(f"対象フォルダ外のdestinationを拒否しました: {relative}")
        return path

    def _move(self, source: Path, destination: Path) -> None:
        if destination.exists():
            raise FileExistsError(f"移動先が既に存在します: {destination.name}")
        shutil.move(str(source), str(destination))

    def _write_log(self, data: dict[str, Any]) -> None:
        self.log_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.log_dir / f"undo-{stamp}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _is_inside_root(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.root)
            return True
        except ValueError:
            return False
