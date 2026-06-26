from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext

from .file_ai import FileOrganizerAI, format_plan_for_display
from .micro_ai import MicroAgentRunner
from .router import TaskRouter
from .safety import FileOperationExecutor
from .session_manager import WorkSession, WorkSessionManager
from .session_store import SessionStore


BG = "#07111f"
PANEL = "#0d1b2f"
PANEL_2 = "#10243d"
CYAN = "#43f5ff"
BLUE = "#6aa8ff"
PINK = "#ff4fd8"
TEXT = "#e8f6ff"
MUTED = "#8aa3b8"
OK = "#53ff9f"
WARN = "#ffd166"


class MiniTaskAIApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Light Shelf AI")
        self.root.geometry("720x680")
        self.root.minsize(520, 460)
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)

        self.selected_folder: Path | None = None
        self.current_plan = None
        self.is_compact = False
        self.is_fullscreen = False
        self.normal_geometry = "720x680"
        self.ai = FileOrganizerAI()
        self.router = TaskRouter()
        self.session_manager = WorkSessionManager()
        self.work_session: WorkSession | None = None
        self.executor: FileOperationExecutor | None = None
        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()

        self._build_ui()
        self._write("AI", f"常駐司令塔だけ起動中です。{self.router.describe_available_tasks()}。必要な小型AIだけ棚から呼びます。")
        self._poll_messages()

    def _build_ui(self) -> None:
        self.font_title = tkfont.Font(family="Yu Gothic UI", size=15, weight="bold")
        self.font_ui = tkfont.Font(family="Yu Gothic UI", size=10)
        self.font_small = tkfont.Font(family="Yu Gothic UI", size=9)
        self.font_mono = tkfont.Font(family="Cascadia Mono", size=10)

        shell = tk.Frame(self.root, bg=BG, padx=14, pady=14)
        shell.pack(fill=tk.BOTH, expand=True)
        self.shell = shell

        header = tk.Frame(shell, bg=BG)
        header.pack(fill=tk.X, pady=(0, 12))

        title_block = tk.Frame(header, bg=BG)
        title_block.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(title_block, text="LIGHT SHELF AI", fg=CYAN, bg=BG, font=self.font_title).pack(anchor="w")
        tk.Label(title_block, text="micro agents on demand / local overlay", fg=MUTED, bg=BG, font=self.font_small).pack(anchor="w")

        overlay_row = tk.Frame(header, bg=BG)
        overlay_row.pack(side=tk.RIGHT)

        self.pin_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            overlay_row,
            text="PIN",
            variable=self.pin_var,
            command=self.toggle_topmost,
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL,
            activebackground=BG,
            activeforeground=CYAN,
            font=self.font_small,
        ).pack(side=tk.LEFT, padx=(0, 6))
        self._button(overlay_row, "FULL", self.toggle_fullscreen).pack(side=tk.LEFT, padx=(0, 6))
        self._button(overlay_row, "− MINI", self.toggle_compact).pack(side=tk.LEFT)

        top = self._card(shell)
        self.top_frame = top
        top.pack(fill=tk.X, pady=(0, 10))

        self.folder_label = tk.Label(top, text="フォルダ未選択", anchor="w", fg=MUTED, bg=PANEL, font=self.font_ui)
        self.folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=12)

        self._button(top, "フォルダ選択", self.choose_folder, accent=True).pack(side=tk.RIGHT, padx=10, pady=10)

        self.chat = scrolledtext.ScrolledText(
            shell,
            height=20,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg="#050b14",
            fg=TEXT,
            insertbackground=CYAN,
            selectbackground="#173b64",
            relief=tk.FLAT,
            borderwidth=0,
            font=self.font_mono,
            padx=14,
            pady=14,
        )
        self.chat_widget = self.chat
        self.chat.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        input_row = self._card(shell)
        self.input_frame = input_row
        input_row.pack(fill=tk.X, pady=(0, 10))

        self.input_var = tk.StringVar()
        entry = tk.Entry(
            input_row,
            textvariable=self.input_var,
            bg="#081321",
            fg=TEXT,
            insertbackground=CYAN,
            relief=tk.FLAT,
            font=self.font_ui,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=12, ipady=7)
        entry.bind("<Return>", lambda _event: self.send())

        self._button(input_row, "SEND", self.send, accent=True).pack(side=tk.RIGHT, padx=(0, 12), pady=12)

        action_row = tk.Frame(shell, bg=BG)
        self.action_frame = action_row
        action_row.pack(fill=tk.X)

        self.apply_button = self._button(action_row, "確認して実行", self.apply_plan, accent=True)
        self.apply_button.config(state=tk.DISABLED)
        self.apply_button.pack(side=tk.LEFT)

        self._button(action_row, "取り消し", self.undo_last).pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="待機中 / LLM offline")
        tk.Label(action_row, textvariable=self.status_var, anchor="e", fg=OK, bg=BG, font=self.font_small).pack(side=tk.RIGHT)

        self.root.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda _event: self.exit_fullscreen())

    def _card(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL, highlightbackground="#1e78a8", highlightthickness=1, bd=0)

    def _button(self, parent: tk.Widget, text: str, command: callable, accent: bool = False) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=CYAN if accent else PANEL_2,
            fg="#001018" if accent else TEXT,
            activebackground=PINK if accent else "#173b64",
            activeforeground="#001018" if accent else CYAN,
            relief=tk.FLAT,
            borderwidth=0,
            padx=14,
            pady=8,
            font=self.font_small,
            cursor="hand2",
        )

    def toggle_topmost(self) -> None:
        self.root.attributes("-topmost", bool(self.pin_var.get()))

    def toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.is_compact = False
            self._show_full_ui()
            self.root.attributes("-fullscreen", True)
            self.status_var.set("全画面モード（Escで解除）")
        else:
            self.root.attributes("-fullscreen", False)
            self.root.geometry(self.normal_geometry)
            self.status_var.set("待機中")

    def exit_fullscreen(self) -> None:
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.root.attributes("-fullscreen", False)
            self.root.geometry(self.normal_geometry)
            self.status_var.set("待機中")

    def toggle_compact(self) -> None:
        if self.is_fullscreen:
            self.exit_fullscreen()
        self.is_compact = not self.is_compact
        if self.is_compact:
            self.normal_geometry = self.root.geometry()
            self._hide_for_compact()
            self.root.geometry("430x108")
            self.root.minsize(320, 90)
            self.status_var.set("ミニ表示")
        else:
            self._show_full_ui()
            self.root.minsize(420, 420)
            self.root.geometry(self.normal_geometry)
            self.status_var.set("待機中")

    def _hide_for_compact(self) -> None:
        self.top_frame.pack_forget()
        self.chat_widget.pack_forget()
        self.action_frame.pack_forget()

    def _show_full_ui(self) -> None:
        self.top_frame.pack(fill=tk.X, pady=(0, 10))
        self.chat_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.input_frame.pack(fill=tk.X, pady=(0, 10))
        self.action_frame.pack(fill=tk.X)

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="整理するフォルダを選択")
        if not folder:
            return
        self.selected_folder = Path(folder).resolve()
        self.executor = FileOperationExecutor(self.selected_folder)
        self.current_plan = None
        self.apply_button.config(state=tk.DISABLED)
        self.folder_label.config(text=str(self.selected_folder))
        self._write("AI", "対象フォルダを選びました。依頼内容から司令塔が使う小型AIを選びます。")

    def send(self) -> None:
        text = self.input_var.get().strip()
        if not text:
            return
        self.input_var.set("")
        self._write("あなた", text)

        if self.work_session is not None:
            self.apply_button.config(state=tk.DISABLED)
            self.status_var.set("司令塔が専門AIを選択中")
            threading.Thread(target=self._session_worker, args=(text,), daemon=True).start()
            return

        route = self.router.route(text)
        if route is None:
            self._write("AI", f"今の棚に合う小型AIがありません。{self.router.describe_available_tasks()}。")
            return

        if route.task_id != "file_organize":
            if route.mode == "session":
                self.work_session = self.session_manager.start(route.label, route.pipeline)
                specialists = [name for name in route.pipeline if name not in ("conductor_router", "handoff_summarizer")]
                self._write("司令塔", f"「{route.label}」を開始。必要に応じて起こす専門AI: {' / '.join(specialists)}")
                self._write("AI", f"このチャットは作業セッションとして扱います。流れは {self.work_session.flow_path} に高速保存します。次の発言から司令塔AIが専門AIを1つ選び、使い終わったらhandoffだけ残して閉じます。")
                return
            self._write("AI", f"「{route.label}」は見つけましたが、このアプリではまだ実行器が未実装です。")
            return

        if self.selected_folder is None or self.executor is None:
            self._write("AI", "先に「フォルダ選択」で整理したいフォルダを選んでください。")
            return

        self.apply_button.config(state=tk.DISABLED)
        self.status_var.set(f"{route.label} 実行中")
        self._write("司令塔", f"{route.reason}、「{route.label}」を選択。呼び出す小型AI: {' → '.join(route.pipeline)}")
        threading.Thread(target=self._make_plan_worker, args=(self.selected_folder, route.pipeline), daemon=True).start()

    def _session_worker(self, text: str) -> None:
        try:
            assert self.work_session is not None
            reply = self.session_manager.talk_once(self.work_session, text)
            self.messages.put(("AI", reply))
            self.messages.put(("STATUS", "作業セッション待機中"))
        except Exception as exc:
            self.messages.put(("AI", f"作業セッションで処理できませんでした。\n{exc}"))
            self.messages.put(("STATUS", "作業セッション待機中"))

    def _make_plan_worker(self, folder: Path, pipeline: list[str]) -> None:
        try:
            plan = self.ai.make_plan(folder, pipeline=pipeline)
            assert self.executor is not None
            validated_plan = self.executor.validate_plan(plan)
            self.current_plan = validated_plan
            self.messages.put(("AI", format_plan_for_display(validated_plan)))
            self.messages.put(("STATUS", "確認待ち"))
            self.messages.put(("ENABLE_APPLY", ""))
        except Exception as exc:
            self.current_plan = None
            self.messages.put(("AI", f"整理案を作れませんでした。\n{exc}"))
            self.messages.put(("STATUS", "待機中"))

    def apply_plan(self) -> None:
        if self.current_plan is None or self.executor is None:
            return
        if not messagebox.askyesno("確認", "表示された整理案を実行しますか？削除は行いません。"):
            return
        try:
            summary = self.executor.apply_plan(self.current_plan)
            self._write("AI", summary)
            self.current_plan = None
            self.apply_button.config(state=tk.DISABLED)
            self.status_var.set("実行完了")
        except Exception as exc:
            messagebox.showerror("実行エラー", str(exc))
            self.status_var.set("実行失敗")

    def undo_last(self) -> None:
        if self.executor is None:
            self._write("AI", "フォルダを選んでから使えます。")
            return
        try:
            summary = self.executor.undo_last()
            self._write("AI", summary)
        except Exception as exc:
            messagebox.showerror("取り消しエラー", str(exc))

    def _poll_messages(self) -> None:
        while True:
            try:
                sender, text = self.messages.get_nowait()
            except queue.Empty:
                break
            if sender == "STATUS":
                self.status_var.set(text)
            elif sender == "ENABLE_APPLY":
                self.apply_button.config(state=tk.NORMAL)
            else:
                self._write(sender, text)
        self.root.after(100, self._poll_messages)

    def _write(self, sender: str, text: str) -> None:
        self.chat.config(state=tk.NORMAL)
        label = "USER" if sender == "あなた" else sender
        self.chat.insert(tk.END, f"╭─ {label}\n{text}\n╰────────────────────────\n\n")
        self.chat.see(tk.END)
        self.chat.config(state=tk.DISABLED)


