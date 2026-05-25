from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ai_provider import RemoteLessonAI
from lesson_config import AilianShuoLesson, FlowerSymbol, LessonConfig
from session_record import SessionRecord


class ClassroomAssistantApp:
    BG = "#F5F0E6"
    CARD = "#FBF8F1"
    PRIMARY = "#23423A"
    PRIMARY_SOFT = "#DCE6E1"
    ACCENT = "#D7928B"
    TEXT = "#2D2926"
    SUBTLE = "#6F655D"
    BORDER = "#CFC3B6"

    def __init__(self, root: tk.Tk, lesson: LessonConfig) -> None:
        self.root = root
        self.lesson = lesson
        self.record = SessionRecord(lesson_title=lesson.lesson_title)
        self.ai = RemoteLessonAI(reflection_prompt=lesson.reflection_prompt)

        self.current_stage_index = 0
        self.flower_labels: dict[str, tk.Label] = {}
        self.revealed_traits: set[int] = set()

        self.question_var = tk.StringVar()
        self.stage_var = tk.StringVar()
        self.ai_mode_var = tk.StringVar()
        self.status_var = tk.StringVar(value="演示模式已就绪，可直接开始课堂。")

        self._configure_root()
        self._build_styles()
        self._build_layout()
        self.show_stage(0)

    def _configure_root(self) -> None:
        self.root.title(self.lesson.lesson_title)
        self.root.geometry("1366x820")
        self.root.minsize(1180, 720)
        self.root.configure(bg=self.BG)

    def _build_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("App.TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.CARD, relief="flat")
        style.configure("Stage.TLabel", background=self.BG, foreground=self.PRIMARY, font=("Microsoft YaHei UI", 13, "bold"))
        style.configure("Title.TLabel", background=self.BG, foreground=self.PRIMARY, font=("Microsoft YaHei UI", 26, "bold"))
        style.configure("Subtitle.TLabel", background=self.BG, foreground=self.SUBTLE, font=("Microsoft YaHei UI", 12))
        style.configure("CardTitle.TLabel", background=self.CARD, foreground=self.PRIMARY, font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Body.TLabel", background=self.CARD, foreground=self.TEXT, font=("Microsoft YaHei UI", 12), wraplength=1080, justify="left")
        style.configure("Hint.TLabel", background=self.CARD, foreground=self.SUBTLE, font=("Microsoft YaHei UI", 11), wraplength=1080, justify="left")
        style.configure("Action.TButton", font=("Microsoft YaHei UI", 12, "bold"), padding=(16, 10))
        style.map(
            "Action.TButton",
            background=[("active", self.ACCENT), ("!disabled", self.PRIMARY)],
            foreground=[("!disabled", "#FFFFFF")],
        )
        style.configure("Secondary.TButton", font=("Microsoft YaHei UI", 11), padding=(14, 8))
        style.map(
            "Secondary.TButton",
            background=[("active", self.PRIMARY_SOFT), ("!disabled", self.CARD)],
            foreground=[("!disabled", self.PRIMARY)],
            bordercolor=[("!disabled", self.BORDER)],
        )

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame", padding=24)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="App.TFrame")
        header.pack(fill="x")

        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)

        ttk.Label(title_block, text=self.lesson.lesson_title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_block, text=self.lesson.subtitle, style="Subtitle.TLabel").pack(anchor="w", pady=(4, 0))
        self.ai_mode_label = tk.Label(
            title_block,
            textvariable=self.ai_mode_var,
            bg=self.BG,
            fg=self.ACCENT,
            font=("Microsoft YaHei UI", 11, "bold"),
            anchor="w",
        )
        self.ai_mode_label.pack(anchor="w", pady=(6, 0))

        stage_badge = tk.Label(
            header,
            textvariable=self.stage_var,
            bg=self.PRIMARY,
            fg="#FFFFFF",
            font=("Microsoft YaHei UI", 12, "bold"),
            padx=18,
            pady=10,
        )
        stage_badge.pack(side="right", anchor="ne")

        self.content = ttk.Frame(outer, style="App.TFrame")
        self.content.pack(fill="both", expand=True, pady=(18, 16))

        footer = ttk.Frame(outer, style="App.TFrame")
        footer.pack(fill="x")

        self.status_label = ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel")
        self.status_label.pack(side="left", anchor="w")

        nav = ttk.Frame(footer, style="App.TFrame")
        nav.pack(side="right")

        self.prev_button = ttk.Button(nav, text="上一步", style="Secondary.TButton", command=self.go_previous)
        self.prev_button.pack(side="left", padx=(0, 10))
        self.next_button = ttk.Button(nav, text="下一步", style="Action.TButton", command=self.go_next)
        self.next_button.pack(side="left")
        self._refresh_ai_mode_status()

    def clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def show_stage(self, index: int) -> None:
        self.current_stage_index = index
        stage_name = self.lesson.stage_names[index]
        self.record.current_stage = stage_name
        self.stage_var.set(stage_name)

        self.clear_content()
        builders = [
            self._build_preview_stage,
            self._build_reading_stage,
            self._build_student_ai_stage,
            self._build_ai_student_stage,
            self._build_teacher_wrap_stage,
        ]
        builders[index]()

        self.prev_button.state(["!disabled"] if index > 0 else ["disabled"])
        if index == len(self.lesson.stage_names) - 1:
            self.next_button.configure(text="保存并结束", command=self.finish_session)
        else:
            self.next_button.configure(text="下一步", command=self.go_next)

    def go_previous(self) -> None:
        if self.current_stage_index > 0:
            self.show_stage(self.current_stage_index - 1)

    def go_next(self) -> None:
        if self.current_stage_index < len(self.lesson.stage_names) - 1:
            self.show_stage(self.current_stage_index + 1)

    def _refresh_ai_mode_status(self) -> None:
        self.ai_mode_var.set(self.ai.get_runtime_status())

    def finish_session(self) -> None:
        self.record.current_stage = self.lesson.stage_names[-1]
        self.record.teacher_summary = self.summary_text.get("1.0", "end").strip()
        self.record.homework = self.homework_text.get("1.0", "end").strip()

        output_path = self.record.save_markdown(Path.cwd() / "session_logs")
        self.status_var.set(f"课堂记录已保存：{output_path.name}")
        messagebox.showinfo("保存完成", f"本节课记录已保存到：\n{output_path}")

    def _card(self, parent: ttk.Frame, title: str, subtitle: str | None = None) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=22)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(card, text=subtitle, style="Hint.TLabel").pack(anchor="w", pady=(8, 0))
        return card

    def _build_preview_stage(self) -> None:
        card = self._card(self.content, "课前过渡", self.lesson.preview_tip)
        card.pack(fill="both", expand=True, pady=10)
        ttk.Label(card, text=self.lesson.preview_message, style="Body.TLabel").pack(anchor="w", pady=(18, 0))

        banner = tk.Label(
            card,
            text="已完成字词与翻译预习，课堂进入深度理解。",
            bg=self.PRIMARY_SOFT,
            fg=self.PRIMARY,
            font=("Microsoft YaHei UI", 18, "bold"),
            padx=22,
            pady=18,
        )
        banner.pack(fill="x", pady=28)

        ttk.Button(card, text="进入正文学习", style="Action.TButton", command=self.go_next).pack(anchor="e", pady=(8, 0))

    def _build_reading_stage(self) -> None:
        wrapper = ttk.Frame(self.content, style="App.TFrame")
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(0, weight=1)
        wrapper.columnconfigure(1, weight=1)
        wrapper.rowconfigure(0, weight=1)

        self.flower_labels = {}

        left = self._card(
            wrapper,
            "三种花分别代表怎样的人",
            "点击卡片揭晓答案，帮助学生回到课文中的象征意义。",
        )
        left.configure(padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 12))

        for symbol in self.lesson.flower_symbols:
            self._build_flower_button(left, symbol)

        right = self._card(
            wrapper,
            "莲具有怎样的品质",
            "依次点开关键句的理解，用于梳理君子品格。",
        )
        right.configure(padding=18)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 12))

        traits_frame = ttk.Frame(right, style="Card.TFrame")
        traits_frame.pack(fill="x", pady=(10, 0))
        for index, trait in enumerate(self.lesson.lotus_traits):
            text = f"品质 {index + 1}"
            button = tk.Button(
                traits_frame,
                text=text,
                command=lambda idx=index: self._reveal_trait(idx),
                bg="#FFFFFF",
                fg=self.PRIMARY,
                activebackground=self.PRIMARY_SOFT,
                activeforeground=self.PRIMARY,
                font=("Microsoft YaHei UI", 11, "bold"),
                bd=1,
                relief="solid",
                wraplength=460,
                padx=14,
                pady=8,
            )
            button.pack(fill="x", pady=4)

        self.trait_output = tk.Text(
            right,
            height=10,
            wrap="word",
            bg="#FFFFFF",
            fg=self.TEXT,
            font=("Microsoft YaHei UI", 12),
            relief="flat",
            padx=12,
            pady=12,
        )
        self.trait_output.pack(fill="both", expand=True, pady=(14, 0))
        self.trait_output.insert("1.0", "点击右侧按钮，逐项揭晓莲花的品质。")
        self.trait_output.configure(state="disabled")

        action_bar = ttk.Frame(wrapper, style="App.TFrame")
        action_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        action_bar.columnconfigure(0, weight=1)

        ttk.Label(
            action_bar,
            text="完成这一轮梳理后，可直接进入“学生向 AI 提问”环节。",
            style="Subtitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            action_bar,
            text="进入学生问 AI",
            style="Action.TButton",
            command=self.go_next,
        ).grid(row=0, column=1, sticky="e")

        self.status_var.set("可先引导学生说出答案，再点击揭晓，保持课堂节奏。")

    def _build_flower_button(self, parent: ttk.Frame, symbol: FlowerSymbol) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill="x", pady=8)

        button = tk.Button(
            frame,
            text=f"{symbol.flower} 花",
            command=lambda item=symbol: self._reveal_flower(item),
            bg="#FFFFFF",
            fg=self.PRIMARY,
            activebackground=self.PRIMARY_SOFT,
            activeforeground=self.PRIMARY,
            font=("Microsoft YaHei UI", 12, "bold"),
            bd=1,
            relief="solid",
            padx=16,
            pady=12,
            width=12,
        )
        button.pack(side="left")

        label = tk.Label(
            frame,
            text="点击揭晓",
            bg=self.CARD,
            fg=self.SUBTLE,
            font=("Microsoft YaHei UI", 11),
            anchor="w",
            justify="left",
            wraplength=320,
        )
        label.pack(side="left", fill="x", expand=True, padx=(14, 0))
        self.flower_labels[symbol.flower] = label

    def _reveal_flower(self, symbol: FlowerSymbol) -> None:
        answer_label = self.flower_labels.get(symbol.flower)
        if answer_label is not None:
            answer_label.configure(text=f"{symbol.symbol}：{symbol.summary}", fg=self.TEXT)
        self.status_var.set(f"已揭晓：{symbol.flower} 象征{symbol.symbol}。")

    def _reveal_trait(self, index: int) -> None:
        self.revealed_traits.add(index)
        content = [self.lesson.lotus_traits[i] for i in sorted(self.revealed_traits)]
        self.trait_output.configure(state="normal")
        self.trait_output.delete("1.0", "end")
        self.trait_output.insert("1.0", "\n\n".join(content))
        self.trait_output.configure(state="disabled")
        self.status_var.set(f"已揭晓 {len(self.revealed_traits)} 项莲的品质。")

    def _build_student_ai_stage(self) -> None:
        wrapper = ttk.Frame(self.content, style="App.TFrame")
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(0, weight=5)
        wrapper.columnconfigure(1, weight=6)
        wrapper.rowconfigure(0, weight=1)

        left = self._card(
            wrapper,
            "学生向 AI 提问",
            "这一环节不直接给出现成问题，而是用提示语引导学生把问题问得更深入。",
        )
        left.configure(padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 12))

        ttk.Label(left, text="提问提示", style="CardTitle.TLabel").pack(anchor="w", pady=(12, 6))
        guidance_box = ttk.Frame(left, style="Card.TFrame")
        guidance_box.pack(fill="x", pady=(4, 0))

        for tip in self.lesson.question_guidance:
            tip_card = tk.Label(
                guidance_box,
                text=f"• {tip}",
                bg="#FFFFFF",
                fg=self.TEXT,
                font=("Microsoft YaHei UI", 11),
                justify="left",
                anchor="w",
                wraplength=420,
                padx=14,
                pady=10,
                bd=1,
                relief="solid",
            )
            tip_card.pack(fill="x", pady=4)

        ttk.Label(left, text="自由输入问题", style="CardTitle.TLabel").pack(anchor="w", pady=(20, 6))
        entry = tk.Entry(
            left,
            textvariable=self.question_var,
            font=("Microsoft YaHei UI", 12),
            relief="solid",
            bd=1,
        )
        entry.pack(fill="x", ipady=10)
        entry.bind("<Return>", lambda _event: self._ask_question(self.question_var.get()))

        ttk.Button(left, text="提交问题", style="Action.TButton", command=lambda: self._ask_question(self.question_var.get())).pack(
            anchor="e",
            pady=(14, 0),
        )

        right = self._card(
            wrapper,
            "AI 回答区",
            "回答会围绕课文内容展开，并自然回扣莲“出淤泥而不染”的核心品质。",
        )
        right.configure(padding=18)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 12))

        self.answer_text = tk.Text(
            right,
            wrap="word",
            bg="#FFFFFF",
            fg=self.TEXT,
            font=("Microsoft YaHei UI", 12),
            relief="flat",
            padx=14,
            pady=14,
        )
        self.answer_text.pack(side="left", fill="both", expand=True, pady=(12, 0))

        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.answer_text.yview)
        scrollbar.pack(side="right", fill="y", pady=(12, 0))
        self.answer_text.configure(yscrollcommand=scrollbar.set)
        self.answer_text.insert("1.0", "请先根据左侧提示组织问题，再输入学生在课堂上的真实提问。")
        self.answer_text.configure(state="disabled")

        action_bar = ttk.Frame(wrapper, style="App.TFrame")
        action_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        action_bar.columnconfigure(0, weight=1)

        ttk.Label(
            action_bar,
            text="完成这一轮提问后，可直接进入“AI 向学生提问”环节。",
            style="Subtitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            action_bar,
            text="进入 AI 问学生",
            style="Action.TButton",
            command=self.go_next,
        ).grid(row=0, column=1, sticky="e")

        self.status_var.set("这一环节建议让学生先自主组织问题，再由教师代输入。")

    def _ask_question(self, question: str) -> None:
        cleaned = question.strip()
        if not cleaned:
            self.status_var.set("请先输入一个问题。")
            return

        answer = self.ai.answer_student_question(cleaned, self.lesson.preview_tip)
        self._refresh_ai_mode_status()
        self.record.add_student_question(cleaned, answer)
        self.question_var.set("")

        self.answer_text.configure(state="normal")
        self.answer_text.delete("1.0", "end")
        self.answer_text.insert("1.0", f"学生问题：{cleaned}\n\nAI 回答：\n{answer}")
        self.answer_text.configure(state="disabled")
        self.status_var.set("AI 已生成回答，可继续追问或切换下一环节。")

    def _build_ai_student_stage(self) -> None:
        wrapper = ttk.Frame(self.content, style="App.TFrame")
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(0, weight=5)
        wrapper.columnconfigure(1, weight=5)

        left = self._card(
            wrapper,
            "AI 向学生提问",
            self.lesson.reflection_prompt_hint,
        )
        left.configure(padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        prompt_label = tk.Label(
            left,
            text=self.ai.get_reflection_prompt(),
            bg=self.PRIMARY_SOFT,
            fg=self.PRIMARY,
            font=("Microsoft YaHei UI", 16, "bold"),
            justify="left",
            wraplength=500,
            padx=18,
            pady=18,
        )
        prompt_label.pack(fill="x", pady=(14, 0))

        ttk.Label(left, text="教师代输全班讨论后的观点", style="CardTitle.TLabel").pack(anchor="w", pady=(22, 6))

        self.reflection_input = tk.Text(
            left,
            height=12,
            wrap="word",
            bg="#FFFFFF",
            fg=self.TEXT,
            font=("Microsoft YaHei UI", 12),
            relief="flat",
            padx=12,
            pady=12,
        )
        self.reflection_input.pack(fill="both", expand=True)

        ttk.Button(left, text="生成点评", style="Action.TButton", command=self._respond_to_reflection).pack(anchor="e", pady=(14, 0))

        right = self._card(
            wrapper,
            "AI 点评",
            "这里会生成更自然的课堂回应，帮助学生把观点和课文主旨连起来。",
        )
        right.configure(padding=18)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.reflection_output = tk.Text(
            right,
            wrap="word",
            bg="#FFFFFF",
            fg=self.TEXT,
            font=("Microsoft YaHei UI", 12),
            relief="flat",
            padx=14,
            pady=14,
        )
        self.reflection_output.pack(side="left", fill="both", expand=True, pady=(12, 0))

        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.reflection_output.yview)
        scrollbar.pack(side="right", fill="y", pady=(12, 0))
        self.reflection_output.configure(yscrollcommand=scrollbar.set)
        self.reflection_output.insert("1.0", "输入学生观点后，这里会生成课堂点评。")
        self.reflection_output.configure(state="disabled")

        self.status_var.set("这一环节建议先口头讨论，再由教师代表输入观点。")

    def _respond_to_reflection(self) -> None:
        student_text = self.reflection_input.get("1.0", "end").strip()
        feedback = self.ai.respond_to_reflection(student_text)
        self._refresh_ai_mode_status()
        self.record.add_reflection(student_text, feedback)

        self.reflection_output.configure(state="normal")
        self.reflection_output.delete("1.0", "end")
        self.reflection_output.insert("1.0", feedback)
        self.reflection_output.configure(state="disabled")
        self.status_var.set("AI 已完成点评，可继续补充观点或进入总结。")

    def _build_teacher_wrap_stage(self) -> None:
        wrapper = ttk.Frame(self.content, style="App.TFrame")
        wrapper.pack(fill="both", expand=True)
        wrapper.columnconfigure(0, weight=1)
        wrapper.columnconfigure(1, weight=1)

        left = self._card(
            wrapper,
            "教师总结",
            "系统先提供总结模板，教师可根据课堂实际进行微调。",
        )
        left.configure(padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.summary_text = tk.Text(
            left,
            wrap="word",
            bg="#FFFFFF",
            fg=self.TEXT,
            font=("Microsoft YaHei UI", 12),
            relief="flat",
            padx=14,
            pady=14,
        )
        self.summary_text.pack(fill="both", expand=True, pady=(12, 0))
        self.summary_text.insert("1.0", self.record.teacher_summary or self.lesson.teacher_summary_template)

        right = self._card(
            wrapper,
            "作业布置",
            "默认给出两项作业建议，可按班级情况现场修改。",
        )
        right.configure(padding=18)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.homework_text = tk.Text(
            right,
            wrap="word",
            bg="#FFFFFF",
            fg=self.TEXT,
            font=("Microsoft YaHei UI", 12),
            relief="flat",
            padx=14,
            pady=14,
        )
        self.homework_text.pack(fill="both", expand=True, pady=(12, 0))
        self.homework_text.insert("1.0", self.record.homework or self.lesson.homework_template)

        self.status_var.set("确认总结与作业后，点击右下角保存并结束。")


def main() -> None:
    root = tk.Tk()
    app = ClassroomAssistantApp(root, AilianShuoLesson)
    root.mainloop()


if __name__ == "__main__":
    main()
