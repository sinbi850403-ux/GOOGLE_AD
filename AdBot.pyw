"""
AdBot GUI - 버튼 하나로 자동 블로그 포스팅
더블클릭으로 실행 (터미널 없음)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")


class AdBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AdBot - 오늘의트렌드 자동 포스팅")
        self.root.geometry("700x600")
        self.root.configure(bg="#0a0f2e")
        self.root.resizable(False, False)

        self.running = False
        self._build_ui()

    def _build_ui(self):
        # ── 헤더 ──────────────────────────────
        header = tk.Frame(self.root, bg="#0a0f2e")
        header.pack(fill="x", pady=(20, 10))

        tk.Label(header, text="오늘의트렌드 AdBot",
                 font=("Arial Black", 20, "bold"),
                 bg="#0a0f2e", fg="white").pack()
        tk.Label(header, text="재테크 · AI · 트렌드 자동 포스팅",
                 font=("Arial", 11),
                 bg="#0a0f2e", fg="#a0c4ff").pack()

        # 골드 구분선
        tk.Frame(self.root, bg="#f0c040", height=2).pack(fill="x", padx=40, pady=8)

        # ── 설정 패널 ──────────────────────────
        settings = tk.Frame(self.root, bg="#0d1f4f", bd=0)
        settings.pack(fill="x", padx=30, pady=8)

        # 글 수
        row1 = tk.Frame(settings, bg="#0d1f4f")
        row1.pack(fill="x", padx=20, pady=12)

        tk.Label(row1, text="생성할 글 수:", font=("Arial", 12),
                 bg="#0d1f4f", fg="white", width=14, anchor="w").pack(side="left")
        self.count_var = tk.IntVar(value=3)
        for i in [1, 2, 3, 5]:
            tk.Radiobutton(row1, text=f"{i}개", variable=self.count_var, value=i,
                           font=("Arial", 11), bg="#0d1f4f", fg="#a0c4ff",
                           selectcolor="#1a3a6e", activebackground="#0d1f4f",
                           activeforeground="white").pack(side="left", padx=8)

        # 발행 모드
        row2 = tk.Frame(settings, bg="#0d1f4f")
        row2.pack(fill="x", padx=20, pady=(0, 12))

        tk.Label(row2, text="발행 모드:", font=("Arial", 12),
                 bg="#0d1f4f", fg="white", width=14, anchor="w").pack(side="left")
        self.draft_var = tk.BooleanVar(value=False)
        tk.Radiobutton(row2, text="즉시 발행", variable=self.draft_var, value=False,
                       font=("Arial", 11), bg="#0d1f4f", fg="#a0c4ff",
                       selectcolor="#1a3a6e", activebackground="#0d1f4f").pack(side="left", padx=8)
        tk.Radiobutton(row2, text="초안 저장", variable=self.draft_var, value=True,
                       font=("Arial", 11), bg="#0d1f4f", fg="#a0c4ff",
                       selectcolor="#1a3a6e", activebackground="#0d1f4f").pack(side="left", padx=8)

        # 키워드 직접 입력
        row3 = tk.Frame(settings, bg="#0d1f4f")
        row3.pack(fill="x", padx=20, pady=(0, 15))

        tk.Label(row3, text="키워드 (선택):", font=("Arial", 12),
                 bg="#0d1f4f", fg="white", width=14, anchor="w").pack(side="left")
        self.keyword_var = tk.StringVar()
        tk.Entry(row3, textvariable=self.keyword_var,
                 font=("Arial", 11), width=30,
                 bg="#1a3a6e", fg="white", insertbackground="white",
                 relief="flat", bd=4).pack(side="left", padx=4)
        tk.Label(row3, text="비우면 자동수집", font=("Arial", 9),
                 bg="#0d1f4f", fg="#666").pack(side="left", padx=4)

        # ── 버튼들 ────────────────────────────
        btn_frame = tk.Frame(self.root, bg="#0a0f2e")
        btn_frame.pack(pady=12)

        self.run_btn = tk.Button(
            btn_frame, text="▶  포스팅 시작",
            font=("Arial Black", 14), width=16,
            bg="#f0c040", fg="#0a0f2e",
            activebackground="#ffdf80", activeforeground="#0a0f2e",
            relief="flat", bd=0, pady=10,
            command=self.start_bot
        )
        self.run_btn.pack(side="left", padx=8)

        self.stop_btn = tk.Button(
            btn_frame, text="■  중지",
            font=("Arial", 12), width=8,
            bg="#333", fg="white",
            activebackground="#555",
            relief="flat", bd=0, pady=10,
            command=self.stop_bot, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=8)

        tk.Button(
            btn_frame, text="통계",
            font=("Arial", 12), width=6,
            bg="#1a3a6e", fg="#a0c4ff",
            activebackground="#2a4a8e",
            relief="flat", bd=0, pady=10,
            command=self.show_stats
        ).pack(side="left", padx=8)

        # ── 로그 출력창 ───────────────────────
        tk.Frame(self.root, bg="#f0c040", height=1).pack(fill="x", padx=30)

        self.log = scrolledtext.ScrolledText(
            self.root, height=12, font=("Consolas", 10),
            bg="#060a1a", fg="#a0c4ff",
            insertbackground="white", relief="flat",
            state="disabled"
        )
        self.log.pack(fill="both", expand=True, padx=30, pady=10)

        # 상태바
        self.status_var = tk.StringVar(value="대기 중...")
        tk.Label(self.root, textvariable=self.status_var,
                 font=("Arial", 9), bg="#0a0f2e", fg="#666").pack(pady=(0, 8))

        self._log("AdBot 준비 완료. '포스팅 시작' 버튼을 누르세요.\n")

    # ── 로그 출력 ──────────────────────────────
    def _log(self, msg: str):
        self.log.config(state="normal")
        self.log.insert("end", msg)
        self.log.see("end")
        self.log.config(state="disabled")

    def _set_status(self, msg: str):
        self.status_var.set(msg)

    # ── 봇 실행 ───────────────────────────────
    def start_bot(self):
        if self.running:
            return
        self.running = True
        self.run_btn.config(state="disabled", bg="#888")
        self.stop_btn.config(state="normal")
        self._log("\n" + "="*50 + "\n")

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    def _run_pipeline(self):
        count = self.count_var.get()
        draft = self.draft_var.get()
        keyword = self.keyword_var.get().strip()

        cmd = [sys.executable, "main.py", "--count", str(count)]
        if draft:
            cmd.append("--draft")
        if keyword:
            cmd += ["--keyword", keyword]

        self._log(f"실행: {' '.join(cmd)}\n")
        self._set_status("실행 중...")

        try:
            process = subprocess.Popen(
                cmd, cwd=SRC_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            self.process = process

            for line in process.stdout:
                self.root.after(0, self._log, line)

            process.wait()
            self.root.after(0, self._done)

        except Exception as e:
            self.root.after(0, self._log, f"\n[오류] {e}\n")
            self.root.after(0, self._done)

    def _done(self):
        self.running = False
        self.run_btn.config(state="normal", bg="#f0c040")
        self.stop_btn.config(state="disabled")
        self._log("\n완료!\n" + "="*50 + "\n")
        self._set_status("완료")

    def stop_bot(self):
        if hasattr(self, "process"):
            self.process.terminate()
        self.running = False
        self.run_btn.config(state="normal", bg="#f0c040")
        self.stop_btn.config(state="disabled")
        self._log("\n[중지됨]\n")
        self._set_status("중지됨")

    # ── 통계 ──────────────────────────────────
    def show_stats(self):
        try:
            result = subprocess.run(
                [sys.executable, "main.py", "--stats"],
                cwd=SRC_DIR, capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            )
            messagebox.showinfo("업로드 통계", result.stdout or "통계 없음")
        except Exception as e:
            messagebox.showerror("오류", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = AdBotApp(root)
    root.mainloop()
