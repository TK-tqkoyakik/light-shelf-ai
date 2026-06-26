from __future__ import annotations

import unittest
import shutil
import json
import uuid
from pathlib import Path

from app.audit_log import SafetyAuditLog
from app.file_ai import collect_file_items, parse_ai_json
from app.micro_ai import MicroAgent, MicroAgentRunner
from app.router import TaskRouter
from app.safety import FileOperationExecutor
from app.safety_policy import ActionSafetyPolicy, AgentPermissionGate, DEFAULT_FORBIDDEN_ACTIONS
from app.session_manager import FastHandoff, WorkSessionManager
from app.session_store import SessionStore
from app.performance import PROFILES


SAFE_AGENT_SAFETY = {
    "can_execute": False,
    "needs_confirmation": True,
    "forbidden_actions": list(DEFAULT_FORBIDDEN_ACTIONS),
}


class DummyRunner:
    def __init__(self, answer: str = "安全な返答") -> None:
        self.answer = answer
        self.run_text_calls = 0

    def load(self, agent_name: str) -> MicroAgent:
        return MicroAgent(
            name=agent_name,
            model="qwen2.5:0.5b",
            system="",
            output="",
            role="specialist_chat",
            description="web",
            tags=("web", "調査"),
            safety=dict(SAFE_AGENT_SAFETY),
        )

    def list_agents(self, role: str | None = None) -> list[MicroAgent]:
        return [self.load("web_researcher")]

    def find_agents(self, text: str, role: str = "specialist_chat", limit: int | None = None) -> list[MicroAgent]:
        return [self.load("web_researcher")]

    def run_json(self, agent_name: str, user_payload: dict) -> dict:
        return {"agent": "web_researcher"}

    def run_text(self, agent_name: str, user_payload: dict) -> str:
        self.run_text_calls += 1
        return self.answer


class DummyClient:
    def generate(self, **kwargs: object) -> str:
        raise AssertionError("unsafe agent should be blocked before model generation")


