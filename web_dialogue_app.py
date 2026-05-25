from __future__ import annotations

import argparse
import json
import socket
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ai_provider import RemoteLessonAI
from session_record import SessionRecord


@dataclass(frozen=True)
class PresetAnswer:
    title: str
    category: str
    question: str
    answer: str
    keywords: tuple[str, ...]


AI_STUDENT_PROMPT = (
    "“出淤泥而不染”是莲最可贵的品质。但在现实生活中，有人认为“近朱者赤，近墨者黑”，"
    "人很难不受环境影响。你更认同哪种观点？请结合自己的经历或见闻谈一谈。"
)


PRESET_ANSWERS: tuple[PresetAnswer, ...] = (
    PresetAnswer(
        title="三种花为什么放在一起写",
        category="预设问题",
        question="作者为什么要把菊、牡丹和莲放在一起写？",
        keywords=("菊", "牡丹", "莲", "一起写", "放在一起", "为什么写三种花", "意图"),
        answer=(
            "作者把菊、牡丹和莲放在一起写，是为了用衬托把莲的君子形象写得更鲜明。菊是“花之隐逸者”，"
            "与莲都有高洁的一面，但菊偏向远离现实，莲则是在现实环境中坚守本心，所以菊对莲形成正衬。"
            "牡丹是“花之富贵者”，象征追名逐利、贪图荣华的富贵者，与莲的淡泊高洁形成反衬。"
            "一正一反地比较，比单独赞美莲更有说服力，也更能突出“出淤泥而不染”的可贵。"
        ),
    ),
    PresetAnswer(
        title="作者对三种花的态度",
        category="预设问题",
        question="作者对这三种花分别是什么态度？",
        keywords=("态度", "看法", "情感", "菊", "牡丹", "莲", "独爱", "众爱"),
        answer=(
            "作者对三种花的态度有明显层次。对菊，他理解并尊重陶渊明的选择，所以说“菊之爱，陶后鲜有闻”，"
            "语气里有惋惜，但并不是反对；只是菊的隐逸不是作者最推崇的人生状态。对牡丹，他借“牡丹之爱，"
            "宜乎众矣”表达讽刺和感慨，批评世人追名逐利的风气。对莲，他用“予独爱莲”直接表明赞赏和自豪，"
            "真正认同的是身处现实而不被污染的君子人格。"
        ),
    ),
    PresetAnswer(
        title="能否结合作者经历分析",
        category="预设问题",
        question="有没有可能结合作者自身的经历来分析？",
        keywords=("经历", "生平", "背景", "周敦颐", "作者自己", "为官", "清廉"),
        answer=(
            "可以结合背景作适度分析，但要注意边界：仅凭课文内容，不能直接推断作者所有经历。课下注释告诉我们，"
            "周敦颐是宋代哲学家，也有为官清廉的评价。这样看，莲就不只是自然界中的花，也像作者人格理想的寄托："
            "身处官场和现实社会这样的“淤泥”之中，仍努力保持清白、正直和独立。这样的分析能帮助我们理解文章的托物言志，"
            "但表达时最好说“结合背景可以这样理解”，不要说成课文本身已经完全写明。"
        ),
    ),
    PresetAnswer(
        title="正衬与反衬怎么区分",
        category="常见追问",
        question="为什么说菊是正衬，牡丹是反衬？",
        keywords=("正衬", "反衬", "衬托", "菊", "牡丹", "区别"),
        answer=(
            "正衬，是用相近的对象来烘托主体；反衬，是用相反的对象来突出主体。菊和莲都有不随俗流的一面，"
            "都显得高洁，所以菊能从相似处衬托莲，这就是正衬。但菊偏向隐居避世，莲却“出淤泥而不染”，"
            "是在现实中保持清白，莲比菊更积极。牡丹象征富贵和世俗追逐，与莲的淡泊、高洁方向相反，"
            "所以它从反面衬出莲的可贵。这样区分，就能把衬托手法和文章主旨连起来。"
        ),
    ),
    PresetAnswer(
        title="莲比菊更独特在哪里",
        category="常见追问",
        question="莲比陶渊明喜欢的菊更独特在哪里？",
        keywords=("比菊", "更独特", "更可贵", "陶渊明", "隐逸", "现实"),
        answer=(
            "菊的可贵在于淡泊名利、远离世俗，它代表隐逸者；莲的可贵则在于不离开现实环境，却能保持清白。"
            "也就是说，菊的高洁有“避开”的意味，莲的高洁更强调“身在其中仍能坚守”。"
            "这正是“出淤泥而不染”的力量：环境并不干净，处境也不轻松，但莲没有随波逐流。"
            "所以作者并不是否定菊，而是借菊进一步突出莲更积极、更难得的君子品质。"
        ),
    ),
    PresetAnswer(
        title="描写莲的句子对应品格",
        category="常见追问",
        question="描写莲的句子分别体现了哪些君子品格？",
        keywords=("句子", "品格", "君子", "出淤泥", "濯清涟", "中通外直", "不蔓不枝", "香远益清", "亭亭净植"),
        answer=(
            "这些句子是在由外形写到人格。“出淤泥而不染”表现洁身自好、不同流合污；“濯清涟而不妖”表现质朴庄重、"
            "不炫耀；“中通外直”表现内心通达、正直无私；“不蔓不枝”表现独立自持、不攀附；"
            "“香远益清”表现美好品德影响深远；“亭亭净植”表现端庄挺立；“可远观而不可亵玩焉”表现尊严、高洁、"
            "不可轻慢。合起来看，作者写莲其实是在写他心目中的君子。"
        ),
    ),
    PresetAnswer(
        title="为什么不直接赞美莲",
        category="常见追问",
        question="作者为什么不直接赞美莲，而要写菊和牡丹？",
        keywords=("直接赞美", "为什么不直接", "写菊", "写牡丹", "说服力", "突出"),
        answer=(
            "如果只直接赞美莲，文章当然也能表达喜爱，但层次会比较单一。加入菊和牡丹后，读者能看到三种人生选择："
            "隐逸避世、追逐富贵、处世而守节。这样一比较，莲的形象就不只是“美”，而是有了人格判断。"
            "菊从相近处衬托，牡丹从相反处映照，最后共同突出莲的主体地位。"
            "所以写菊和牡丹不是跑题，而是让“予独爱莲”的理由更充分。"
        ),
    ),
    PresetAnswer(
        title="托物言志与衬托",
        category="常见追问",
        question="托物言志和衬托在这篇文章里有什么关系？",
        keywords=("托物言志", "衬托", "对比", "写法", "手法", "关系"),
        answer=(
            "托物言志是文章的整体写法：作者表面写莲，实际表达自己对君子人格的追求。衬托是实现这个目的的重要手段："
            "菊和牡丹不是中心，却能帮助莲的形象更清楚。菊让我们看到莲不是简单的清高避世，牡丹让我们看到莲不追逐富贵、"
            "不迎合世俗。把两者放在一起看，就能发现衬托服务于托物言志，最终都是为了表达作者“洁身自好、不与世俗同流合污”的志向。"
        ),
    ),
)


