"""
AdBot GUI - 오늘의트렌드 자동 포스팅 데스크탑 앱
실행: python src/gui.py  (프로젝트 루트에서)
"""

import os
import sys
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 작업 디렉터리로 설정 (상대 경로 logs/, config/ 정상화)
_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_ROOT)
sys.path.insert(0, str(_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv()

# ── 색상 팔레트 ───────────────────────────────────────────────
BG_MAIN   = "#0d1b2a"
BG_CARD   = "#142035"
BG_INPUT  = "#1e3a5f"
GOLD      = "#f0c040"
WHITE     = "#ffffff"
GRAY      = "#8899aa"
GREEN_LOG = "#00e676"
BTN_START = "#e6a817"
BTN_STOP  = "#4a4a4a"
BTN_STATS = "#1565c0"
BORDER    = "#2a3f5f"

LOG_PATH = _ROOT / "logs" / "upload_log.json"


# ── 큐 기반 stdout 리다이렉터 ─────────────────────────────────

class _QueueWriter:
    def __init__(self, q: queue.Queue):
        self._q = q

    def write(self, text: str):
        if text and text.strip():
            self._q.put(text.rstrip("\n"))

    def flush(self):
        pass


# ── 메인 GUI 클래스 ───────────────────────────────────────────

class AdBotGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AdBot - 오늘의트렌드 자동 포스팅")
        self.root.geometry("720x640")
        self.root.configure(bg=BG_MAIN)
        self.root.resizable(False, False)

        self._running = False
        self._thread: threading.Thread | None = None
        self._log_queue: queue.Queue = queue.Queue()

        self._build_ui()
        self._poll_log()

    # ── UI 구성 ──────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_settings()
        self._build_buttons()
        self._build_log()
        self._build_statusbar()

    def _build_header(self):
        frm = tk.Frame(self.root, bg=BG_MAIN)
        frm.pack(fill="x", padx=32, pady=(24, 4))

        title_frm = tk.Frame(frm, bg=BG_MAIN)
        title_frm.pack()
        tk.Label(title_frm, text="오늘의트렌드 ", font=("맑은 고딕", 22, "bold"),
                 bg=BG_MAIN, fg=WHITE).pack(side="left")
        tk.Label(title_frm, text="AdBot", font=("맑은 고딕", 22, "bold"),
                 bg=BG_MAIN, fg=GOLD).pack(side="left")

        tk.Label(self.root, text="재테크 · AI · 트렌드 자동 포스팅",
                 font=("맑은 고딕", 10), bg=BG_MAIN, fg=GRAY).pack()

        tk.Frame(self.root, height=2, bg=GOLD).pack(fill="x", padx=32, pady=(10, 14))

    def _build_settings(self):
        card = tk.Frame(self.root, bg=BG_CARD, bd=0, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill="x", padx=32, pady=2)

        # 생성할 글 수
        self.count_var = tk.IntVar(value=3)
        row = self._card_row(card, "생성할 글 수:")
        for val, label in [(1, "1개"), (2, "2개"), (3, "3개"), (5, "5개")]:
            tk.Radiobutton(row, text=label, variable=self.count_var, value=val,
                           bg=BG_CARD, fg=WHITE, selectcolor=BG_INPUT,
                           activebackground=BG_CARD, activeforeground=WHITE,
                           font=("맑은 고딕", 10)).pack(side="left", padx=10)

        # 발행 모드
        self.draft_var = tk.BooleanVar(value=True)
        row2 = self._card_row(card, "발행 모드:")
        for val, label in [(False, "즉시 발행"), (True, "초안 저장")]:
            tk.Radiobutton(row2, text=label, variable=self.draft_var, value=val,
                           bg=BG_CARD, fg=WHITE, selectcolor=BG_INPUT,
                           activebackground=BG_CARD, activeforeground=WHITE,
                           font=("맑은 고딕", 10)).pack(side="left", padx=10)

        # 키워드 (선택)
        row3 = self._card_row(card, "키워드 (선택):", pady_bottom=14)
        self.keyword_var = tk.StringVar()
        entry = tk.Entry(row3, textvariable=self.keyword_var,
                         bg=BG_INPUT, fg=WHITE, insertbackground=WHITE,
                         font=("맑은 고딕", 11), relief="flat", bd=6, width=24)
        entry.pack(side="left", padx=(0, 8))

        tk.Button(row3, text="비우면 자동수집",
                  bg="#253a55", fg=GRAY, activebackground="#2e4b6a",
                  font=("맑은 고딕", 9), relief="flat", padx=8, pady=4,
                  cursor="hand2",
                  command=lambda: self.keyword_var.set("")).pack(side="left")

    def _card_row(self, parent, label_text: str, pady_bottom: int = 8) -> tk.Frame:
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", padx=20, pady=(12, pady_bottom))
        tk.Label(row, text=label_text, font=("맑은 고딕", 11),
                 bg=BG_CARD, fg=WHITE, width=13, anchor="w").pack(side="left")
        return row

    def _build_buttons(self):
        frm = tk.Frame(self.root, bg=BG_MAIN)
        frm.pack(pady=16)

        self.btn_start = tk.Button(
            frm, text="► 포스팅 시작",
            font=("맑은 고딕", 13, "bold"),
            bg=BTN_START, fg="#1a1a1a", activebackground="#d4920f",
            relief="flat", padx=24, pady=10, cursor="hand2",
            command=self._on_start)
        self.btn_start.pack(side="left", padx=6)

        self.btn_stop = tk.Button(
            frm, text="■ 중지",
            font=("맑은 고딕", 12),
            bg=BTN_STOP, fg=WHITE, activebackground="#666",
            relief="flat", padx=18, pady=10, state="disabled", cursor="hand2",
            command=self._on_stop)
        self.btn_stop.pack(side="left", padx=6)

        tk.Button(
            frm, text="통계",
            font=("맑은 고딕", 12),
            bg=BTN_STATS, fg=WHITE, activebackground="#1976d2",
            relief="flat", padx=18, pady=10, cursor="hand2",
            command=self._on_stats).pack(side="left", padx=6)

    def _build_log(self):
        frm = tk.Frame(self.root, bg=BG_MAIN)
        frm.pack(fill="both", expand=True, padx=32, pady=(0, 4))

        self.log_text = tk.Text(
            frm, bg=BG_CARD, fg=GREEN_LOG,
            font=("Consolas", 9), relief="flat",
            state="disabled", wrap="word",
            highlightbackground=BORDER, highlightthickness=1)
        sb = tk.Scrollbar(frm, command=self.log_text.yview,
                          bg=BG_CARD, troughcolor=BG_MAIN, relief="flat")
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="준비")
        bar = tk.Frame(self.root, bg=BORDER, height=1)
        bar.pack(fill="x", padx=0)
        tk.Label(self.root, textvariable=self.status_var,
                 font=("맑은 고딕", 9), bg=BG_MAIN, fg=GRAY,
                 anchor="w").pack(fill="x", padx=32, pady=(2, 6))

    # ── 이벤트 핸들러 ─────────────────────────────────────────

    def _on_start(self):
        if self._running:
            return
        self._running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_var.set("실행 중...")

        count = self.count_var.get()
        draft = self.draft_var.get()
        keyword = self.keyword_var.get().strip() or None

        self._thread = threading.Thread(
            target=self._worker, args=(count, draft, keyword), daemon=True)
        self._thread.start()

    def _on_stop(self):
        self._running = False
        self._push_log("⚠ 중지 요청됨 (현재 작업 완료 후 종료)")
        self.btn_stop.configure(state="disabled")
        self.status_var.set("중지 중...")

    def _on_stats(self):
        if not LOG_PATH.exists():
            self._push_log("📊 아직 발행된 글이 없습니다.")
            return
        with open(LOG_PATH, encoding="utf-8") as f:
            logs = json.load(f)
        pub = sum(1 for l in logs if l.get("status") == "published")
        dft = sum(1 for l in logs if l.get("status") == "draft")
        last = logs[-1]["timestamp"][:10] if logs else "-"
        self._push_log(
            f"📊 통계 | 전체 {len(logs)}개  발행 {pub}개  초안 {dft}개  마지막: {last}")
        self._push_log("─" * 50)

    # ── 백그라운드 워커 ──────────────────────────────────────

    def _worker(self, count: int, draft: bool, keyword: str | None):
        old_stdout = sys.stdout
        sys.stdout = _QueueWriter(self._log_queue)
        try:
            from main import run_pipeline
            run_pipeline(count=count, draft=draft, specific_keyword=keyword)
        except Exception as e:
            self._push_log(f"[오류] {e}")
        finally:
            sys.stdout = old_stdout
            self._running = False
            self.root.after(0, self._on_done)

    def _on_done(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_var.set("완료")

    # ── 로그 큐 폴링 ─────────────────────────────────────────

    def _push_log(self, msg: str):
        self._log_queue.put(msg)

    def _poll_log(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(80, self._poll_log)


# ── 진입점 ────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    AdBotGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