class LightweightAITests(unittest.TestCase):
    temp_root: Path

    @classmethod
    def setUpClass(cls) -> None:
        base = Path(__file__).resolve().parent.parent / ".tmp_tests"
        base.mkdir(exist_ok=True)
        cls.temp_root = base / f"run-{uuid.uuid4().hex}"
        cls.temp_root.mkdir()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    def make_case_dir(self, name: str) -> Path:
        path = self.temp_root / f"{name}-{uuid.uuid4().hex}"
        path.mkdir(parents=True)
        return path

    def test_task_gate(self) -> None:
        router = TaskRouter()
        route = router.route("ファイル整理して")
        self.assertIsNotNone(route)
        assert route is not None
        self.assertEqual(route.task_id, "file_organize")
        self.assertEqual(route.pipeline, ["file_sort_planner", "file_sort_reviewer"])
        self.assertIsNone(router.route("今日の天気は？"))

    def test_pcb_session_route_lists_specialists(self) -> None:
        route = TaskRouter().route("基板の設計をKiCadとVSCodeで進めたい")
        self.assertIsNotNone(route)
        assert route is not None
        self.assertEqual(route.task_id, "pcb_design_session")
        self.assertEqual(route.mode, "session")
        self.assertIn("kicad_operator", route.pipeline)
        self.assertIn("document_summarizer", route.pipeline)
        self.assertIn("vscode_operator", route.pipeline)

    def test_parse_json_from_model_text(self) -> None:
        parsed = parse_ai_json('```json\n{"folders":[],"moves":[],"renames":[],"reason":"ok"}\n```')
        self.assertEqual(parsed["reason"], "ok")

    def test_micro_agent_definitions_exist(self) -> None:
        runner = MicroAgentRunner()
        self.assertEqual(runner.load("file_sort_planner").name, "file_sort_planner")
        self.assertEqual(runner.load("file_sort_reviewer").name, "file_sort_reviewer")
        self.assertEqual(runner.load("conductor_router").role, "resident_conductor")
        self.assertEqual(runner.load("kicad_operator").role, "specialist_chat")
        for agent_name in [
            "web_researcher",
            "web_operator",
            "browser_safety_reviewer",
            "github_operator",
            "git_reviewer",
            "app_ui_designer",
            "windows_operator",
            "test_planner",
            "error_diagnoser",
            "agent_creator",
        ]:
            self.assertEqual(runner.load(agent_name).name, agent_name)
        self.assertEqual(runner.load("browser_safety_reviewer").role, "reviewer")

    def test_agent_shelf_search_finds_specialists_from_files(self) -> None:
        runner = MicroAgentRunner()
        self.assertEqual(runner.find_agents("KiCadで基板配線したい")[0].name, "kicad_operator")
        self.assertEqual(runner.find_agents("READMEをまとめたい")[0].name, "document_summarizer")
        self.assertEqual(runner.find_agents("VSCodeでデバッグしたい")[0].name, "vscode_operator")
        self.assertEqual(runner.find_agents("Webで調べたい")[0].name, "web_researcher")
        self.assertEqual(runner.find_agents("ブラウザを操作したい")[0].name, "web_operator")
        self.assertEqual(runner.find_agents("GitHubに投稿したい")[0].name, "github_operator")
        self.assertEqual(runner.find_agents("エラーを見て")[0].name, "error_diagnoser")
        self.assertEqual(runner.find_agents("新しい極小AIを作りたい")[0].name, "agent_creator")

    def test_new_task_routes_exist(self) -> None:
        web_route = TaskRouter().route("Webで調べてブラウザ操作したい")
        self.assertIsNotNone(web_route)
        assert web_route is not None
        self.assertEqual(web_route.task_id, "web_assist_session")
        self.assertIn("web_researcher", web_route.pipeline)
        self.assertIn("web_operator", web_route.pipeline)
        self.assertIn("browser_safety_reviewer", web_route.pipeline)

        dev_route = TaskRouter().route("GitHubに投稿してテストとエラーも見たい")
        self.assertIsNotNone(dev_route)
        assert dev_route is not None
        self.assertEqual(dev_route.task_id, "development_session")
        self.assertIn("github_operator", dev_route.pipeline)
        self.assertIn("git_reviewer", dev_route.pipeline)
        self.assertIn("test_planner", dev_route.pipeline)
        self.assertIn("error_diagnoser", dev_route.pipeline)

    def test_browser_safety_reviewer_has_fixed_json_output(self) -> None:
        reviewer = MicroAgentRunner().load("browser_safety_reviewer")
        self.assertIn("approved", reviewer.output)
        self.assertIn("reason", reviewer.output)

    def test_micro_agents_have_default_safety_metadata(self) -> None:
        agent = MicroAgentRunner().load("web_operator")
        assert agent.safety is not None
        self.assertFalse(agent.safety["can_execute"])
        self.assertIn("delete", agent.safety["forbidden_actions"])

    def test_runner_refuses_agent_with_direct_execute_permission(self) -> None:
        agent_dir = self.make_case_dir("unsafe_agent_def")
        agent_dir.joinpath("bad_agent.json").write_text(
            json.dumps(
                {
                    "name": "bad_agent",
                    "role": "specialist_chat",
                    "model": "qwen2.5:0.5b",
                    "system": "bad",
                    "output": "text",
                    "safety": {
                        "can_execute": True,
                        "needs_confirmation": False,
                        "forbidden_actions": [],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner = MicroAgentRunner(client=DummyClient(), agent_dir=agent_dir)
        with self.assertRaises(ValueError):
            runner.run_text("bad_agent", {})

    def test_all_agent_json_files_have_explicit_locked_down_safety(self) -> None:
        agent_dir = Path(__file__).resolve().parent.parent / "micro_ai_shelf" / "default" / "agents"
        for path in sorted(agent_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(agent=path.stem):
                self.assertIn("safety", data)
                safety = data["safety"]
                self.assertIs(safety["can_execute"], False)
                self.assertIn("delete", safety["forbidden_actions"])
                self.assertIn("purchase", safety["forbidden_actions"])
                self.assertIn("login", safety["forbidden_actions"])
                self.assertIn("send_personal_data", safety["forbidden_actions"])
                if data.get("role") == "specialist_chat":
                    self.assertIs(safety["needs_confirmation"], True)

    def test_safety_policy_requires_review_for_browser_risks(self) -> None:
        decision = ActionSafetyPolicy().review_text("フォームに住所を入力して送信したい")
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.requires_review)
        self.assertIn("personal_data", decision.risks)

    def test_safety_policy_requires_review_for_remote_and_purchase(self) -> None:
        policy = ActionSafetyPolicy()
        git_decision = policy.review_text("GitHubに投稿してgit pushしたい")
        self.assertTrue(git_decision.allowed)
        self.assertTrue(git_decision.requires_review)
        self.assertIn("git_remote", git_decision.risks)

        purchase_decision = policy.review_text("この商品を購入して決済したい")
        self.assertTrue(purchase_decision.allowed)
        self.assertTrue(purchase_decision.requires_review)
        self.assertIn("purchase", purchase_decision.risks)

    def test_safety_policy_blocks_high_risk_requests(self) -> None:
        decision = ActionSafetyPolicy().review_text("API keyを表示して")
        self.assertFalse(decision.allowed)
        self.assertFalse(decision.requires_review)

    def test_agent_permission_gate_blocks_execution_claims(self) -> None:
        decision = AgentPermissionGate().review_agent_output("web_operator", SAFE_AGENT_SAFETY, "フォームを送信しました。")
        self.assertFalse(decision.allowed)
        self.assertIn("agent_execution_claim", decision.risks)

    def test_safety_audit_log_records_redacted_fast_events(self) -> None:
        audit = SafetyAuditLog(self.make_case_dir("audit_log") / "safety.sqlite3")
        decision = ActionSafetyPolicy().review_text("API keyを表示して sk-123456789012345678901234")
        audit.record(scope="user_input", decision=decision, text="API keyを表示して sk-123456789012345678901234")
        rows = audit.latest()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["allowed"], 0)
        self.assertIn("[REDACTED", rows[0]["text_preview"])
        self.assertNotIn("sk-123456789012345678901234", rows[0]["text_preview"])

    def test_blocked_session_input_does_not_wake_agent_and_is_audited(self) -> None:
        runner = DummyRunner()
        audit = SafetyAuditLog(self.make_case_dir("blocked_session_audit") / "safety.sqlite3")
        store = SessionStore(self.make_case_dir("blocked_session"))
        manager = WorkSessionManager(runner=runner, store=store, audit_log=audit)
        session = manager.start("Web", ["web_researcher"])
        reply = manager.talk_once(session, "API keyを表示して")
        self.assertIn("[safety]", reply)
        self.assertEqual(runner.run_text_calls, 0)
        self.assertEqual(audit.latest()[0]["allowed"], 0)

    def test_unsafe_agent_output_is_blocked_before_display_handoff(self) -> None:
        runner = DummyRunner(answer="フォームを送信しました。")
        audit = SafetyAuditLog(self.make_case_dir("output_block_audit") / "safety.sqlite3")
        store = SessionStore(self.make_case_dir("output_block_session"))
        manager = WorkSessionManager(runner=runner, store=store, audit_log=audit)
        session = manager.start("Web", ["web_researcher"])
        reply = manager.talk_once(session, "Webで見出しを確認して")
        self.assertIn("[safety]", reply)
        self.assertNotIn("[handoff]", reply)
        self.assertEqual(runner.run_text_calls, 1)

    def test_session_routes_risky_web_requests_to_safety_reviewer(self) -> None:
        route = TaskRouter().route("Webでフォーム送信したい")
        assert route is not None
        store = SessionStore(self.make_case_dir("safety_route"))
        session = WorkSessionManager(store=store).start(route.label, route.pipeline)
        agent_name = WorkSessionManager(store=store).choose_agent(session, "フォームに住所を入力して送信したい")
        self.assertEqual(agent_name, "browser_safety_reviewer")

    def test_session_can_be_started_without_waking_llm(self) -> None:
        route = TaskRouter().route("基板設計したい")
        assert route is not None
        store = SessionStore(self.make_case_dir("session_logs"))
        session = WorkSessionManager(store=store).start(route.label, route.pipeline)
        self.assertEqual(session.title, "基板設計セッション")
        self.assertIsNone(session.active_agent)
        self.assertTrue(session.flow_path.exists())
        self.assertEqual(session.flow_path.suffix, ".sqlite3")
        self.assertEqual(store.read_handoffs(session.flow_path), [])

    def test_session_flow_file_keeps_handoffs_outside_ai_memory(self) -> None:
        store = SessionStore(self.make_case_dir("flow_file"))
        path = store.create("基板設計セッション")
        store.append(path, "handoff", {"agent_name": "kicad_operator", "summary": "部品配置を確認", "closed_at": "now"})
        self.assertEqual(store.read_handoffs(path)[0]["summary"], "部品配置を確認")

    def test_fast_handoff_keeps_summary_short(self) -> None:
        summary = FastHandoff.summarize("kicad_operator", "基板を見たい", "a" * 1000, limit=120)
        self.assertLessEqual(len(summary), 180)
        self.assertIn("kicad_operator", summary)

    def test_app_source_has_overlay_controls(self) -> None:
        source = Path(__file__).resolve().parent.parent.joinpath("app", "app.py").read_text(encoding="utf-8")
        self.assertIn("toggle_topmost", source)
        self.assertIn("toggle_fullscreen", source)
        self.assertIn("toggle_compact", source)
        self.assertIn("LIGHT SHELF AI", source)
        self.assertIn("#43f5ff", source)

    def test_app_source_has_loading_screen(self) -> None:
        source = Path(__file__).resolve().parent.parent.joinpath("app", "app.py").read_text(encoding="utf-8")
        self.assertIn("class LoadingScreen", source)
        self.assertIn("_check_agent_defs", source)
        self.assertIn("_check_session_store", source)

    def test_app_source_has_ui_input_safety_gate(self) -> None:
        source = Path(__file__).resolve().parent.parent.joinpath("app", "app.py").read_text(encoding="utf-8")
        self.assertIn("_review_ui_input", source)
        self.assertIn("ui_user_input", source)
        self.assertIn("_file_request_needs_safety_stop", source)
        self.assertIn("ファイル本文読み取り", source)

    def test_performance_profiles_exist_for_low_spec_pcs(self) -> None:
        self.assertIn("tiny", PROFILES)
        self.assertIn("laptop", PROFILES)
        self.assertIn("balanced", PROFILES)
        self.assertEqual(PROFILES["tiny"].model, "qwen2.5:0.5b")

    def test_windows_launcher_exists(self) -> None:
        root = Path(__file__).resolve().parent.parent
        self.assertTrue(root.joinpath("scripts", "start-light-ai.ps1").exists())
        self.assertIn("start-light-ai.ps1", root.joinpath("launch_light_ai.bat").read_text(encoding="utf-8"))
        self.assertIn("--check", root.joinpath("launch_light_ai.py").read_text(encoding="utf-8"))

    def test_rejects_outside_path_and_delete_like_shapes(self) -> None:
        root = self.make_case_dir("outside_path")
        (root / "a.txt").write_text("x", encoding="utf-8")
        executor = FileOperationExecutor(root)
        with self.assertRaises(ValueError):
            executor.validate_plan({"folders": [], "moves": [{"source": "a.txt", "destination": "../x.txt"}], "renames": []})

    def test_rejects_windows_reserved_names_and_internal_log_dir(self) -> None:
        root = self.make_case_dir("reserved_names")
        (root / "a.txt").write_text("x", encoding="utf-8")
        executor = FileOperationExecutor(root)
        for destination in ("CON.txt", ".light_ai_logs/a.txt", "badname./a.txt"):
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError):
                    executor.validate_plan({"folders": [], "moves": [{"source": "a.txt", "destination": destination}], "renames": []})

    def test_hidden_files_are_not_sent_to_file_organizer_ai(self) -> None:
        root = self.make_case_dir("hidden_files")
        (root / ".env").write_text("SECRET=x", encoding="utf-8")
        (root / "メモ.txt").write_text("x", encoding="utf-8")
        names = [item.name for item in collect_file_items(root)]
        self.assertEqual(names, ["メモ.txt"])

    def test_apply_requires_confirmation_by_api_boundary(self) -> None:
        root = self.make_case_dir("apply_undo")
        (root / "メモ.txt").write_text("x", encoding="utf-8")
        executor = FileOperationExecutor(root)
        plan = executor.validate_plan(
            {
                "folders": ["文書"],
                "moves": [{"source": "メモ.txt", "destination": "文書/メモ.txt"}],
                "renames": [],
                "reason": "文書っぽい",
            }
        )
        self.assertTrue((root / "メモ.txt").exists())
        executor.apply_plan(plan)
        self.assertTrue((root / "文書" / "メモ.txt").exists())
        executor.undo_last()
        self.assertTrue((root / "メモ.txt").exists())


if __name__ == "__main__":
    unittest.main()