class DialogueEngine:
    def __init__(self) -> None:
        self.ai = RemoteLessonAI(reflection_prompt=AI_STUDENT_PROMPT)
        self.preset_answer_turn = 0

    def bootstrap(self) -> dict[str, Any]:
        return {
            "lessonTitle": "《爱莲说》，说AI莲",
            "subtitle": "课堂对话 AI",
            "runtimeStatus": self.ai.get_runtime_status(),
            "studentQuestionPrompt": "围绕“三种花的区别”或“作者写这三种花的意图”提出一个有价值的问题。",
            "aiStudentPrompt": AI_STUDENT_PROMPT,
        }

    def answer_student_question(self, question: str) -> dict[str, str]:
        cleaned = question.strip()
        if not cleaned:
            return {
                "answer": "请先输入一个课堂问题。",
                "source": "empty",
                "matchedTitle": "",
                "runtimeStatus": self.ai.get_runtime_status(),
            }

        preset = self._match_preset(cleaned)
        if preset is not None:
            answer = self._vary_preset_answer(preset.answer)
            return {
                "answer": answer,
                "source": "preset",
                "matchedTitle": preset.title,
                "runtimeStatus": self.ai.get_runtime_status(),
            }

        lesson_context = (
            "本环节是《爱莲说》“对话AI 深入探究”。学生正在围绕三种花的区别、"
            "作者写三种花的意图、衬托手法和“出淤泥而不染”的现实价值提问。"
        )
        answer = self.ai.answer_student_question(cleaned, lesson_context)
        return {
            "answer": answer,
            "source": "generated",
            "matchedTitle": "",
            "runtimeStatus": self.ai.get_runtime_status(),
        }

    def respond_to_reflection(self, student_text: str) -> dict[str, str]:
        cleaned = student_text.strip()
        feedback = self.ai.respond_to_reflection(cleaned)
        return {
            "prompt": AI_STUDENT_PROMPT,
            "feedback": feedback,
            "followUp": self._build_follow_up(cleaned),
            "runtimeStatus": self.ai.get_runtime_status(),
        }

    def respond_to_follow_up(self, follow_up: str, student_text: str) -> dict[str, str]:
        cleaned = student_text.strip()
        if not cleaned:
            return {
                "response": "可以先让学生用一句话回应这个追问，再补充一个具体理由。",
                "runtimeStatus": self.ai.get_runtime_status(),
            }

        response = self._build_follow_up_response(follow_up, cleaned)
        return {
            "response": response,
            "runtimeStatus": self.ai.get_runtime_status(),
        }

    def save_record(self, payload: dict[str, Any]) -> Path:
        record = SessionRecord(lesson_title="《爱莲说》，说AI莲")
        record.current_stage = "对话 AI"

        for item in payload.get("studentQuestions", []):
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            if question or answer:
                record.add_student_question(question, answer)

        for item in payload.get("reflections", []):
            if not isinstance(item, dict):
                continue
            response = str(item.get("response", "")).strip()
            feedback = str(item.get("feedback", "")).strip()
            follow_up = str(item.get("followUp", "")).strip()
            follow_up_answer = str(item.get("followUpAnswer", "")).strip()
            follow_up_feedback = str(item.get("followUpFeedback", "")).strip()
            if response or feedback:
                combined_feedback = feedback if not follow_up else f"{feedback}\n\n追问：{follow_up}"
                if follow_up_answer:
                    combined_feedback += f"\n\n学生回应追问：{follow_up_answer}"
                if follow_up_feedback:
                    combined_feedback += f"\n\nAI 二次回应：{follow_up_feedback}"
                record.add_reflection(response, combined_feedback)

        output_dir = Path.cwd() / "session_logs"
        return record.save_markdown(output_dir)

    @staticmethod
    def _match_preset(question: str) -> PresetAnswer | None:
        normalized = _normalize_text(question)
        best_item: PresetAnswer | None = None
        best_score = 0

        for item in PRESET_ANSWERS:
            preset_question = _normalize_text(item.question)
            if normalized == preset_question or preset_question in normalized or normalized in preset_question:
                return item

            score = sum(1 for keyword in item.keywords if _normalize_text(keyword) in normalized)
            if score > best_score:
                best_score = score
                best_item = item

        return best_item if best_score >= 2 else None

    def _vary_preset_answer(self, answer: str) -> str:
        sentences = _split_sentences(answer)
        if len(sentences) < 3:
            return answer

        variants = (
            self._as_original_answer,
            self._as_conclusion_first_answer,
            self._as_detail_first_answer,
            self._as_question_bridge_answer,
        )
        variant = variants[self.preset_answer_turn % len(variants)]
        self.preset_answer_turn += 1
        return variant(sentences)

    @staticmethod
    def _as_original_answer(sentences: list[str]) -> str:
        return "".join(sentences)

    @staticmethod
    def _as_conclusion_first_answer(sentences: list[str]) -> str:
        return f"先给结论：{sentences[-1]}再回到课文看，{''.join(sentences[:-1])}"

    @staticmethod
    def _as_detail_first_answer(sentences: list[str]) -> str:
        middle = sentences[1:-1]
        if not middle:
            return "".join(sentences)
        return f"可以先看两个参照对象：{''.join(middle)}由此再看开头的问题，{sentences[0]}{sentences[-1]}"

    @staticmethod
    def _as_question_bridge_answer(sentences: list[str]) -> str:
        if len(sentences) < 4:
            return "".join(sentences)
        return f"这个问题的关键不是“写了几种花”，而是“用谁来突出谁”。{sentences[0]}{sentences[2]}{sentences[1]}{''.join(sentences[3:])}"

    @staticmethod
    def _build_follow_up(student_text: str) -> str:
        if not student_text:
            return "请先用一句话表明你的立场，再补充一个生活中的例子。"

        if _contains_any(student_text, ("两种", "辩证", "既", "也", "一方面", "另一方面", "主动选择")):
            return "如果环境会影响人，而人也能作选择，你认为“选择环境”和“守住内心”哪一步更关键？"
        if _contains_any(student_text, ("近墨者黑", "环境", "影响", "带偏", "很难")):
            return "当环境确实会影响人时，一个人可以靠哪些具体做法减少被“染”的可能？"
        if _contains_any(student_text, ("出淤泥而不染", "坚持", "原则", "底线", "独立", "不盲从", "抄作业")):
            return "把你的例子再推进一步：这种“不染”靠的是一时勇气，还是长期形成的判断力？"
        return "请把你的观点和课文中的一句话连起来，再说明这句话为什么能支持你的看法。"

    @staticmethod
    def _build_follow_up_response(follow_up: str, student_text: str) -> str:
        if _contains_any(student_text, ("长期", "判断力", "习惯", "一直", "平时")):
            return (
                "这个回应把“不染”从一次选择推进到了长期修养。莲的可贵也正在这里：不是偶尔显得干净，"
                "而是在复杂环境中反复作出清醒选择。可以把这个观点再压缩成一句话：君子的高洁，来自长期守住判断和底线。"
            )
        if _contains_any(student_text, ("勇气", "敢", "拒绝", "说不")):
            return (
                "你抓住了现实中的难处：很多时候“不染”确实需要勇气。接下来还可以再想一步，"
                "勇气怎样才能不只停留在一瞬间？如果能把勇气和原则、习惯联系起来，对“出淤泥而不染”的理解会更完整。"
            )
        if _contains_any(student_text, ("选择环境", "朋友", "圈子", "远离", "主动")):
            return (
                "这个回答把人的主动性说出来了。选择环境不是逃避现实，而是在知道环境会影响人的前提下，"
                "尽量让自己接近更好的力量；同时，即使不能完全选择环境，也要保留自己的判断。这样理解就比较辩证。"
            )
        if _contains_any(student_text, ("课文", "出淤泥", "濯清涟", "不染", "莲")):
            return (
                "你已经能把自己的观点拉回课文，这是很关键的一步。继续完善时，可以明确指出：这句话不是说环境没有影响，"
                "而是强调人在环境影响中仍然可以保持清醒和自持。"
            )
        return (
            "这个回应可以作为继续讨论的起点。再往前推进时，请补上一个具体情境，说明人在压力、诱惑或从众心理面前，"
            "到底怎样做才算真正理解“出淤泥而不染”。"
        )


