from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class PerformanceProfile:
    name: str
    model: str
    keep_alive: int | str
    max_handoff_chars: int
    use_llm_router_when_single_candidate: bool
    max_agent_candidates: int
    description: str


TINY_PROFILE = PerformanceProfile(
    name="tiny",
    model="qwen2.5:0.5b",
    keep_alive=0,
    max_handoff_chars=180,
    use_llm_router_when_single_candidate=False,
    max_agent_candidates=3,
    description="低スペックPC向け。LLM呼び出しを最小化し、0.5Bモデルだけを使う。",
)

LAPTOP_PROFILE = PerformanceProfile(
    name="laptop",
    model="qwen2.5:0.5b",
    keep_alive=0,
    max_handoff_chars=280,
    use_llm_router_when_single_candidate=False,
    max_agent_candidates=6,
    description="このPC向けの標準。軽さを保ちつつ専門AI切替で高性能に見せる。",
)

BALANCED_PROFILE = PerformanceProfile(
    name="balanced",
    model="qwen2.5:1.5b",
    keep_alive=0,
    max_handoff_chars=420,
    use_llm_router_when_single_candidate=False,
    max_agent_candidates=8,
    description="少し高性能寄り。余裕がある時だけ1.5B級を使う。",
)


PROFILES = {
    TINY_PROFILE.name: TINY_PROFILE,
    LAPTOP_PROFILE.name: LAPTOP_PROFILE,
    BALANCED_PROFILE.name: BALANCED_PROFILE,
}


def get_active_profile() -> PerformanceProfile:
    requested = os.environ.get("LIGHT_AI_PROFILE", LAPTOP_PROFILE.name).strip().lower()
    return PROFILES.get(requested, LAPTOP_PROFILE)


def describe_profile(profile: PerformanceProfile = LAPTOP_PROFILE) -> str:
    return (
        f"{profile.name}: model={profile.model}, keep_alive={profile.keep_alive}, "
        f"handoff<={profile.max_handoff_chars}chars"
    )
