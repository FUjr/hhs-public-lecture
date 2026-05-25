from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SessionRecord:
    lesson_title: str
    started_at: datetime = field(default_factory=datetime.now)
    current_stage: str = ""
    student_questions: list[tuple[str, str]] = field(default_factory=list)
    reflections: list[tuple[str, str]] = field(default_factory=list)
    teacher_summary: str = ""
    homework: str = ""

    def add_student_question(self, question: str, answer: str) -> None:
        self.student_questions.append((question.strip(), answer.strip()))

    def add_reflection(self, student_text: str, feedback: str) -> None:
        self.reflections.append((student_text.strip(), feedback.strip()))

    def save_markdown(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.strftime("%Y%m%d_%H%M%S")
        file_path = output_dir / f"{stamp}_爱莲说.md"

        lines = [
            f"# {self.lesson_title} 课堂记录",
            "",
            f"- 开始时间：{self.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 最后环节：{self.current_stage or '未记录'}",
            "",
            "## 学生向 AI 提问",
            "",
        ]

        if self.student_questions:
            for index, (question, answer) in enumerate(self.student_questions, start=1):
                lines.extend(
                    [
                        f"### 问题 {index}",
                        question,
                        "",
                        "AI 回答：",
                        answer,
                        "",
                    ]
                )
        else:
            lines.append("本节课未记录学生向 AI 的提问。")
            lines.append("")

        lines.extend(["## AI 向学生提问与回应", ""])

        if self.reflections:
            for index, (student_text, feedback) in enumerate(self.reflections, start=1):
                lines.extend(
                    [
                        f"### 观点 {index}",
                        student_text,
                        "",
                        "AI 点评：",
                        feedback,
                        "",
                    ]
                )
        else:
            lines.append("本节课未记录学生观点。")
            lines.append("")

        lines.extend(
            [
                "## 教师总结",
                "",
                self.teacher_summary.strip() or "未填写。",
                "",
                "## 作业布置",
                "",
                self.homework.strip() or "未填写。",
                "",
            ]
        )

        file_path.write_text("\n".join(lines), encoding="utf-8")
        return file_path