def _normalize_text(text: str) -> str:
    return (
        text.replace("？", "?")
        .replace("“", "")
        .replace("”", "")
        .replace("‘", "")
        .replace("’", "")
        .replace("，", "")
        .replace("。", "")
        .replace("、", "")
        .replace("；", "")
        .replace("：", "")
        .replace(" ", "")
        .lower()
        .strip()
    )


def _split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    buffer: list[str] = []
    for char in text:
        buffer.append(char)
        if char in "。！？!?":
            sentence = "".join(buffer).strip()
            if sentence:
                sentences.append(sentence)
            buffer = []

    tail = "".join(buffer).strip()
    if tail:
        sentences.append(tail)
    return sentences


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


class DialogueRequestHandler(BaseHTTPRequestHandler):
    server_version = "AilianDialogueAI/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML_PAGE)
            return
        if parsed.path == "/api/bootstrap":
            self._send_json(self.server.engine.bootstrap())
            return
        self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json()

        if parsed.path == "/api/ask":
            question = str(payload.get("question", ""))
            self._send_json(self.server.engine.answer_student_question(question))
            return

        if parsed.path == "/api/reflect":
            response = str(payload.get("response", ""))
            self._send_json(self.server.engine.respond_to_reflection(response))
            return

        if parsed.path == "/api/follow-up":
            follow_up = str(payload.get("followUp", ""))
            response = str(payload.get("response", ""))
            self._send_json(self.server.engine.respond_to_follow_up(follow_up, response))
            return

        if parsed.path == "/api/save":
            output_path = self.server.engine.save_record(payload)
            self._send_json({"savedPath": str(output_path), "fileName": output_path.name})
            return

        self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class DialogueHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(server_address, handler_class)
        self.engine = DialogueEngine()


