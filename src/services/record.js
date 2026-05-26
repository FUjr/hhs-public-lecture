function pad(value) {
  return String(value).padStart(2, "0");
}

function timestamp(date = new Date()) {
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

export function buildSessionMarkdown(lesson, studentQuestions, reflections) {
  const lines = [
    `# ${lesson.title || "课堂"} 课堂记录`,
    "",
    `- 生成时间：${new Date().toLocaleString("zh-CN")}`,
    "",
    "## 学生向 AI 提问",
    "",
  ];

  if (studentQuestions.length) {
    studentQuestions.forEach((item, index) => {
      lines.push(`### 问题 ${index + 1}`, item.question, "", "AI 回答：", item.answer, "");
    });
  } else {
    lines.push("本节课未记录学生向 AI 的提问。", "");
  }

  lines.push("## AI 向学生提问与回应", "");
  if (reflections.length) {
    reflections.forEach((item, index) => {
      lines.push(`### 观点 ${index + 1}`, item.response || "未填写。", "", "AI 点评：", item.feedback || "未生成。", "");
      if (item.followUp) {
        lines.push("追问：", item.followUp, "");
      }
      if (item.followUpAnswer || item.followUpFeedback) {
        lines.push("学生回应追问：", item.followUpAnswer || "未填写。", "", "AI 二次回应：", item.followUpFeedback || "未生成。", "");
      }
    });
  } else {
    lines.push("本节课未记录学生观点。", "");
  }

  lines.push("## 教师总结", "", lesson.summaryTemplate || "未填写。", "", "## 作业布置", "", lesson.homeworkTemplate || "未填写。", "");
  return lines.join("\n");
}

export function downloadSessionMarkdown(lesson, studentQuestions, reflections) {
  const content = buildSessionMarkdown(lesson, studentQuestions, reflections);
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const safeTitle = String(lesson.title || "lesson").replace(/[\\/:*?"<>|]/g, "_");
  link.href = url;
  link.download = `${timestamp()}_${safeTitle}.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
