from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app_logging import get_app_logger
from scripts import generate_lessons


logger = get_app_logger(__name__)
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "dist"
LESSON_DIR = ROOT / "lesson_plan"
GENERATED_DIR = ROOT / "public" / "generated-lessons"


def load_dotenv() -> None:
    loaded_paths = []
    for env_path in dotenv_candidates():
        if env_path.exists():
            load_env_file(env_path)
            loaded_paths.append(str(env_path))
    logger.info(
        "Prep env loaded. paths=%s token=%s repo=%s sshKey=%s aiEndpoint=%s",
        loaded_paths,
        secret_fingerprint(os.environ.get("PREP_MODE_TOKEN", "")),
        bool(os.environ.get("PREP_GIT_REPO", "").strip()),
        secret_fingerprint(os.environ.get("PREP_GIT_SSH_PRIVATE_KEY", "")),
        bool(os.environ.get("PREP_AI_ENDPOINT", "").strip()),
    )


def dotenv_candidates() -> list[Path]:
    candidates = [ROOT / ".env", Path.cwd() / ".env"]
    deploy_command = os.environ.get("DEPLOY_UPDATE_COMMAND", "")
    for token in re.findall(r"(?:-f|--project-directory)\s+([^\s]+)", deploy_command):
        path = Path(token)
        if path.name in {"docker-compose.yml", "compose.yml"}:
            candidates.append(path.parent / ".env")
        else:
            candidates.append(path / ".env")

    unique = []
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def load_env_file(env_path: Path) -> None:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class DialogueEngine:
    def validate_prep_token(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_prep_token(payload)
        return {"ok": True}

    def list_prep_templates(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_prep_token(payload)
        lessons = []
        index_path = GENERATED_DIR / "index.json"
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                index = {}
            for item in index.get("lessons", []) if isinstance(index, dict) else []:
                lesson_id = str(item.get("id", "")).strip()
                lesson_path = GENERATED_DIR / f"{lesson_id}.json"
                if not lesson_id or not lesson_path.exists():
                    continue
                try:
                    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                markdown = self._read_lesson_markdown(lesson)
                lessons.append({"id": lesson_id, "lesson": lesson, "markdown": markdown})
        return {"lessons": lessons}

    def parse_prep_markdown(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_prep_token(payload)
        markdown = str(payload.get("markdown", "")).strip()
        if not markdown:
            raise ValueError("markdown_required")
        lesson_id = self._lesson_id_from_payload(payload, markdown)
        lesson = self._build_lesson_from_markdown(lesson_id, markdown, generated_by="parsed")
        return {"markdown": markdown, "lesson": lesson}

    def generate_prep_lesson(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_prep_token(payload)
        title = str(payload.get("title", "")).strip() or "新课文"
        source_text = str(payload.get("sourceText", "")).strip()
        brief = str(payload.get("brief", "")).strip()
        if not source_text and not brief:
            raise ValueError("source_or_brief_required")

        fallback_markdown = self._build_draft_markdown(title, source_text, brief)
        fallback_lesson_id = generate_lessons.slugify(title)
        fallback_lesson = self._build_lesson_from_markdown(fallback_lesson_id, fallback_markdown, generated_by="fallback")
        ai_result = self._generate_lesson_with_ai(title, source_text, brief, fallback_markdown, fallback_lesson)
        if not ai_result:
            return {"markdown": fallback_markdown, "lesson": fallback_lesson, "generatedBy": "fallback"}

        markdown = str(ai_result.get("markdown", "")).strip() or fallback_markdown
        raw_lesson = ai_result.get("lesson") if isinstance(ai_result.get("lesson"), dict) else {}
        lesson_id = self._lesson_id_from_payload({"title": raw_lesson.get("title") or title}, markdown)
        fallback = self._build_lesson_from_markdown(lesson_id, markdown, generated_by="fallback")
        lesson = self._normalize_lesson_json({**fallback, **raw_lesson}, lesson_id, markdown, "ai")
        return {"markdown": markdown, "lesson": lesson, "generatedBy": "ai"}

    def save_prep_lesson(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_prep_token(payload)
        markdown = str(payload.get("markdown", "")).strip()
        lesson = _dict(payload.get("lesson"))
        if not markdown:
            raise ValueError("markdown_required")
        lesson_id = str(lesson.get("id") or self._lesson_id_from_payload(payload, markdown)).strip()
        lesson = self._normalize_lesson_json(lesson, lesson_id, markdown, "prep")
        markdown_path = f"lesson_plan/{lesson_id}.md"
        lesson_path = f"public/generated-lessons/{lesson_id}.json"
        commit_message = str(payload.get("commitMessage") or f"备课模式生成《{lesson.get('title', lesson_id)}》导学案模板").strip()
        commit = self._push_lesson_to_draft_branch(markdown_path, markdown, lesson_path, lesson, commit_message)
        return {"ok": True, "branch": self._prep_branch(), "commit": commit, "lesson": lesson, "markdown": markdown}

    def list_prep_drafts(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_prep_token(payload)
        with self._git_repo() as (workdir, env):
            branch = self._prep_branch()
            self._run_git(["git", "fetch", "origin", branch], workdir, env)
            lessons = self._read_lessons_from_git_ref(workdir, env, f"origin/{branch}")
        return {"branch": self._prep_branch(), "lessons": lessons}

    def merge_prep_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_prep_token(payload)
        lesson_id = generate_lessons.slugify(str(payload.get("lessonId") or payload.get("id") or "").strip())
        if not lesson_id:
            raise ValueError("lesson_id_required")

        draft_branch = self._prep_branch()
        target_branch = self._target_branch()
        with self._git_repo() as (workdir, env):
            self._run_git(["git", "fetch", "origin", draft_branch], workdir, env)
            self._run_git(["git", "fetch", "origin", target_branch], workdir, env, check=False)
            checkout = subprocess.run(
                ["git", "checkout", "-B", target_branch, f"origin/{target_branch}"],
                cwd=workdir,
                env=env,
                text=True,
                capture_output=True,
            )
            if checkout.returncode != 0:
                self._run_git(["git", "checkout", "-b", target_branch], workdir, env)

            draft = self._read_lesson_from_git_ref(workdir, env, f"origin/{draft_branch}", lesson_id)
            lesson = _dict(draft.get("lesson"))
            markdown = str(draft.get("markdown") or "").strip()
            if not lesson or not markdown:
                raise ValueError("draft_lesson_not_found")

            markdown_path = str(lesson.get("lessonPlanSource") or f"lesson_plan/{lesson_id}.md")
            lesson_path = f"public/generated-lessons/{lesson_id}.json"
            (workdir / markdown_path).parent.mkdir(parents=True, exist_ok=True)
            (workdir / markdown_path).write_text(markdown.rstrip() + "\n", encoding="utf-8")
            (workdir / lesson_path).parent.mkdir(parents=True, exist_ok=True)
            (workdir / lesson_path).write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._write_lesson_index(workdir, lesson)
            self._run_git(["git", "add", markdown_path, lesson_path, "public/generated-lessons/index.json"], workdir, env)
            diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=workdir, env=env)
            if diff.returncode == 0:
                commit = self._run_git(["git", "rev-parse", "HEAD"], workdir, env).strip()
            else:
                commit_message = str(payload.get("commitMessage") or f"合并草稿导学案《{lesson.get('title', lesson_id)}》到 v2").strip()
                self._run_git(["git", "commit", "-m", commit_message], workdir, env)
                self._run_git(["git", "push", "origin", target_branch], workdir, env)
                commit = self._run_git(["git", "rev-parse", "HEAD"], workdir, env).strip()
        return {"ok": True, "branch": target_branch, "commit": commit, "lesson": lesson, "markdown": markdown}

    def update_container(self) -> dict[str, Any]:
        command = os.environ.get(
            "DEPLOY_UPDATE_COMMAND",
            "docker compose pull hhs-class-1-v2 && docker compose up -d hhs-class-1-v2",
        )
        completed = subprocess.run(
            command,
            shell=True,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=600,
        )
        output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
        logger.info("Deploy update command finished. returnCode=%s", completed.returncode)
        return {
            "ok": completed.returncode == 0,
            "returnCode": completed.returncode,
            "output": output[-4000:],
        }

    def _require_prep_token(self, payload: dict[str, Any]) -> None:
        expected = os.environ.get("PREP_MODE_TOKEN", "").strip()
        provided = str(payload.get("token") or "").strip()
        if not provided:
            provided = str(payload.get("prepToken") or "").strip()
        if not expected or provided != expected:
            logger.warning(
                "Prep token rejected. expected=%s provided=%s",
                secret_fingerprint(expected),
                secret_fingerprint(provided),
            )
            raise PermissionError("invalid_prep_token")

    def _read_lesson_markdown(self, lesson: dict[str, Any]) -> str:
        source = str(lesson.get("lessonPlanSource") or "").strip()
        if source:
            path = (ROOT / source).resolve()
            if str(path).startswith(str(ROOT.resolve())) and path.exists():
                return path.read_text(encoding="utf-8")
        lesson_id = str(lesson.get("id") or "").strip()
        if lesson_id:
            path = LESSON_DIR / f"{lesson_id}.md"
            if path.exists():
                return path.read_text(encoding="utf-8")
        return ""

    def _build_lesson_from_markdown(self, lesson_id: str, markdown: str, generated_by: str) -> dict[str, Any]:
        fallback = generate_lessons.build_fallback_lesson(LESSON_DIR / f"{lesson_id}.md", markdown)
        return self._normalize_lesson_json(fallback, lesson_id, markdown, generated_by)

    def _normalize_lesson_json(self, source: dict[str, Any], lesson_id: str, markdown: str, generated_by: str) -> dict[str, Any]:
        fallback = generate_lessons.build_fallback_lesson(LESSON_DIR / f"{lesson_id}.md", markdown)
        merged = {**fallback, **source}
        title = str(merged.get("title") or fallback.get("title") or lesson_id).strip()
        lesson = {
            **merged,
            "id": lesson_id,
            "title": title,
            "subtitle": str(merged.get("subtitle") or "课堂对话 AI").strip(),
            "questionPrompt": str(merged.get("questionPrompt") or fallback["questionPrompt"]).strip(),
            "aiStudentPrompt": str(merged.get("aiStudentPrompt") or fallback["aiStudentPrompt"]).strip(),
            "askPanelTitle": str(merged.get("askPanelTitle") or fallback["askPanelTitle"]).strip(),
            "askPanelDescription": str(merged.get("askPanelDescription") or fallback["askPanelDescription"]).strip(),
            "questionPlaceholder": str(merged.get("questionPlaceholder") or "输入学生问题").strip(),
            "lessonPlanSource": f"lesson_plan/{lesson_id}.md",
            generate_lessons.SOURCE_HASH_KEY: generate_lessons.markdown_hash(markdown),
            generate_lessons.GENERATED_BY_KEY: generated_by,
        }
        for key in ["goals", "stages", "questionCues", "flowerCards", "thinkingSteps", "reflectionHints", "presets"]:
            value = lesson.get(key)
            lesson[key] = value if isinstance(value, list) else fallback.get(key, [])
        for key in ["keyPoints", "difficultPoints", "coreStatement", "summaryTemplate", "homeworkTemplate"]:
            lesson[key] = str(lesson.get(key) or fallback.get(key) or "").strip()
        lesson["emptyAskMark"] = str(lesson.get("emptyAskMark") or generate_lessons.first_cjk_char(title) or "问")
        lesson["emptyReflectMark"] = str(lesson.get("emptyReflectMark") or "问")
        return lesson

    def _lesson_id_from_payload(self, payload: dict[str, Any], markdown: str) -> str:
        explicit = str(payload.get("lessonId") or payload.get("id") or "").strip()
        if explicit:
            return generate_lessons.slugify(explicit)
        title = str(payload.get("title") or generate_lessons.extract_title(markdown) or "new-lesson").strip()
        return generate_lessons.slugify(title)

    def _build_draft_markdown(self, title: str, source_text: str, brief: str) -> str:
        return (
            f"# {title}\n\n"
            "## 学习目标\n"
            "1、理解课文主要内容，梳理关键语句和核心观点。\n"
            "2、通过学生自主向AI提问，围绕文本内容、写作手法和现实意义展开探究。\n"
            "3、回答AI的提问，结合自己的经历或见闻表达观点。\n\n"
            "## 学习重点\n"
            "抓住课文中的关键内容和表达特点，理解作者想要强调的核心观点。\n\n"
            "## 学习难点\n"
            "结合AI回应和课堂讨论，把文本理解推进到现实思辨和表达训练。\n\n"
            "## 教学设计\n\n"
            "### 一、导入与整体感知\n"
            "教师引导学生回顾课文内容，明确本节课讨论的核心问题。\n\n"
            "### 二、文本细读\n"
            "围绕关键词句、人物或意象、写作手法和作者态度展开分析。\n\n"
            "### 三、对话AI 深入探究\n"
            "#### （一）学生问AI\n"
            "请以小组为单位，围绕课文内容、写作手法、作者意图或现实意义，设计一个有价值的问题，向AI发出提问。\n\n"
            "#### （二）AI问学生\n"
            "**AI提问**：请结合课文内容和自己的经历，说说你对本课核心观点的理解。\n\n"
            "## 预设问题\n"
            "- 这篇课文最值得追问的问题是什么？\n"
            "  可以先抓住课文中的关键内容，再回到作者想表达的核心观点。\n\n"
            "## 教师补充材料\n"
            f"### 课文原文\n{source_text or '（请补充课文原文）'}\n\n"
            f"### 简要思路\n{brief or '（请补充教学思路）'}\n"
        )

    def _generate_lesson_with_ai(self, title: str, source_text: str, brief: str, fallback_markdown: str, fallback_lesson: dict[str, Any]) -> dict[str, Any] | None:
        endpoint = os.environ.get("PREP_AI_ENDPOINT", "").strip()
        api_key = os.environ.get("PREP_AI_API_KEY", "").strip()
        model = os.environ.get("PREP_AI_MODEL", "deepseek-ai/DeepSeek-V4-Flash").strip()
        if not endpoint or not api_key:
            return None
        examples = self._lesson_style_examples()
        prompt = (
            "你是语文公开课导学案与课堂互动模板生成器。请参考现有导学案风格，根据课文原文和教师简要思路生成新导学案。\n"
            "只能输出 JSON 对象，不要 Markdown 代码块。JSON 格式必须为：{\"markdown\": \"...\", \"lesson\": {...}}。\n"
            "markdown 要是完整导学案，lesson 要能直接用于课堂互动模板。\n"
            "lesson 必须包含字段：title, subtitle, questionPrompt, aiStudentPrompt, askPanelTitle, askPanelDescription, "
            "questionPlaceholder, questionCues, flowerCards, thinkingSteps, reflectionHints, presets, goals, stages, "
            "keyPoints, difficultPoints, coreStatement, summaryTemplate, homeworkTemplate。\n"
            "presets 每项包含 title, category, question, keywords, answer；questionCues 要具体，不要泛泛而谈。\n\n"
            f"课题：{title}\n\n课文原文：\n{source_text}\n\n教师简要思路：\n{brief}\n\n"
            f"默认兜底 Markdown：\n{fallback_markdown}\n\n默认兜底 JSON：\n{json.dumps(fallback_lesson, ensure_ascii=False)}\n\n"
            f"现有导学案风格参考：\n{examples}"
        )
        url, mode = generate_lessons.normalize_endpoint(endpoint)
        request = urllib.request.Request(
            url,
            data=json.dumps(generate_lessons.build_ai_payload(mode, model, prompt), ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._prep_ai_timeout()) as response:
                raw = response.read().decode("utf-8")
            text = generate_lessons.strip_code_fence(generate_lessons.extract_ai_text(json.loads(raw)))
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except (OSError, TimeoutError, json.JSONDecodeError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            logger.warning("Prep AI generation failed. error=%s", exc)
            return None

    def _lesson_style_examples(self) -> str:
        parts = []
        for path in sorted(LESSON_DIR.glob("*.md"))[:3]:
            text = path.read_text(encoding="utf-8")
            parts.append(f"--- {path.name} ---\n{text[:5000]}")
        return "\n\n".join(parts)

    def _push_lesson_to_draft_branch(self, markdown_path: str, markdown: str, lesson_path: str, lesson: dict[str, Any], commit_message: str) -> str:
        branch = self._prep_branch()
        with self._git_repo() as (workdir, env):
            self._run_git(["git", "fetch", "origin", branch], workdir, env, check=False)
            checkout = subprocess.run(["git", "checkout", branch], cwd=workdir, env=env, text=True, capture_output=True)
            if checkout.returncode != 0:
                self._run_git(["git", "checkout", "-b", branch], workdir, env)

            (workdir / markdown_path).parent.mkdir(parents=True, exist_ok=True)
            (workdir / markdown_path).write_text(markdown.rstrip() + "\n", encoding="utf-8")
            (workdir / lesson_path).parent.mkdir(parents=True, exist_ok=True)
            (workdir / lesson_path).write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._write_lesson_index(workdir, lesson)
            self._run_git(["git", "add", markdown_path, lesson_path, "public/generated-lessons/index.json"], workdir, env)
            diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=workdir, env=env)
            if diff.returncode == 0:
                return self._run_git(["git", "rev-parse", "HEAD"], workdir, env).strip()
            self._run_git(["git", "commit", "-m", commit_message], workdir, env)
            self._run_git(["git", "push", "origin", branch], workdir, env)
            return self._run_git(["git", "rev-parse", "HEAD"], workdir, env).strip()

    @contextmanager
    def _git_repo(self):
        repo = os.environ.get("PREP_GIT_REPO", "").strip()
        private_key = os.environ.get("PREP_GIT_SSH_PRIVATE_KEY", "").strip()
        if not repo:
            raise RuntimeError("prep_git_repo_missing")
        if not private_key:
            raise RuntimeError("prep_git_ssh_private_key_missing")
        user_name = os.environ.get("PREP_GIT_USER_NAME", "prep-bot").strip()
        user_email = os.environ.get("PREP_GIT_USER_EMAIL", "prep-bot@example.local").strip()

        with tempfile.TemporaryDirectory(prefix="lesson-prep-") as tmp:
            workdir = Path(tmp) / "repo"
            key_path = Path(tmp) / "prep_key"
            key_path.write_text(private_key.replace("\\n", "\n").strip() + "\n", encoding="utf-8")
            key_path.chmod(0o600)
            ssh_command = f"ssh -i {key_path} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
            env = {**os.environ, "GIT_SSH_COMMAND": ssh_command}
            self._run_git(["git", "clone", repo, str(workdir)], ROOT, env)
            self._run_git(["git", "config", "user.name", user_name], workdir, env)
            self._run_git(["git", "config", "user.email", user_email], workdir, env)
            yield workdir, env

    def _read_lessons_from_git_ref(self, workdir: Path, env: dict[str, str], ref: str) -> list[dict[str, Any]]:
        try:
            index_raw = self._run_git(["git", "show", f"{ref}:public/generated-lessons/index.json"], workdir, env)
            index = json.loads(index_raw)
        except (RuntimeError, json.JSONDecodeError):
            return []
        lessons = []
        for item in index.get("lessons", []) if isinstance(index, dict) else []:
            lesson_id = str(item.get("id", "")).strip()
            if not lesson_id:
                continue
            draft = self._read_lesson_from_git_ref(workdir, env, ref, lesson_id)
            if draft:
                lessons.append(draft)
        return lessons

    def _read_lesson_from_git_ref(self, workdir: Path, env: dict[str, str], ref: str, lesson_id: str) -> dict[str, Any]:
        lesson_path = f"public/generated-lessons/{lesson_id}.json"
        try:
            lesson = json.loads(self._run_git(["git", "show", f"{ref}:{lesson_path}"], workdir, env))
        except (RuntimeError, json.JSONDecodeError):
            return {}
        markdown_path = str(lesson.get("lessonPlanSource") or f"lesson_plan/{lesson_id}.md")
        try:
            markdown = self._run_git(["git", "show", f"{ref}:{markdown_path}"], workdir, env)
        except RuntimeError:
            markdown = ""
        return {"id": lesson_id, "lesson": lesson, "markdown": markdown}

    def _write_lesson_index(self, workdir: Path, lesson: dict[str, Any]) -> None:
        index_path = workdir / "public/generated-lessons/index.json"
        lessons = []
        if index_path.exists():
            try:
                parsed = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                parsed = {}
            lessons = parsed.get("lessons", []) if isinstance(parsed, dict) and isinstance(parsed.get("lessons"), list) else []
        item = {"id": lesson["id"], "title": lesson["title"], "subtitle": lesson.get("subtitle", "")}
        lessons = [entry for entry in lessons if entry.get("id") != lesson["id"]]
        lessons.append(item)
        lessons.sort(key=lambda entry: str(entry.get("title", "")))
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps({"lessons": lessons}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _prep_branch(self) -> str:
        return os.environ.get("PREP_GIT_BRANCH", "lesson-drafts").strip() or "lesson-drafts"

    def _target_branch(self) -> str:
        return os.environ.get("PREP_GIT_TARGET_BRANCH", "v2").strip() or "v2"

    def _prep_ai_timeout(self) -> int:
        raw = os.environ.get("PREP_AI_TIMEOUT_SECONDS", "300").strip()
        try:
            return max(30, min(900, int(raw)))
        except ValueError:
            return 300

    @staticmethod
    def _run_git(command: list[str], cwd: Path, env: dict[str, str], check: bool = True) -> str:
        completed = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=120)
        if check and completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "git_failed")[-2000:])
        return completed.stdout


class DialogueRequestHandler(BaseHTTPRequestHandler):
    server_version = "LessonTemplateV2/2.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        logger.info("GET %s", parsed.path)
        self._send_static(parsed.path)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        logger.info("HEAD %s", parsed.path)
        self._send_static(parsed.path, head_only=True)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json()
        logger.info("POST %s", parsed.path)

        if parsed.path == "/api/deploy/update":
            if not self._is_deploy_request_authorized(parsed.query):
                self._send_json({"ok": False, "error": "forbidden"}, HTTPStatus.FORBIDDEN)
                return
            try:
                result = self.server.engine.update_container()
            except subprocess.TimeoutExpired:
                self._send_json({"ok": False, "error": "update_timeout"}, HTTPStatus.GATEWAY_TIMEOUT)
                return
            except OSError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(result, HTTPStatus.OK if result["ok"] else HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        routes = {
            "/api/prep/validate-token": self.server.engine.validate_prep_token,
            "/api/prep/templates": self.server.engine.list_prep_templates,
            "/api/prep/parse": self.server.engine.parse_prep_markdown,
            "/api/prep/generate": self.server.engine.generate_prep_lesson,
            "/api/prep/save": self.server.engine.save_prep_lesson,
            "/api/prep/drafts": self.server.engine.list_prep_drafts,
            "/api/prep/merge-draft": self.server.engine.merge_prep_draft,
        }
        handler = routes.get(parsed.path)
        if handler:
            try:
                self._send_json(handler(payload))
            except PermissionError:
                self._send_json({"ok": False, "error": "forbidden"}, HTTPStatus.FORBIDDEN)
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except RuntimeError as exc:
                logger.exception("Prep API failed. path=%s", parsed.path)
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            except Exception as exc:  # noqa: BLE001 - API boundary should return JSON.
                logger.exception("Prep API failed. path=%s", parsed.path)
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.info("[%s] %s %s", timestamp, self.address_string(), format % args)

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

    def _is_deploy_request_authorized(self, query: str) -> bool:
        expected_token = os.environ.get("DEPLOY_WEBHOOK_TOKEN", "").strip()
        if not expected_token:
            return False
        tokens = parse_qs(query).get("token", [])
        return bool(tokens and tokens[0] == expected_token)

    def _send_static(self, request_path: str, head_only: bool = False) -> None:
        if not STATIC_DIR.exists():
            self._send_json({"error": "dist_not_built"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return

        clean_path = request_path.lstrip("/") or "index.html"
        candidate = (STATIC_DIR / clean_path).resolve()
        if not str(candidate).startswith(str(STATIC_DIR.resolve())):
            self._send_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.exists():
            candidate = STATIC_DIR / "index.html"

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix == ".js":
            content_type = "text/javascript"
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") or content_type == "application/json" else content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
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
    actual_port = port if host != "127.0.0.1" else find_available_port(port)
    server = DialogueHTTPServer((host, actual_port), DialogueRequestHandler)
    print(f"课堂模板平台已启动：http://{host}:{actual_port}")
    print("按 Ctrl+C 结束服务。")
    server.serve_forever()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="课堂模板平台 v2")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run(args.host, args.port)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def secret_fingerprint(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return "missing"
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12]
    return f"len:{len(cleaned)} sha256:{digest}"


if __name__ == "__main__":
    main()
