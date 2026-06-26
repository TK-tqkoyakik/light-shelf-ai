from __future__ import annotations

from dataclasses import dataclass


DEFAULT_FORBIDDEN_ACTIONS = (
    "delete",
    "purchase",
    "login",
    "send_personal_data",
    "change_permissions",
    "external_submit",
    "git_remote",
    "read_secrets",
    "run_commands",
    "read_local_files",
    "network_write",
)

RISK_TO_FORBIDDEN_ACTION = {
    "login": "login",
    "personal_data": "send_personal_data",
    "external_submit": "external_submit",
    "purchase": "purchase",
    "permission": "change_permissions",
    "delete": "delete",
    "git_remote": "git_remote",
    "secrets": "read_secrets",
    "destructive_git": "git_remote",
    "unsafe_delete": "delete",
    "local_file_read": "read_local_files",
    "command_execution": "run_commands",
}


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    requires_review: bool
    reason: str
    risks: tuple[str, ...] = ()
    scope: str = "text"


class ActionSafetyPolicy:
    """Small local policy gate inspired by Codex-style sandbox/approval boundaries."""

    REVIEW_PATTERNS = {
        "login": ("ログイン", "signin", "sign in", "password", "パスワード", "認証コード", "2fa", "token", "api key"),
        "personal_data": ("個人情報", "住所", "電話番号", "メールアドレス", "クレカ", "カード番号", "氏名", "生年月日"),
        "external_submit": ("送信", "submit", "フォーム", "公開", "投稿", "アップロード", "publish", "upload"),
        "purchase": ("購入", "支払い", "決済", "checkout", "buy", "注文"),
        "permission": ("権限", "permission", "共有設定", "公開範囲", "管理者", "admin", "everyone"),
        "delete": ("削除", "delete", "remove", "消して", "trash"),
        "git_remote": ("push", "git push", "force push", "remote", "githubに投稿", "githubに投稿", "pull request", "release"),
        "local_file_read": ("ファイル本文", "中身を読", "read file", ".env", "秘密鍵", "ssh key"),
        "command_execution": ("コマンド実行", "powershell", "cmd.exe", "bash", "管理者として実行", "sudo"),
    }

    BLOCK_PATTERNS = {
        "secrets": (
            "パスワードを教えて",
            "パスワードを表示",
            "tokenを表示",
            "api keyを表示",
            "apiキーを表示",
            "secretを表示",
            "認証コードを教えて",
            "秘密鍵を表示",
            ".envを表示",
        ),
        "destructive_git": ("git reset --hard", "履歴を消して", "repoを削除", "リポジトリを削除", "force pushして"),
        "unsafe_delete": ("全部削除", "全消し", "rm -rf", "del /s", "format ", "初期化して"),
    }

    def review_text(self, text: str, agent_name: str | None = None) -> SafetyDecision:
        normalized = text.lower()
        blocked = self._matches(normalized, self.BLOCK_PATTERNS)
        if blocked:
            return SafetyDecision(
                allowed=False,
                requires_review=False,
                reason="危険度が高い要求をローカルポリシーで停止しました。",
                risks=blocked,
                scope="user_input" if agent_name is None else f"{agent_name}:text",
            )

        risks = self._matches(normalized, self.REVIEW_PATTERNS)
        if risks:
            return SafetyDecision(
                allowed=True,
                requires_review=True,
                reason="外部送信・権限・削除・認証などの可能性があるため安全レビューが必要です。",
                risks=risks,
                scope="user_input" if agent_name is None else f"{agent_name}:text",
            )

        return SafetyDecision(allowed=True, requires_review=False, reason="低リスク要求です。", scope="user_input" if agent_name is None else f"{agent_name}:text")

    def _matches(self, normalized_text: str, patterns: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
        risks: list[str] = []
        for risk, words in patterns.items():
            if any(word.lower() in normalized_text for word in words):
                risks.append(risk)
        return tuple(risks)


class AgentPermissionGate:
    """Enforce least-privilege rules for tiny saved agents before/after LLM calls."""

    EXECUTION_CLAIMS = (
        "実行しました",
        "送信しました",
        "投稿しました",
        "購入しました",
        "決済しました",
        "ログインしました",
        "削除しました",
        "消しました",
        "権限を変更しました",
        "公開しました",
        "アップロードしました",
        "pushしました",
        "プッシュしました",
    )

    def __init__(self, text_policy: ActionSafetyPolicy | None = None) -> None:
        self.text_policy = text_policy or ActionSafetyPolicy()

    def review_agent_definition(self, agent_name: str, safety: dict | None) -> SafetyDecision:
        safety = safety or {}
        if safety.get("can_execute") is True:
            return SafetyDecision(
                allowed=False,
                requires_review=False,
                reason=f"{agent_name} は v1 で禁止している直接実行権限を持っています。",
                risks=("agent_can_execute",),
                scope="agent_definition",
            )
        missing = [key for key in ("can_execute", "needs_confirmation", "forbidden_actions") if key not in safety]
        if missing:
            return SafetyDecision(
                allowed=True,
                requires_review=True,
                reason=f"{agent_name} の安全メタデータが不足しています: {', '.join(missing)}",
                risks=("missing_safety_metadata",),
                scope="agent_definition",
            )
        return SafetyDecision(
            allowed=True,
            requires_review=False,
            reason=f"{agent_name} は直接実行権限を持たない定義です。",
            scope="agent_definition",
        )

    def review_agent_output(self, agent_name: str, safety: dict | None, output: str) -> SafetyDecision:
        safety = safety or {}
        base = self.text_policy.review_text(output, agent_name=agent_name)
        if not base.allowed:
            return SafetyDecision(
                allowed=False,
                requires_review=False,
                reason=f"{agent_name} の返答に表示前停止対象の危険内容が含まれています。",
                risks=base.risks,
                scope="agent_output",
            )

        if safety.get("can_execute") is not True and self._looks_like_execution_claim(output):
            return SafetyDecision(
                allowed=False,
                requires_review=False,
                reason=f"{agent_name} は直接実行できないため、実行済みと見える返答を停止しました。",
                risks=("agent_execution_claim",),
                scope="agent_output",
            )

        forbidden_actions = set(safety.get("forbidden_actions") or DEFAULT_FORBIDDEN_ACTIONS)
        forbidden_hits = tuple(
            sorted(
                {
                    RISK_TO_FORBIDDEN_ACTION[risk]
                    for risk in base.risks
                    if RISK_TO_FORBIDDEN_ACTION.get(risk) in forbidden_actions
                }
            )
        )
        if forbidden_hits:
            return SafetyDecision(
                allowed=True,
                requires_review=True,
                reason=f"{agent_name} の返答に禁止/要確認操作の候補があるため、人間の確認が必要です。",
                risks=forbidden_hits,
                scope="agent_output",
            )

        if base.requires_review:
            return SafetyDecision(
                allowed=True,
                requires_review=True,
                reason=f"{agent_name} の返答に安全レビュー対象の内容があります。",
                risks=base.risks,
                scope="agent_output",
            )

        return SafetyDecision(
            allowed=True,
            requires_review=False,
            reason=f"{agent_name} の返答は低リスクです。",
            scope="agent_output",
        )

    def _looks_like_execution_claim(self, text: str) -> bool:
        normalized = text.lower()
        return any(phrase.lower() in normalized for phrase in self.EXECUTION_CLAIMS)