def find_available_port(start_port: int) -> int:
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No available port found.")


def run(host: str, port: int) -> None:
    actual_port = find_available_port(port)
    server = DialogueHTTPServer((host, actual_port), DialogueRequestHandler)
    print(f"课堂对话 AI 已启动：http://{host}:{actual_port}")
    print("按 Ctrl+C 结束服务。")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="《爱莲说》，说AI莲 网页模块")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run(args.host, args.port)


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>《爱莲说》对话 AI</title>
  <style>
    :root {
      --bg: #eef5f0;
      --surface: #ffffff;
      --surface-2: #f7faf8;
      --ink: #172524;
      --muted: #61716d;
      --line: #ccd9d2;
      --green: #0e5d50;
      --green-2: #dcebe5;
      --coral: #c95f42;
      --gold: #a76f21;
      --blue: #325e8f;
      --shadow: 0 18px 45px rgba(20, 44, 38, 0.12);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(90deg, rgba(14, 93, 80, 0.08) 1px, transparent 1px),
        linear-gradient(180deg, rgba(14, 93, 80, 0.06) 1px, transparent 1px),
        var(--bg);
      background-size: 42px 42px;
      color: var(--ink);
      font-family: "Noto Serif SC", "Microsoft YaHei UI", "Songti SC", serif;
      letter-spacing: 0;
    }

    button,
    textarea,
    input {
      font: inherit;
    }

    button {
      cursor: pointer;
    }

    .app-shell {
      width: min(1480px, calc(100vw - 44px));
      margin: 0 auto;
      padding: 22px 0 26px;
    }

    .topbar {
      display: grid;
      grid-template-columns: minmax(280px, 1fr) auto auto;
      gap: 18px;
      align-items: center;
      padding: 18px 0 22px;
      border-bottom: 2px solid rgba(14, 93, 80, 0.2);
    }

    .title-block h1 {
      margin: 0;
      font-size: 34px;
      line-height: 1.15;
      color: var(--green);
      font-weight: 800;
    }

    .title-block p {
      margin: 7px 0 0;
      color: var(--muted);
      font-size: 16px;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      min-height: 38px;
      padding: 0 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
      color: var(--green);
      font-size: 14px;
      font-weight: 700;
      white-space: nowrap;
    }

    .tabs {
      display: inline-grid;
      grid-template-columns: 1fr 1fr;
      border: 1px solid var(--green);
      background: var(--surface);
      overflow: hidden;
    }

    .tab {
      min-width: 128px;
      border: 0;
      border-right: 1px solid var(--green);
      background: transparent;
      color: var(--green);
      padding: 11px 16px;
      font-weight: 800;
    }

    .tab:last-child {
      border-right: 0;
    }

    .tab.active {
      background: var(--green);
      color: #fff;
    }

    .view {
      display: none;
      padding-top: 22px;
    }

    .view.active {
      display: block;
    }

    .ask-grid {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      gap: 18px;
      min-height: calc(100vh - 156px);
    }

    .reflect-grid {
      display: grid;
      grid-template-columns: minmax(360px, 0.92fr) minmax(0, 1.08fr);
      gap: 18px;
      min-height: calc(100vh - 156px);
    }

    .panel {
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      min-width: 0;
    }

    .panel-header {
      padding: 17px 18px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--surface-2);
    }

    .panel-header h2 {
      margin: 0;
      color: var(--ink);
      font-size: 20px;
      line-height: 1.25;
    }

    .panel-header p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
    }

    .flower-gallery {
      display: grid;
      gap: 14px;
      padding: 14px;
    }

    .flower-card {
      position: relative;
      min-height: 148px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .flower-card svg {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }

    .flower-caption {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: end;
      padding: 12px;
      background: linear-gradient(180deg, transparent, rgba(18, 32, 30, 0.82));
      color: #fff;
    }

    .flower-caption strong {
      font-size: 24px;
      line-height: 1;
    }

    .flower-caption span {
      max-width: 180px;
      font-size: 13px;
      line-height: 1.35;
      text-align: right;
    }

    .question-cues {
      display: grid;
      gap: 10px;
      padding: 0 14px 16px;
    }

    .cue {
      border-left: 4px solid var(--green);
      padding: 8px 10px;
      background: var(--surface-2);
      color: var(--muted);
      line-height: 1.55;
      font-size: 14px;
    }

    .chat-panel {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      min-height: 100%;
    }

    .chat-stream {
      overflow: auto;
      padding: 18px;
      background: linear-gradient(180deg, #fff 0%, #f7faf8 100%);
    }

    .empty-state {
      min-height: 100%;
      display: grid;
      align-content: center;
      gap: 18px;
      color: var(--muted);
    }

    .empty-state .large-mark {
      font-size: 88px;
      line-height: 1;
      color: rgba(14, 93, 80, 0.16);
      font-weight: 900;
    }

    .empty-state strong {
      color: var(--green);
      font-size: 28px;
      line-height: 1.2;
    }

    .message {
      max-width: 980px;
      margin-bottom: 18px;
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 8px;
      overflow: hidden;
    }

    .message.question {
      margin-left: auto;
      border-color: rgba(50, 94, 143, 0.38);
    }

    .message.answer {
      border-color: rgba(14, 93, 80, 0.36);
    }

    .message-label {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 9px 13px;
      background: var(--surface-2);
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }

    .message-body {
      padding: 14px 15px 16px;
      font-size: 18px;
      line-height: 1.78;
      white-space: pre-wrap;
    }

    .message.question .message-body {
      color: var(--blue);
      font-weight: 700;
    }

    .source-tag {
      color: var(--coral);
      white-space: nowrap;
    }

    .composer {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 10px;
      align-items: center;
      padding: 14px;
      border-top: 1px solid var(--line);
      background: var(--surface);
    }

    .question-input {
      min-height: 48px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0 14px;
      outline: none;
      background: #fff;
    }

    .question-input:focus,
    textarea:focus {
      border-color: var(--green);
      box-shadow: 0 0 0 3px rgba(14, 93, 80, 0.12);
    }

    .action-button,
    .ghost-button {
      min-height: 48px;
      border-radius: 8px;
      padding: 0 18px;
      font-weight: 800;
      white-space: nowrap;
    }

    .action-button {
      border: 1px solid var(--green);
      background: var(--green);
      color: #fff;
    }

    .action-button:hover {
      background: #0a493f;
    }

    .ghost-button {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--green);
    }

    .ghost-button:hover {
      border-color: var(--green);
      background: var(--green-2);
    }

    .prompt-block {
      padding: 22px;
    }

    .prompt-quote {
      border-left: 6px solid var(--coral);
      padding: 4px 0 4px 18px;
      color: var(--ink);
      font-size: 24px;
      line-height: 1.65;
      font-weight: 800;
    }

    .thinking-steps {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      margin-top: 20px;
    }

    .step {
      border: 1px solid var(--line);
      background: var(--surface-2);
      padding: 12px;
      border-radius: 8px;
    }

    .step strong {
      display: block;
      color: var(--green);
      font-size: 18px;
    }

    .step span {
      color: var(--muted);
      font-size: 13px;
    }

    .reflection-editor {
      display: grid;
      gap: 12px;
      padding: 18px;
      border-top: 1px solid var(--line);
    }

    textarea {
      width: 100%;
      min-height: 160px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      line-height: 1.7;
      outline: none;
      color: var(--ink);
      background: #fff;
    }

    .reflection-hints {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }

    .hint-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-2);
      color: var(--muted);
      padding: 10px;
      line-height: 1.45;
      font-size: 13px;
    }

    .hint-card strong {
      display: block;
      margin-bottom: 3px;
      color: var(--green);
      font-size: 14px;
    }

    .feedback-panel {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      min-height: 100%;
    }

    .feedback-body {
      padding: 18px;
      overflow: auto;
      background: #fff;
    }

    .feedback-output {
      display: grid;
      gap: 16px;
    }

    .feedback-box,
    .follow-box,
    .follow-response-box {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      line-height: 1.8;
      font-size: 18px;
      white-space: pre-wrap;
    }

    .feedback-box {
      border-color: rgba(14, 93, 80, 0.32);
      background: var(--surface-2);
    }

    .follow-box {
      border-color: rgba(201, 95, 66, 0.35);
      background: rgba(201, 95, 66, 0.07);
    }

    .follow-response-box {
      border-color: rgba(50, 94, 143, 0.32);
      background: rgba(50, 94, 143, 0.07);
    }

    .follow-up-composer {
      display: grid;
      gap: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fff;
    }

    .follow-up-composer textarea {
      min-height: 112px;
    }

    .button-row {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }

    .toast {
      position: fixed;
      right: 22px;
      bottom: 22px;
      max-width: min(460px, calc(100vw - 44px));
      padding: 13px 15px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--green);
      box-shadow: var(--shadow);
      border-radius: 8px;
      font-weight: 800;
      opacity: 0;
      pointer-events: none;
      transform: translateY(10px);
      transition: opacity 160ms ease, transform 160ms ease;
    }

    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }

    @media (max-width: 980px) {
      .app-shell {
        width: min(100vw - 24px, 760px);
        padding-top: 12px;
      }

      .topbar {
        grid-template-columns: 1fr;
        gap: 12px;
      }

      .tabs {
        width: 100%;
      }

      .tab {
        min-width: 0;
      }

      .ask-grid,
      .reflect-grid {
        grid-template-columns: 1fr;
        min-height: 0;
      }

      .flower-gallery {
        grid-template-columns: 1fr;
      }

      .composer {
        grid-template-columns: 1fr;
      }

      .thinking-steps {
        grid-template-columns: 1fr;
      }

      .reflection-hints {
        grid-template-columns: 1fr;
      }

      .prompt-quote {
        font-size: 20px;
      }
    }
  </style>
