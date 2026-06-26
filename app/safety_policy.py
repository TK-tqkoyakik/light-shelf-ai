from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    requires_review: bool
    reason: str
    risks: tuple[str, ...] = ()


class ActionSafetyPolicy:
    """Small local policy gate inspired by Codex-style sandbox/approval boundaries."""

    REVIEW_PATTERNS = {
        "login": ("ログイン", "signin", "sign in", "password", "パスワード", "認証コード", "token", "api key"),
        "personal_data": ("個人情報", "住所", "電話番号", "メールアドレス", "クレカ", "カード番号"),
        "external_submit": ("送信", "submit", "フォーム", "公開", "投稿", "アップロード"),
        "purchase": ("購入", "支払い", "決済", "checkout", "buy"),
        "permission": ("権限", "permission", "共有設定", "公開範囲", "管理者"),
        "delete": ("削除", "delete", "remove", "消して"),
        "git_remote": ("push", "git push", "remote", "githubに投稿", "GitHubに投稿"),
    }

    BLOCK_PATTERNS = {
        "secrets": ("パスワードを教えて", "tokenを表示", "api keyを表示", "secretを表示", "認証コードを教えて"),
        "destructive_git": ("git reset --hard", "履歴を消して", "repoを削除", "リポジトリを削除"),
        "unsafe_delete": ("全部削除", "全消し", "format ", "初期化して"),
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
            )

        risks = self._matches(normalized, self.REVIEW_PATTERNS)
        if risks:
            return SafetyDecision(
                allowed=True,
                requires_review=True,
                reason="外部送信・権限・削除・認証などの可能性があるため安全レビューが必要です。",
                risks=risks,
            )

        return SafetyDecision(allowed=True, requires_review=False, reason="低リスク要求です。")

    def _matches(self, normalized_text: str, patterns: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
        risks: list[str] = []
        for risk, words in patterns.items():
            if any(word.lower() in normalized_text for word in words):
                risks.append(risk)
        return tuple(risks)