class LoadingScreen:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Light Shelf AI 起動中")
        self.root.geometry("500x300")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)

        frame = tk.Frame(root, padx=22, pady=22, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="LIGHT SHELF AI", fg=CYAN, bg=BG, font=("Yu Gothic UI", 17, "bold")).pack(anchor="w")
        tk.Label(frame, text="boot sequence / checking local agent shelf", fg=MUTED, bg=BG, font=("Yu Gothic UI", 9)).pack(anchor="w", pady=(2, 16))

        self.status = tk.StringVar(value="準備中")
        tk.Label(frame, textvariable=self.status, anchor="w", fg=OK, bg=BG, font=("Yu Gothic UI", 10, "bold")).pack(fill=tk.X)

        self.log = tk.Listbox(frame, height=7, bg="#050b14", fg=TEXT, selectbackground="#173b64", relief=tk.FLAT, borderwidth=0, font=("Cascadia Mono", 9))
        self.log.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.steps: list[tuple[str, callable]] = [
            ("agentsフォルダを確認", self._check_agents),
            ("tasksフォルダを確認", self._check_tasks),
            ("小型AI定義を読み込み", self._check_agent_defs),
            ("タスク棚を読み込み", self._check_task_defs),
            ("セッション保存先を確認", self._check_session_store),
        ]
        self.index = 0
        self.root.after(200, self._run_next)

    def _run_next(self) -> None:
        if self.index >= len(self.steps):
            self.status.set("起動完了")
            self.log.insert(tk.END, "OK: 本画面を開きます")
            self.root.after(350, self._open_main)
            return

        label, check = self.steps[self.index]
        self.status.set(label)
        try:
            detail = check()
            self.log.insert(tk.END, f"OK: {detail}")
        except Exception as exc:
            self.log.insert(tk.END, f"NG: {label}")
            messagebox.showerror("起動チェック失敗", f"{label} に失敗しました。\n\n{exc}")
            self.root.destroy()
            return
        self.index += 1
        self.root.after(180, self._run_next)

    def _open_main(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.attributes("-fullscreen", False)
        MiniTaskAIApp(self.root)

    def _check_agents(self) -> str:
        path = Path(__file__).resolve().parent.parent / "micro_ai_shelf" / "default" / "agents"
        if not path.is_dir():
            raise FileNotFoundError(path)
        return str(path)

    def _check_tasks(self) -> str:
        path = Path(__file__).resolve().parent.parent / "micro_ai_shelf" / "default" / "tasks"
        if not path.is_dir():
            raise FileNotFoundError(path)
        return str(path)

    def _check_agent_defs(self) -> str:
        agents = MicroAgentRunner().list_agents()
        if not agents:
            raise RuntimeError("agents/*.json が見つかりません。")
        return f"{len(agents)}個のAIを確認"

    def _check_task_defs(self) -> str:
        router = TaskRouter()
        if not router.tasks:
            raise RuntimeError("tasks/*.json が見つかりません。")
        return f"{len(router.tasks)}個のタスクを確認"

    def _check_session_store(self) -> str:
        store = SessionStore()
        store.session_dir.mkdir(exist_ok=True)
        return str(store.session_dir)


def run_startup_self_check() -> None:
    checks: list[tuple[str, callable]] = [
        ("agents", lambda: MicroAgentRunner().list_agents()),
        ("tasks", lambda: TaskRouter().tasks),
        ("session_store", lambda: SessionStore().session_dir.mkdir(exist_ok=True)),
    ]
    for label, check in checks:
        result = check()
        if isinstance(result, list) and not result:
            raise RuntimeError(f"{label} check failed: empty")
        print(f"OK: {label}")


def main() -> None:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.35)
    except Exception:
        pass
    LoadingScreen(root)
    root.mainloop()


if __name__ == "__main__":
    main()