</head>
<body>
  <main class="app-shell">
    <header class="topbar">
      <div class="title-block">
        <h1 id="lessonTitle">《爱莲说》，说AI莲</h1>
        <p id="subtitle">对话 AI 课堂互动</p>
      </div>
      <div class="status-pill" id="runtimeStatus">加载中</div>
      <nav class="tabs" aria-label="互动环节">
        <button class="tab active" data-tab="ask">学生问 AI</button>
        <button class="tab" data-tab="reflect">AI 问学生</button>
      </nav>
    </header>

    <section id="askView" class="view active">
      <div class="ask-grid">
        <aside class="panel">
          <div class="panel-header">
            <h2>看花，也看人</h2>
            <p id="questionPrompt">围绕三种花的区别、作者的写作意图和你自己的疑问来提问。</p>
          </div>
          <div class="flower-gallery" aria-label="菊、莲、牡丹">
            <figure class="flower-card">
              <svg viewBox="0 0 420 180" role="img" aria-label="菊花">
                <defs>
                  <radialGradient id="chrysanthemumBg" cx="34%" cy="32%" r="80%">
                    <stop offset="0" stop-color="#fff8d6"/>
                    <stop offset="1" stop-color="#d9ece3"/>
                  </radialGradient>
                </defs>
                <rect width="420" height="180" fill="url(#chrysanthemumBg)"/>
                <g transform="translate(130 78)">
                  <g fill="none" stroke="#d39a1f" stroke-width="9" stroke-linecap="round">
                    <path d="M0 0 C-46 -34 -72 -54 -94 -68"/>
                    <path d="M0 0 C-34 -44 -50 -73 -60 -98"/>
                    <path d="M0 0 C-12 -55 -14 -88 -12 -116"/>
                    <path d="M0 0 C14 -55 28 -84 44 -106"/>
                    <path d="M0 0 C42 -40 70 -58 98 -72"/>
                    <path d="M0 0 C52 -14 82 -19 112 -17"/>
                    <path d="M0 0 C-52 -2 -86 4 -116 14"/>
                    <path d="M0 0 C-41 30 -67 52 -88 78"/>
                    <path d="M0 0 C-6 48 -7 78 -2 108"/>
                    <path d="M0 0 C28 38 54 58 84 75"/>
                    <path d="M0 0 C50 16 82 22 112 20"/>
                  </g>
                  <circle r="24" fill="#8d5d15"/>
                  <circle r="13" fill="#f0c24e"/>
                </g>
                <path d="M160 112 C170 136 182 154 206 173" fill="none" stroke="#4c8a62" stroke-width="8" stroke-linecap="round"/>
                <path d="M205 150 C235 128 270 126 306 143" fill="none" stroke="#4c8a62" stroke-width="7" stroke-linecap="round"/>
              </svg>
              <figcaption class="flower-caption"><strong>菊</strong><span>隐逸、淡泊，也引出比较</span></figcaption>
            </figure>
            <figure class="flower-card">
              <svg viewBox="0 0 420 180" role="img" aria-label="莲花">
                <defs>
                  <linearGradient id="lotusBg" x1="0" x2="1" y1="0" y2="1">
                    <stop offset="0" stop-color="#e6f5f7"/>
                    <stop offset="1" stop-color="#d8eee4"/>
                  </linearGradient>
                </defs>
                <rect width="420" height="180" fill="url(#lotusBg)"/>
                <path d="M40 136 C98 112 142 154 202 132 C265 110 305 132 380 116" fill="none" stroke="#5aa7a0" stroke-width="9" stroke-linecap="round"/>
                <path d="M58 156 C118 142 158 166 220 148 C280 131 326 152 386 139" fill="none" stroke="#85b9a7" stroke-width="6" stroke-linecap="round"/>
                <g transform="translate(214 92)">
                  <path d="M0 27 C-28 -2 -22 -48 0 -75 C23 -47 29 -1 0 27Z" fill="#f7d9df" stroke="#d98b9a" stroke-width="3"/>
                  <path d="M-10 30 C-55 10 -64 -34 -44 -70 C-8 -48 8 -6 -10 30Z" fill="#f3b8c6" stroke="#d98b9a" stroke-width="3"/>
                  <path d="M10 30 C55 10 64 -34 44 -70 C8 -48 -8 -6 10 30Z" fill="#f3b8c6" stroke="#d98b9a" stroke-width="3"/>
                  <path d="M-8 28 C-38 30 -65 12 -76 -18 C-42 -27 -12 -9 -8 28Z" fill="#f0a3b8" stroke="#d98b9a" stroke-width="3"/>
                  <path d="M8 28 C38 30 65 12 76 -18 C42 -27 12 -9 8 28Z" fill="#f0a3b8" stroke="#d98b9a" stroke-width="3"/>
                  <ellipse cx="0" cy="27" rx="24" ry="10" fill="#e9b84e"/>
                </g>
                <path d="M214 119 C210 140 206 158 202 178" fill="none" stroke="#3f8569" stroke-width="8" stroke-linecap="round"/>
              </svg>
              <figcaption class="flower-caption"><strong>莲</strong><span>身处现实，仍保持高洁</span></figcaption>
            </figure>
            <figure class="flower-card">
              <svg viewBox="0 0 420 180" role="img" aria-label="牡丹">
                <defs>
                  <radialGradient id="peonyBg" cx="68%" cy="38%" r="78%">
                    <stop offset="0" stop-color="#ffe4dc"/>
                    <stop offset="1" stop-color="#edf1e1"/>
                  </radialGradient>
                </defs>
                <rect width="420" height="180" fill="url(#peonyBg)"/>
                <g transform="translate(220 82)">
                  <path d="M0 24 C-38 22 -80 5 -88 -36 C-50 -54 -15 -42 0 24Z" fill="#d85c55" stroke="#a93835" stroke-width="3"/>
                  <path d="M0 24 C38 22 80 5 88 -36 C50 -54 15 -42 0 24Z" fill="#d85c55" stroke="#a93835" stroke-width="3"/>
                  <path d="M0 24 C-22 -18 -12 -61 22 -88 C50 -52 42 -8 0 24Z" fill="#ee7a70" stroke="#a93835" stroke-width="3"/>
                  <path d="M0 24 C-2 -18 -38 -46 -78 -48 C-86 -8 -45 22 0 24Z" fill="#c94755" stroke="#a93835" stroke-width="3"/>
                  <path d="M0 24 C2 -18 38 -46 78 -48 C86 -8 45 22 0 24Z" fill="#c94755" stroke="#a93835" stroke-width="3"/>
                  <path d="M0 28 C-24 38 -55 34 -78 8 C-48 -12 -12 -8 0 28Z" fill="#b9384d" stroke="#a93835" stroke-width="3"/>
                  <path d="M0 28 C24 38 55 34 78 8 C48 -12 12 -8 0 28Z" fill="#b9384d" stroke="#a93835" stroke-width="3"/>
                  <circle r="20" fill="#f0bd3f"/>
                  <circle r="9" fill="#7f4b14"/>
                </g>
                <path d="M220 112 C224 135 232 157 248 178" fill="none" stroke="#4f8750" stroke-width="8" stroke-linecap="round"/>
                <path d="M246 148 C280 124 320 123 350 145" fill="none" stroke="#4f8750" stroke-width="7" stroke-linecap="round"/>
              </svg>
              <figcaption class="flower-caption"><strong>牡丹</strong><span>富贵、热闹，也形成映照</span></figcaption>
            </figure>
          </div>
          <div class="question-cues">
            <div class="cue">可以从“为什么这样安排内容”发问。</div>
            <div class="cue">可以从“作者真正赞赏什么人格”发问。</div>
            <div class="cue">可以从“这些花和现实生活有什么关系”发问。</div>
          </div>
        </aside>

        <section class="panel chat-panel">
          <div class="panel-header">
            <h2>对话记录</h2>
            <p>学生自由提问，AI 围绕课文内容、写作手法和现实思考作答。</p>
          </div>
          <div class="chat-stream" id="chatStream">
            <div class="empty-state">
              <div class="large-mark">莲</div>
              <strong>等待学生提出第一个问题</strong>
            </div>
          </div>
          <div class="composer">
            <input id="questionInput" class="question-input" placeholder="输入学生问题，例如：作者为什么要写菊和牡丹？" />
            <button id="askButton" class="action-button">提交问题</button>
            <button id="saveButton" class="ghost-button">保存记录</button>
          </div>
        </section>
      </div>
    </section>

    <section id="reflectView" class="view">
      <div class="reflect-grid">
        <section class="panel">
          <div class="panel-header">
            <h2>AI 提问</h2>
            <p>学习活动四</p>
          </div>
          <div class="prompt-block">
            <div class="prompt-quote" id="aiStudentPrompt"></div>
            <div class="thinking-steps">
              <div class="step"><strong>2 分钟</strong><span>独立写关键词</span></div>
              <div class="step"><strong>2 分钟</strong><span>小组交流观点</span></div>
              <div class="step"><strong>3 分钟</strong><span>全班代表分享</span></div>
            </div>
          </div>
          <div class="reflection-editor">
            <textarea id="reflectionInput" placeholder="输入学生代表观点或小组讨论后的观点"></textarea>
            <div class="reflection-hints" aria-label="思考提示">
              <div class="hint-card"><strong>先表明立场</strong>你更认同哪一种观点，或者是否想辩证看待？</div>
              <div class="hint-card"><strong>再联系经历</strong>可以联系同学相处、学习习惯、网络环境或身边见闻。</div>
              <div class="hint-card"><strong>最后回到课文</strong>想一想你的观点怎样理解“出淤泥而不染”。</div>
            </div>
            <div class="button-row">
              <button id="reflectButton" class="action-button">生成点评</button>
            </div>
          </div>
        </section>

        <section class="panel feedback-panel">
          <div class="panel-header">
            <h2>AI 点评与追问</h2>
            <p>保留不同立场，把讨论推进到现实中的选择与坚守。</p>
          </div>
          <div class="feedback-body">
            <div id="feedbackOutput" class="feedback-output">
              <div class="empty-state">
                <div class="large-mark">问</div>
                <strong>等待学生观点</strong>
              </div>
            </div>
          </div>
        </section>
      </div>
    </section>
  </main>
  <div id="toast" class="toast"></div>

  <script>
    const state = {
      studentQuestions: [],
      reflections: [],
      bootstrap: null,
    };

    const $ = (selector) => document.querySelector(selector);

    async function api(path, payload) {
      const options = payload === undefined ? {} : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      };
      const response = await fetch(path, options);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    }

    function setStatus(text) {
      $("#runtimeStatus").textContent = text || "当前使用演示模式";
    }

    function toast(text) {
      const node = $("#toast");
      node.textContent = text;
      node.classList.add("show");
      window.clearTimeout(toast.timer);
      toast.timer = window.setTimeout(() => node.classList.remove("show"), 2600);
    }

    function renderChat() {
      const stream = $("#chatStream");
      if (!state.studentQuestions.length) {
        stream.innerHTML = `<div class="empty-state"><div class="large-mark">莲</div><strong>等待学生提出第一个问题</strong></div>`;
        return;
      }

      stream.innerHTML = "";
      state.studentQuestions.forEach((item, index) => {
        const q = document.createElement("article");
        q.className = "message question";
        q.innerHTML = `
          <div class="message-label"><span>学生问题 ${index + 1}</span></div>
          <div class="message-body"></div>
        `;
        q.querySelector(".message-body").textContent = item.question;
        stream.appendChild(q);

        const a = document.createElement("article");
        a.className = "message answer";
        const sourceText = item.source === "preset" ? "AI 回答" : "生成回答";
        a.innerHTML = `
          <div class="message-label"><span>AI 回答</span><span class="source-tag">${sourceText}</span></div>
          <div class="message-body"></div>
        `;
        a.querySelector(".message-body").textContent = item.answer;
        stream.appendChild(a);
      });
      stream.scrollTop = stream.scrollHeight;
    }

    async function askQuestion(question) {
      const input = $("#questionInput");
      const cleaned = (question || input.value).trim();
      if (!cleaned) {
        toast("请先输入一个问题");
        return;
      }

      $("#askButton").disabled = true;
      try {
        const result = await api("/api/ask", { question: cleaned });
        state.studentQuestions.push({
          question: cleaned,
          answer: result.answer,
          source: result.source,
          matchedTitle: result.matchedTitle || "",
        });
        input.value = "";
        setStatus(result.runtimeStatus);
        renderChat();
      } catch (error) {
        toast("生成回答失败，请检查服务是否仍在运行");
      } finally {
        $("#askButton").disabled = false;
        input.focus();
      }
    }

    function renderReflection(result, studentResponse) {
      const output = $("#feedbackOutput");
      output.innerHTML = "";
      const reflectionIndex = state.reflections.length;

      const feedback = document.createElement("div");
      feedback.className = "feedback-box";
      feedback.textContent = result.feedback;
      output.appendChild(feedback);

      const follow = document.createElement("div");
      follow.className = "follow-box";
      follow.textContent = `追问：${result.followUp}`;
      output.appendChild(follow);

      state.reflections.push({
        response: studentResponse,
        feedback: result.feedback,
        followUp: result.followUp,
        followUpAnswer: "",
        followUpFeedback: "",
      });

      const composer = document.createElement("div");
      composer.className = "follow-up-composer";
      composer.innerHTML = `
        <textarea id="followUpInput" placeholder="学生继续回答 AI 的追问"></textarea>
        <div class="button-row">
          <button id="followUpButton" class="action-button">回应追问</button>
        </div>
      `;
      output.appendChild(composer);
      $("#followUpButton").addEventListener("click", () => respondToFollowUp(reflectionIndex));
      $("#followUpInput").focus();
    }

    async function respondToReflection() {
      const input = $("#reflectionInput");
      const studentResponse = input.value.trim();
      $("#reflectButton").disabled = true;
      try {
        const result = await api("/api/reflect", { response: studentResponse });
        setStatus(result.runtimeStatus);
        renderReflection(result, studentResponse);
      } catch (error) {
        toast("生成点评失败，请检查服务是否仍在运行");
      } finally {
        $("#reflectButton").disabled = false;
      }
    }

    async function respondToFollowUp(reflectionIndex) {
      const input = $("#followUpInput");
      if (!input) {
        return;
      }
      const studentResponse = input.value.trim();
      if (!studentResponse) {
        toast("请先输入学生对追问的回应");
        return;
      }

      const item = state.reflections[reflectionIndex];
      if (!item) {
        toast("未找到这一轮追问记录");
        return;
      }

      $("#followUpButton").disabled = true;
      try {
        const result = await api("/api/follow-up", {
          followUp: item.followUp,
          response: studentResponse,
        });
        item.followUpAnswer = studentResponse;
        item.followUpFeedback = result.response;
        setStatus(result.runtimeStatus);

        const answerBox = document.createElement("div");
        answerBox.className = "follow-response-box";
        answerBox.textContent = `学生回应：${studentResponse}\n\nAI 二次回应：${result.response}`;
        $("#feedbackOutput").appendChild(answerBox);

        input.disabled = true;
        $("#followUpButton").disabled = true;
      } catch (error) {
        toast("回应追问失败，请检查服务是否仍在运行");
        $("#followUpButton").disabled = false;
      }
    }

    async function saveRecord() {
      if (!state.studentQuestions.length && !state.reflections.length) {
        toast("当前还没有可保存的课堂记录");
        return;
      }
      try {
        const result = await api("/api/save", {
          studentQuestions: state.studentQuestions,
          reflections: state.reflections,
        });
        toast(`课堂记录已保存：${result.fileName}`);
      } catch (error) {
        toast("保存失败，请检查 session_logs 目录权限");
      }
    }

    function bindTabs() {
      document.querySelectorAll("[data-tab]").forEach((button) => {
        button.addEventListener("click", () => {
          document.querySelectorAll("[data-tab]").forEach((item) => item.classList.remove("active"));
          document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
          button.classList.add("active");
          const viewId = button.dataset.tab === "ask" ? "#askView" : "#reflectView";
          $(viewId).classList.add("active");
        });
      });
    }

    async function boot() {
      bindTabs();
      $("#askButton").addEventListener("click", () => askQuestion());
      $("#questionInput").addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          askQuestion();
        }
      });
      $("#reflectButton").addEventListener("click", respondToReflection);
      $("#saveButton").addEventListener("click", saveRecord);

      const data = await api("/api/bootstrap");
      state.bootstrap = data;
      $("#lessonTitle").textContent = data.lessonTitle;
      $("#subtitle").textContent = data.subtitle;
      $("#questionPrompt").textContent = data.studentQuestionPrompt;
      $("#aiStudentPrompt").textContent = data.aiStudentPrompt;
      setStatus(data.runtimeStatus);
      $("#questionInput").focus();
    }

    boot().catch(() => toast("页面初始化失败，请刷新重试"));
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
