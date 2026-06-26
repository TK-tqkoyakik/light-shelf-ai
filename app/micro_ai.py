from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ollama_client import OllamaClient
from .performance import get_active_profile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = PROJECT_ROOT / "micro_ai_shelf" / "default" / "agents"


@dataclass(frozen=True)
class MicroAgent:
    name: str
    model: str
    system: str
    output: str
    role: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    safety: dict[str, Any] | None = None


class MicroAgentRunner:
    """Saved, tiny task agents that wake up for one step and unload afterward."""

    def __init__(self, client: OllamaClient | None = None, agent_dir: Path = AGENT_DIR) -> None:
        self.client = client or OllamaClient()
        self.agent_dir = agent_dir
        self.profile = get_active_profile()

    def run_json(self, agent_name: str, user_payload: dict) -> dict:
        agent = self.load(agent_name)
        prompt = self._build_prompt(agent, user_payload)
        raw = self.client.generate(model=self._select_model(agent), prompt=prompt, keep_alive=self.profile.keep_alive)
        return self._parse_json(raw)

    def run_text(self, agent_name: str, user_payload: dict) -> str:
        agent = self.load(agent_name)
        prompt = self._build_prompt(agent, user_payload)
        return self.client.generate(model=self._select_model(agent), prompt=prompt, keep_alive=self.profile.keep_alive).strip()

    def load(self, agent_name: str) -> MicroAgent:
        path = self.agent_dir / f"{agent_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"小型AI定義が見つかりません: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return MicroAgent(
            name=str(data["name"]),
            model=str(data.get("model", self.profile.model)),
            system=str(data["system"]),
            output=str(data["output"]),
            role=str(data.get("role", "")),
            description=str(data.get("description", "")),
            tags=tuple(str(tag) for tag in data.get("tags", [])),
            safety=dict(data.get("safety", self._default_safety(data))),
        )

    def _default_safety(self, data: dict) -> dict[str, Any]:
        role = str(data.get("role", ""))
        return {
            "can_execute": False,
            "needs_confirmation": role in ("reviewer", "specialist_chat"),
            "forbidden_actions": ["delete", "purchase", "login", "send_personal_data", "change_permissions"],
        }

    def list_agents(self, role: str | None = None) -> list[MicroAgent]:
        agents: list[MicroAgent] = []
        for path in sorted(self.agent_dir.glob("*.json")):
            agent = self.load(path.stem)
            if role is None or agent.role == role:
                agents.append(agent)
        return agents

    def find_agents(self, text: str, role: str = "specialist_chat", limit: int | None = None) -> list[MicroAgent]:
        limit = limit or self.profile.max_agent_candidates
        normalized = text.lower()
        scored: list[tuple[int, MicroAgent]] = []
        for agent in self.list_agents(role=role):
            haystack = " ".join((agent.name, agent.description, " ".join(agent.tags))).lower()
            score = sum(1 for token in agent.tags if token.lower() in normalized)
            score += sum(1 for word in normalized.split() if word and word in haystack)
            if score > 0:
                scored.append((score, agent))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [agent for _score, agent in scored[:limit]]

    def _select_model(self, agent: MicroAgent) -> str:
        if self.profile.name in ("tiny", "laptop"):
            return self.profile.model
        return agent.model or self.profile.model

    def _build_prompt(self, agent: MicroAgent, user_payload: dict) -> str:
        payload = json.dumps(user_payload, ensure_ascii=False, indent=2)
        return f"""
{agent.system}

出力形式:
{agent.output}

入力:
{payload}
""".strip()

    def _parse_json(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("小型AIの返答がJSON形式ではありません。")
        data = json.loads(text[start : end + 1])
        if not isinstance(data, dict):
            raise ValueError("小型AIの返答がJSONオブジェクトではありません。")
        return data
