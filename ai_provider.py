from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections import deque
from urllib.parse import urlparse

from app_logging import get_app_logger


logger = get_app_logger(__name__)


class AIProvider(ABC):
    @abstractmethod
    def answer_student_question(self, question: str, lesson_context: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_reflection_prompt(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def respond_to_reflection(self, student_text: str) -> str:
        raise NotImplementedError


class MockLessonAI(AIProvider):
    def __init__(self, reflection_prompt: str) -> None:
        self._reflection_prompt = reflection_prompt

    def answer_student_question(self, question: str, lesson_context: str) -> str:
        normalized = question.replace("？", "?").strip()

        if self._contains_any(normalized, ["衬托", "正衬", "反衬", "写法", "手法", "对比"]) and self._contains_any(
            normalized, ["莲", "菊", "牡丹", "三种花", "文章"]
        ):
            return (
                "如果从写法看，作者写菊和牡丹，都是为了更好地托出莲。菊让我们看到莲不是逃避现实，"
                "牡丹又让我们看到莲不追逐富贵、不迎合世俗。这样一正一反地比较，莲的形象就更鲜明了。"
                "所以，这些写法最后都服务于同一个重点: 突出莲“出淤泥而不染”的高洁品质。"
            )

        if self._contains_any(normalized, ["态度", "看法", "情感", "赞美", "独爱", "众爱", "可爱者甚蕃"]):
            return (
                "作者对三种花的态度层次很清楚。对菊，他带着理解，因为菊象征隐逸者；对牡丹，他并不赞同，"
                "因为牡丹对应的是世人追逐富贵的风气；对莲，则是发自内心的赞美。这样的态度对比，"
                "正好让我们看出作者最欣赏的，是莲在复杂环境中仍能保持洁净，也就是“出淤泥而不染”。"
            )

        if self._contains_any(normalized, ["经历", "生平", "背景", "周敦颐", "作者自己"]):
            return (
                "结合背景可这样理解: 周敦颐关注现实，也重视人格操守，所以他赞美的不是远离社会的消极避世，"
                "而是像莲一样身在环境之中，却还能守住自己的品格。这样看，《爱莲说》就不只是写花，"
                "更是在借莲表达自己的精神追求，而“出淤泥而不染”正是这种追求最鲜明的表达。"
            )

        if self._contains_any(normalized, ["象征", "代表", "分别是什么人", "分别代表", "三种花"]) and self._contains_any(
            normalized, ["菊", "牡丹", "莲", "花"]
        ):
            return (
                "文中的三种花分别象征三类人: 菊象征隐逸者，牡丹象征追逐富贵者，莲象征品德高洁的君子。"
                "作者写这三类人，不是为了平均介绍，而是为了层层比较，最后把重点落在莲身上。"
                "因为在作者眼里，最可贵的不是远离现实，也不是追逐富贵，而是像莲那样“出淤泥而不染”。"
            )

        if self._contains_any(normalized, ["放在一起写", "一起写", "同时写", "为什么写菊", "为什么写牡丹", "为什么要写三种花"]):
            return (
                "作者把菊、牡丹、莲放在一起写，是为了通过对比更鲜明地突出莲的君子品格。"
                "菊代表淡泊避世，牡丹代表世人追逐的富贵，莲则代表既身处现实又保持高洁的君子。"
                "这样写既让人物形象更清楚，也能看出作者不是单纯写花，而是借花表达自己的志向，最后都汇聚到对莲“出淤泥而不染”这一品质的赞美。"
            )

        if self._contains_any(normalized, ["出淤泥而不染", "主旨", "中心", "核心", "品质", "可贵", "君子品格", "高洁"]):
            return (
                "如果抓主旨，最重要的就是“出淤泥而不染”。它不是单纯写莲长得美，而是在赞美一种人格: "
                "身处复杂环境，却不随波逐流，不被世俗污染。前面写菊、写牡丹、写各种品质，"
                "其实都是在为这一点服务。所以读到最后，我们记住的应当不是花本身，而是莲所象征的君子精神。"
            )

        return (
            "这个问题可以继续往文章深处想: 作者写三种花、写不同态度、写多种品质，最后都不是分散的，"
            "而是共同指向莲的君子形象。理解时可以再追问一句: 这些分析为什么都要落到莲身上? "
            "因为作者真正要赞美的，是身处环境却保持高洁的品格，而这正集中体现在“出淤泥而不染”上。"
        )

    def get_reflection_prompt(self) -> str:
        return self._reflection_prompt

    def respond_to_reflection(self, student_text: str) -> str:
        stripped = student_text.strip()
        if not stripped:
            return "先把你们讨论后的想法输入进来，我会结合课文和现实帮你们梳理。"

        if "近墨者黑" in stripped or "环境" in stripped or "影响" in stripped:
            return (
                "这个观点很真实，因为人确实会受到环境影响，所以“近墨者黑”有它的道理。"
                "但《爱莲说》赞美莲，不是说环境不复杂，而是强调人在复杂环境里仍然可以努力守住本心。"
                "也就是说，环境会影响人，可是人也可以通过判断、选择和坚持，让自己尽量接近“出淤泥而不染”的状态。"
            )

        if any(word in stripped for word in ["坚持", "原则", "底线", "拒绝"]):
            return (
                "你们抓住了“坚守原则”这个关键点。莲最可贵的地方，不是在干净环境里显得美，而是在复杂环境中还能守住本色。"
                "放到现实里，这提醒我们面对诱惑、从众或压力时，不能只看别人怎么做，还要想清楚什么是自己应该坚持的。"
            )

        if any(word in stripped for word in ["朋友", "同学", "班级", "集体"]):
            return (
                "把思考放进班级生活里就更有说服力了。课文中的“出淤泥而不染”不是让人离开集体，"
                "而是提醒我们在群体中也要保持判断和正直。能在和同学相处时不盲从、会分辨，这就是对莲花品质很实际的理解。"
            )

        return (
            "这个回答已经开始把课文和生活联系起来了。再往深处想，“出淤泥而不染”强调的不是完全不受环境影响，"
            "而是在受到影响和压力时，仍然努力保持清醒、作出正确选择。这样理解，就真正把莲的品质带进现实生活了。"
        )

    @staticmethod
    def _contains_any(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)


class RemoteLessonAI(AIProvider):
    REQUEST_ERROR_TEXT = "请求错误：AI 后端响应异常，请检查接口配置、网络状态或稍后重试。"

    def __init__(
        self,
        reflection_prompt: str,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 12,
    ) -> None:
        raw_endpoint = endpoint or os.getenv("V2_LESSON_AI_ENDPOINT") or os.getenv("LESSON_AI_ENDPOINT")
        self.api_key = api_key or os.getenv("V2_LESSON_AI_API_KEY") or os.getenv("LESSON_AI_API_KEY")
        self.model = model or os.getenv("V2_LESSON_AI_MODEL") or os.getenv("LESSON_AI_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
        self.timeout_seconds = timeout_seconds
        self.fallback = MockLessonAI(reflection_prompt)
        self.recent_answers: deque[str] = deque(maxlen=4)
        self.recent_feedbacks: deque[str] = deque(maxlen=4)
        self.answer_turn = 0
        self.feedback_turn = 0
        self.endpoint, self.api_mode = self._normalize_endpoint(raw_endpoint)
        self.last_call_used_remote = False
        self.last_error: str | None = None
        self.remote_available = False
        self._check_remote_backend()

    def answer_student_question(self, question: str, lesson_context: str) -> str:
        question_type = self._classify_student_question(question)
        style_hint = self._next_answer_style()
        recent_openers = self._format_recent_openers(self.recent_answers)
        prompt = (
            "你是一名七年级下册语文课堂助手，正在辅助《爱莲说》第二课时。"
            "请回答学生提问，要求语言自然、像课堂即时回应，不要总是重复同一种开头或同一种结尾。\n"
            f"本次问题类型：{question_type}\n"
            f"本次表达风格：{style_hint}\n"
            "回答要求：\n"
            "1. 120到220字，先正面回答学生真正关心的问题，再顺势回到课文。\n"
            "2. 不要空泛复述全文，不要把所有问题都答成同一个模板。\n"
            "3. 如果是象征类问题，先解释三种花分别代表什么人。\n"
            "4. 如果是态度类问题，先比较作者对菊、牡丹、莲的不同态度。\n"
            "5. 如果是写法类问题，先分析对比、衬托怎样突出莲。\n"
            "6. 如果是主旨类问题，先点明“出淤泥而不染”为什么是核心品质。\n"
            "7. 如果涉及作者经历，要明确写成“结合背景可这样理解”。\n"
            "8. 结尾要自然回扣莲的核心品质“出淤泥而不染”，但不要机械重复同一句话。\n"
            f"最近几次回答的开头请尽量避开这些说法：{recent_openers}\n"
            f"课堂背景：{lesson_context}\n"
            f"学生问题：{question}"
        )
        answer = self._ask_remote(prompt, self.fallback.answer_student_question(question, lesson_context))
        self._remember(self.recent_answers, answer)
        return answer

    def get_reflection_prompt(self) -> str:
        return self.fallback.get_reflection_prompt()

    def respond_to_reflection(self, student_text: str) -> str:
        stance = self._classify_reflection(student_text)
        style_hint = self._next_feedback_style()
        recent_openers = self._format_recent_openers(self.recent_feedbacks)
        prompt = (
            "你是一名七年级下册语文课堂助手，正在对学生围绕《爱莲说》的课堂观点作即时回应。"
            "请像老师在课堂上真实接话那样点评，不要模板腔，不要总重复“这个观点很真实”“这个回答已经开始”等固定说法。\n"
            f"学生当前立场：{stance}\n"
            f"本次点评风格：{style_hint}\n"
            "点评要求：\n"
            "1. 80到180字，先接住学生观点，再往深处推进一步。\n"
            "2. 如果学生更认同“近墨者黑”，先承认环境影响真实存在，再谈人仍然可以努力作出选择。\n"
            "3. 如果学生更认同“出淤泥而不染”，先肯定主动坚守的价值，再提醒这种坚守并不轻松。\n"
            "4. 如果学生两边都提到，就回应这种辩证看法，并帮助他把重点落到“怎样在现实中守住本心”。\n"
            "5. 可以适度回扣课文，但不要直接背模板，也不要每次都用同一结构。\n"
            f"最近几次点评的开头请尽量避开这些说法：{recent_openers}\n"
            f"学生观点：{student_text}"
        )
        feedback = self._ask_remote(prompt, self.fallback.respond_to_reflection(student_text))
        self._remember(self.recent_feedbacks, feedback)
        return feedback

    def _ask_remote(self, prompt: str, fallback_text: str) -> str:
        if not self.endpoint or not self.api_key:
            self.last_call_used_remote = False
            self.last_error = "missing_config"
            logger.info("AI backend is not configured; using local fallback.")
            return fallback_text

        if not self.remote_available:
            self.last_call_used_remote = False
            if self.last_error == "manual_local_mode":
                logger.info("Runtime is in manual local mode; using local fallback.")
                return fallback_text
            error = self.last_error or "remote_unavailable"
            logger.warning("AI backend is unavailable; returning request error prompt. error=%s", error)
            return self._request_error_text(error)

        try:
            text = self._request_remote(prompt)
        except urllib.error.HTTPError as exc:
            self.last_call_used_remote = False
            self.last_error = f"http_{exc.code}"
            self.remote_available = False
            logger.warning("AI request failed with HTTP error. status=%s reason=%s", exc.code, exc.reason)
            return self._request_error_text(self.last_error)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            self.last_call_used_remote = False
            self.last_error = "request_failed"
            self.remote_available = False
            logger.warning("AI request failed. error=%s", exc)
            return self._request_error_text(self.last_error)

        if text and text.strip():
            self.last_call_used_remote = True
            self.last_error = None
            logger.info("AI request succeeded.")
            return text.strip()

        self.last_call_used_remote = False
        self.last_error = "empty_response"
        self.remote_available = False
        logger.warning("AI request returned an empty response.")
        return self._request_error_text(self.last_error)

    def _check_remote_backend(self) -> None:
        if not self.endpoint or not self.api_key:
            self.remote_available = False
            self.last_error = "missing_config"
            logger.info("AI backend health check skipped because configuration is missing.")
            return

        try:
            text = self._request_remote("请只回复：已连接")
        except urllib.error.HTTPError as exc:
            self.remote_available = False
            self.last_error = f"http_{exc.code}"
            logger.warning("AI backend health check failed with HTTP error. status=%s reason=%s", exc.code, exc.reason)
            return
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            self.remote_available = False
            self.last_error = "request_failed"
            logger.warning("AI backend health check failed. error=%s", exc)
            return

        if text.strip():
            self.remote_available = True
            self.last_call_used_remote = True
            self.last_error = None
            logger.info("AI backend health check succeeded.")
            return

        self.remote_available = False
        self.last_error = "empty_response"
        logger.warning("AI backend health check returned an empty response.")

    def _request_error_text(self, error: str) -> str:
        if error.startswith("http_"):
            return f"{self.REQUEST_ERROR_TEXT}（错误：{error}）"
        if error == "empty_response":
            return "请求错误：AI 后端返回为空，请检查模型输出或稍后重试。"
        return self.REQUEST_ERROR_TEXT

    def _request_remote(self, prompt: str) -> str:
        payload = self._build_payload(prompt)
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body)
        return self._extract_text(parsed).strip()

    def _build_payload(self, prompt: str) -> dict:
        if self.api_mode == "chat_completions":
            return {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "temperature": 0.8,
                "top_p": 0.9,
            }

        return {
            "model": self.model,
            "input": prompt,
        }

    @staticmethod
    def _extract_text(payload: dict) -> str:
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]

        output = payload.get("output")
        if isinstance(output, list):
            collected: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "output_text":
                        text = block.get("text")
                        if isinstance(text, str):
                            collected.append(text)
            if collected:
                return "\n".join(collected)

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        parts: list[str] = []
                        for item in content:
                            if isinstance(item, dict):
                                text = item.get("text")
                                if isinstance(text, str):
                                    parts.append(text)
                        if parts:
                            return "\n".join(parts)

        return ""

    def _classify_student_question(self, question: str) -> str:
        normalized = question.replace("？", "?").strip()

        if self._contains_any(normalized, ["态度", "看法", "情感", "赞美", "独爱", "众爱"]):
            return "态度类"
        if self._contains_any(normalized, ["衬托", "正衬", "反衬", "写法", "手法", "对比"]):
            return "写法类"
        if self._contains_any(normalized, ["经历", "生平", "背景", "周敦颐", "作者自己"]):
            return "背景类"
        if self._contains_any(normalized, ["出淤泥而不染", "主旨", "中心", "核心", "品质", "高洁", "君子品格"]):
            return "主旨类"
        if self._contains_any(normalized, ["象征", "代表", "分别是什么人", "分别代表", "三种花"]):
            return "象征类"
        return "综合理解类"

    def _classify_reflection(self, student_text: str) -> str:
        stripped = student_text.strip()

        if self._contains_any(stripped, ["都", "两种", "一方面", "另一方面", "既", "也"]):
            return "辩证比较"
        if self._contains_any(stripped, ["近墨者黑", "环境", "影响", "带偏", "很难不受影响"]):
            return "更强调环境影响"
        if self._contains_any(stripped, ["出淤泥而不染", "坚持", "原则", "底线", "守住自己", "不盲从"]):
            return "更强调主动坚守"
        return "结合经历表达看法"

    def _next_answer_style(self) -> str:
        styles = [
            "先给结论，再回到课文细节展开",
            "先抓关键词，再解释作者用意",
            "先比较三种花，再落到莲的品质",
        ]
        style = styles[self.answer_turn % len(styles)]
        self.answer_turn += 1
        return style

    def _next_feedback_style(self) -> str:
        styles = [
            "贴近教师即时回应，语气自然",
            "在肯定之后再推进一层理解",
            "联系现实场景，让学生更容易代入",
        ]
        style = styles[self.feedback_turn % len(styles)]
        self.feedback_turn += 1
        return style

    def _format_recent_openers(self, items: deque[str]) -> str:
        if not items:
            return "暂无"

        openers = [self._extract_opener(text) for text in items if text.strip()]
        openers = [opener for opener in openers if opener]
        if not openers:
            return "暂无"
        return "；".join(openers[-3:])

    @staticmethod
    def _extract_opener(text: str) -> str:
        buffer: list[str] = []
        for char in text.strip():
            if char in "。！？!?":
                break
            buffer.append(char)
            if len(buffer) >= 24:
                break
        return "".join(buffer)

    @staticmethod
    def _contains_any(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _remember(items: deque[str], text: str) -> None:
        cleaned = text.strip()
        if cleaned:
            items.append(cleaned)

    def is_remote_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def is_using_remote(self) -> bool:
        return self.is_remote_configured() and self.remote_available

    def use_local_mode(self) -> None:
        self.remote_available = False
        self.last_call_used_remote = False
        self.last_error = "manual_local_mode"
        logger.info("Runtime switched to local mode manually.")

    def try_remote_mode(self) -> bool:
        self._check_remote_backend()
        return self.is_using_remote()

    def get_runtime_status(self) -> str:
        if not self.is_remote_configured():
            return "课堂模式：本地"
        if self.is_using_remote():
            return "AI后端已连接"
        if self.last_error and self.last_error not in ("missing_config", "manual_local_mode"):
            return "AI后端请求错误"
        return "课堂模式：本地"

    @staticmethod
    def _normalize_endpoint(endpoint: str | None) -> tuple[str | None, str]:
        if not endpoint:
            return None, "responses"

        cleaned = endpoint.strip().rstrip("/")
        parsed = urlparse(cleaned)
        host = (parsed.hostname or "").lower()
        path = parsed.path.rstrip("/")
        lower = cleaned.lower()

        if lower.endswith("/responses"):
            return cleaned, "responses"

        if lower.endswith("/chat/completions"):
            return cleaned, "chat_completions"

        if lower.endswith("/completions"):
            return cleaned, "chat_completions"

        if path in ("", "/", "/v1", "/v1beta", "/v1beta1"):
            if "api.openai.com" in host:
                return f"{cleaned}/responses", "responses"
            return f"{cleaned}/chat/completions", "chat_completions"

        if "api.openai.com" in host:
            return cleaned, "responses"

        return cleaned, "chat_completions"
