from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .micro_ai import MicroAgentRunner
from .performance import get_active_profile
from .session_store import SessionStore


@dataclass
class AgentHandoff:
    agent_name: str
    summary: str
    closed_at: str


@dataclass
class WorkSession:
    title: str
    available_agents: list[str]
    flow_path: Path
    active_agent: str | None = None


class WorkSessionManager:
    """Resident conductor: wake one specialist chat AI, receive a handoff, then close it."""

    def __init__(self, runner: MicroAgentRunner | None = None, store: SessionStore | None = None) -> None:
        self.runner = runner or MicroAgentRunner()
        self.store = store or SessionStore()
        self.profile = get_active_profile()

    def start(self, title: str, available_agents: list[str]) -> WorkSession:
        flow_path = self.store.create(title)
        return WorkSession(title=title, available_agents=available_agents, flow_path=flow_path)

    def choose_agent(self, session: WorkSession, user_message: str) -> str:
        handoffs = self.store.read_handoffs(session.flow_path)
        candidates = self.runner.find_agents(user_message)
        candidate_names = [agent.name for agent in candidates]
        allowed_agents = candidate_names or [
            name
            for name in session.available_agents
            if name not in ("conductor_router", "handoff_summarizer")
        ]
        if len(allowed_agents) == 1 and not self.profile.use_llm_router_when_single_candidate:
            session.active_agent = allowed_agents[0]
            return allowed_agents[0]
        payload = {
            "session_title": session.title,
            "available_agents": allowed_agents,
            "agent_shelf": [
                {"name": agent.name, "description": agent.description, "tags": list(agent.tags)}
                for agent in candidates
            ],
            "handoffs": handoffs,
            "user_message": user_message,
        }
        decision = self.runner.run_json("conductor_router", payload)
        agent_name = decision.get("agent")
        if agent_name not in allowed_agents:
            raise ValueError(f"司令塔が棚にないAIを選びました: {agent_name}")
        session.active_agent = agent_name
        return agent_name

    def talk_once(self, session: WorkSession, user_message: str) -> str:
        self.store.append(session.flow_path, "user_message", {"text": user_message})
        agent_name = self.choose_agent(session, user_message)
        handoffs = self.store.read_handoffs(session.flow_path)
        self.store.append(session.flow_path, "agent_selected", {"agent_name": agent_name})
        payload = {
            "session_title": session.title,
            "handoffs": handoffs,
            "user_message": user_message,
        }
        answer = self.runner.run_text(agent_name, payload)
        self.store.append(session.flow_path, "agent_answer", {"agent_name": agent_name, "answer": answer})
        handoff = self._summarize_and_close(session, agent_name, user_message, answer)
        self.store.append_dataclass(session.flow_path, "handoff", handoff)
        session.active_agent = None
        return f"[{agent_name}]\n{answer}\n\n[handoff]\n{handoff.summary}"

    def _summarize_and_close(self, session: WorkSession, agent_name: str, user_message: str, answer: str) -> AgentHandoff:
        if len(answer) <= 500:
            return AgentHandoff(
                agent_name=agent_name,
                summary=FastHandoff.summarize(agent_name, user_message, answer, limit=self.profile.max_handoff_chars),
                closed_at=datetime.now().isoformat(timespec="seconds"),
            )
        payload = {
            "session_title": session.title,
            "agent_name": agent_name,
            "user_message": user_message,
            "agent_answer": answer,
            "previous_handoffs": self.store.read_handoffs(session.flow_path),
        }
        summary_data = self.runner.run_json("handoff_summarizer", payload)
        return AgentHandoff(
            agent_name=agent_name,
            summary=str(summary_data.get("summary", ""))[:800],
            closed_at=datetime.now().isoformat(timespec="seconds"),
        )


class FastHandoff:
    @staticmethod
    def summarize(agent_name: str, user_message: str, answer: str, limit: int = 280) -> str:
        text = " ".join(answer.replace("\n", " ").split())
        if len(text) > limit:
            text = text[: limit - 1] + "…"
        return f"{agent_name}: user='{user_message[:80]}', result='{text}'"
