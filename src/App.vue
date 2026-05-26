<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="title-block">
        <h1>{{ lesson.title || "课堂模板平台" }}</h1>
        <p>{{ lesson.subtitle || "对话 AI 课堂互动" }}</p>
      </div>
      <div class="topbar-controls">
        <div class="mode-toggle" aria-label="AI 模式">
          <button
            v-for="mode in aiModes"
            :key="mode.key"
            type="button"
            :class="{ active: settings.aiMode === mode.key }"
            :disabled="busy"
            @click="setAiMode(mode.key)"
          >
            {{ mode.label }}
          </button>
        </div>
        <button class="status-pill" :class="{ loading: busy }" type="button" :disabled="busy && !isRunningTask('connection')" @click="testConnection">
          {{ busy ? activeTaskLabel : runtimeStatus }}
        </button>
      </div>
      <nav class="tabs" aria-label="课堂环节">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab"
          :class="{ active: activeTab === tab.key }"
          type="button"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </nav>
    </header>

    <section v-if="loadError" class="load-error panel">
      {{ loadError }}
    </section>

    <section v-else-if="activeTab === 'overview'" class="view active">
      <div class="overview-grid">
        <aside class="panel">
          <div class="panel-header">
            <h2>课堂脉络</h2>
            <p>根据当前课文模板生成，可在设置中切换课文。</p>
          </div>
          <ol class="stage-list">
            <li v-for="stage in lesson.stages" :key="stage.title">
              <strong>{{ stage.title }}</strong>
              <span>{{ stage.description }}</span>
            </li>
          </ol>
        </aside>
        <section class="panel">
          <div class="panel-header">
            <h2>学习目标</h2>
            <p>{{ lesson.lessonPlanSource || "lesson_plan" }}</p>
          </div>
          <div class="info-grid">
            <article class="info-block">
              <strong>目标</strong>
              <p v-for="goal in lesson.goals" :key="goal">{{ goal }}</p>
            </article>
            <article class="info-block">
              <strong>重点</strong>
              <p>{{ lesson.keyPoints || "未配置" }}</p>
            </article>
            <article class="info-block">
              <strong>难点</strong>
              <p>{{ lesson.difficultPoints || "未配置" }}</p>
            </article>
            <article class="info-block">
              <strong>核心问题</strong>
              <p>{{ lesson.aiStudentPrompt }}</p>
            </article>
          </div>
        </section>
      </div>
    </section>

    <section v-else-if="activeTab === 'ask'" class="view active">
      <div class="ask-grid">
        <aside class="panel">
          <div class="panel-header">
            <h2>{{ lesson.askPanelTitle || "看课文，也看自己" }}</h2>
            <p>{{ lesson.questionPrompt }}</p>
          </div>
          <div class="flower-gallery" :aria-label="lesson.askPanelTitle">
            <figure v-for="card in lesson.flowerCards" :key="card.mark + card.title" class="flower-card">
              <div class="visual-mark">{{ card.mark }}</div>
              <figcaption class="flower-caption">
                <strong>{{ card.title }}</strong>
                <span>{{ card.description }}</span>
              </figcaption>
            </figure>
          </div>
          <div class="question-cues">
            <div v-for="cue in lesson.questionCues" :key="cue" class="cue">{{ cue }}</div>
          </div>
        </aside>

        <section class="panel chat-panel">
          <div class="panel-header">
            <h2>对话记录</h2>
            <p>{{ lesson.askPanelDescription }}</p>
          </div>
          <div ref="chatStream" class="chat-stream">
            <div v-if="!studentQuestions.length" class="empty-state">
              <div class="large-mark">{{ lesson.emptyAskMark || "问" }}</div>
              <strong>等待学生提出第一个问题</strong>
            </div>
            <template v-for="(item, index) in studentQuestions" :key="`${index}-${item.question}`">
              <article class="message question">
                <div class="message-label"><span>学生问题 {{ index + 1 }}</span></div>
                <div class="message-body">{{ item.question }}</div>
              </article>
              <article class="message answer">
                <div class="message-label">
                  <span>AI 回答</span>
                  <span class="message-actions">
                    <span class="source-tag">{{ sourceLabel(item.source) }}</span>
                    <button
                      v-if="isRunningTask('ask-regen', index)"
                      class="inline-button danger"
                      type="button"
                      @click="cancelActiveTask"
                    >
                      终止
                    </button>
                    <button
                      v-else
                      class="inline-button"
                      type="button"
                      :disabled="busy"
                      @click="regenerateQuestion(index)"
                    >
                      重新生成
                    </button>
                  </span>
                </div>
                <div class="message-body">{{ item.answer }}</div>
              </article>
            </template>
          </div>
          <div class="composer">
            <input
              v-model="questionInput"
              class="question-input"
              :placeholder="lesson.questionPlaceholder"
              :disabled="isQuestionBusy"
              @keydown.enter.prevent="askQuestion()"
            />
            <button class="action-button" type="button" :disabled="busy" @click="askQuestion()">提交问题</button>
            <button v-if="isRunningTask('ask-new')" class="danger-button" type="button" @click="cancelActiveTask">终止</button>
            <button v-else class="ghost-button" type="button" :disabled="busy" @click="saveRecord">保存记录</button>
          </div>
        </section>
      </div>
    </section>

    <section v-else-if="activeTab === 'reflect'" class="view active">
      <div class="reflect-grid">
        <section class="panel">
          <div class="panel-header">
            <h2>AI 提问</h2>
            <p>学习活动</p>
          </div>
          <div class="prompt-block">
            <div class="prompt-quote">{{ lesson.aiStudentPrompt }}</div>
            <div class="thinking-steps">
              <div v-for="step in lesson.thinkingSteps" :key="step.title" class="step">
                <strong>{{ step.title }}</strong>
                <span>{{ step.description }}</span>
              </div>
            </div>
          </div>
          <div class="reflection-editor">
            <textarea v-model="reflectionInput" :disabled="busy" placeholder="输入学生代表观点或小组讨论后的观点"></textarea>
            <div class="reflection-hints" aria-label="思考提示">
              <div v-for="hint in lesson.reflectionHints" :key="hint.title" class="hint-card">
                <strong>{{ hint.title }}</strong>{{ hint.description }}
              </div>
            </div>
            <div class="button-row">
              <button class="action-button" type="button" :disabled="busy" @click="respondToReflection">生成点评</button>
              <button v-if="isRunningTask('reflect-new')" class="danger-button" type="button" @click="cancelActiveTask">终止</button>
            </div>
          </div>
        </section>

        <section class="panel feedback-panel">
          <div class="panel-header">
            <h2>AI 点评与追问</h2>
            <p>保留不同立场，把讨论推进到现实中的选择与坚守。</p>
          </div>
          <div class="feedback-body">
            <div class="feedback-output">
              <div v-if="!activeReflection" class="empty-state">
                <div class="large-mark">{{ lesson.emptyReflectMark || "问" }}</div>
                <strong>等待学生观点</strong>
              </div>
              <template v-else>
                <div class="feedback-box">
                  <div class="box-toolbar">
                    <span>AI 点评</span>
                    <button
                      v-if="isRunningTask('reflect-regen', reflections.length - 1)"
                      class="inline-button danger"
                      type="button"
                      @click="cancelActiveTask"
                    >
                      终止
                    </button>
                    <button
                      v-else
                      class="inline-button"
                      type="button"
                      :disabled="busy"
                      @click="regenerateReflection(reflections.length - 1)"
                    >
                      重新生成
                    </button>
                  </div>
                  <div>{{ activeReflection.feedback }}</div>
                </div>
                <div class="follow-box">追问：{{ activeReflection.followUp }}</div>
                <div v-if="activeReflection.followUpFeedback" class="follow-response-box">
                  <div class="box-toolbar">
                    <span>二次回应</span>
                    <button
                      v-if="isRunningTask('follow-up-regen', reflections.length - 1)"
                      class="inline-button danger"
                      type="button"
                      @click="cancelActiveTask"
                    >
                      终止
                    </button>
                    <button
                      v-else
                      class="inline-button"
                      type="button"
                      :disabled="busy"
                      @click="regenerateFollowUp(reflections.length - 1)"
                    >
                      重新生成
                    </button>
                  </div>
                  学生回应：{{ activeReflection.followUpAnswer }}

                  AI 二次回应：{{ activeReflection.followUpFeedback }}
                </div>
                <div v-else class="follow-up-composer">
                  <textarea v-model="followUpInput" :disabled="isFollowUpBusy" placeholder="学生继续回答 AI 的追问"></textarea>
                  <div class="button-row">
                    <button class="action-button" type="button" :disabled="busy" @click="respondToFollowUp">回应追问</button>
                    <button v-if="isRunningTask('follow-up-new')" class="danger-button" type="button" @click="cancelActiveTask">终止</button>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </section>
      </div>
    </section>
  </main>

  <button class="settings-button" type="button" title="设置" @click="openSettings">⚙</button>

  <section v-if="settingsOpen" class="settings-backdrop" @click.self="settingsOpen = false">
    <form class="settings-panel" @submit.prevent="saveSettingsForm">
      <div class="panel-header">
        <h2>设置</h2>
        <p>本地模式使用课堂模板生成模拟回答；大语言模型模式由浏览器直连 AI API。</p>
      </div>
      <div class="settings-mode-block">
        <span>AI 模式</span>
        <div class="mode-toggle wide" aria-label="设置 AI 模式">
          <button
            v-for="mode in aiModes"
            :key="mode.key"
            type="button"
            :class="{ active: settingsDraft.aiMode === mode.key }"
            @click="settingsDraft.aiMode = mode.key"
          >
            {{ mode.label }}
          </button>
        </div>
        <p>{{ modeHelpText(settingsDraft.aiMode) }}</p>
      </div>
      <label>
        <span>课文</span>
        <select v-model="selectedLessonId">
          <option v-for="item in lessonIndex.lessons" :key="item.id" :value="item.id">{{ item.title }}</option>
        </select>
      </label>
      <label>
        <span>API Endpoint</span>
        <input v-model="settingsDraft.endpoint" placeholder="https://api.openai.com/v1/responses" />
      </label>
      <label>
        <span>API Key</span>
        <input v-model="settingsDraft.apiKey" type="password" placeholder="填写 SiliconFlow API Key" />
      </label>
      <label>
        <span>Model</span>
        <input v-model="settingsDraft.model" placeholder="deepseek-ai/DeepSeek-V4-Flash" />
      </label>
      <div class="export-config-box">
        <div>
          <strong>导出配置链接</strong>
          <span>链接包含 API Key，打开后会自动导入当前 AI 配置。</span>
        </div>
        <button class="ghost-button" type="button" @click="exportSettingsUrl">生成链接</button>
        <input v-if="exportedSettingsUrl" :value="exportedSettingsUrl" readonly @focus="$event.target.select()" />
      </div>
      <div class="settings-actions">
        <button class="ghost-button" type="button" @click="resetSettingsForm">恢复默认</button>
        <button class="ghost-button" type="button" @click="testConnection">测试连接</button>
        <button class="action-button" type="submit">保存</button>
      </div>
    </form>
  </section>

  <div class="toast" :class="{ show: toastText }">{{ toastText }}</div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { loadLesson, loadLessonIndex } from "./services/api";
import { buildFallbackAnswer, buildFollowUpResponse, buildReflectionFeedback } from "./services/localAi";
import { answerStudentQuestion, respondToFollowUp as requestFollowUp, respondToReflection as requestReflection, testRemoteAi } from "./services/remoteAi";
import { buildSettingsImportUrl, defaultSettings, importSettingsFromUrl, loadLessonId, saveLessonId, saveSettings } from "./services/storage";
import { downloadSessionMarkdown } from "./services/record";

const tabs = [
  { key: "overview", label: "课堂脉络" },
  { key: "ask", label: "学生问 AI" },
  { key: "reflect", label: "AI 问学生" },
];
const aiModes = [
  { key: "local", label: "本地模式" },
  { key: "llm", label: "大语言模型模式" },
];

const activeTab = ref("overview");
const lesson = ref({});
const lessonIndex = reactive({ lessons: [] });
const selectedLessonId = ref("");
const importedSettingsResult = importSettingsFromUrl();
const settings = ref(importedSettingsResult.settings);
const settingsDraft = reactive({ ...settings.value });
const settingsOpen = ref(false);
const runtimeStatus = ref("课堂模式：本地");
const loadError = ref("");
const toastText = ref("");
const exportedSettingsUrl = ref("");
const questionInput = ref("");
const reflectionInput = ref("");
const followUpInput = ref("");
const studentQuestions = ref([]);
const reflections = ref([]);
const chatStream = ref(null);
const activeTask = ref(null);

const activeReflection = computed(() => reflections.value[reflections.value.length - 1] || null);
const busy = computed(() => Boolean(activeTask.value));
const activeTaskLabel = computed(() => activeTask.value?.label || "AI思考中...");
const isQuestionBusy = computed(() => isRunningTask("ask-new") || Boolean(activeTask.value?.type === "ask-regen"));
const isFollowUpBusy = computed(() => isRunningTask("follow-up-new") || Boolean(activeTask.value?.type === "follow-up-regen"));

onMounted(async () => {
  try {
    const index = await loadLessonIndex();
    lessonIndex.lessons = Array.isArray(index.lessons) ? index.lessons : [];
    selectedLessonId.value = loadLessonId() || lessonIndex.lessons[0]?.id || "";
    await switchLesson(selectedLessonId.value);
    if (importedSettingsResult.imported) {
      showToast("AI 配置已从链接导入");
    } else if (importedSettingsResult.error) {
      showToast(importedSettingsResult.error);
    }
    await initializeAiMode();
  } catch (error) {
    loadError.value = "课文模板加载失败，请确认 public/generated-lessons/index.json 已生成。";
  }
});

watch(selectedLessonId, async (id, previous) => {
  if (id && previous && id !== previous) {
    await switchLesson(id);
  }
});

async function switchLesson(id) {
  if (!id) {
    return;
  }
  lesson.value = normalizeLesson(await loadLesson(id));
  saveLessonId(id);
  studentQuestions.value = [];
  reflections.value = [];
  questionInput.value = "";
  reflectionInput.value = "";
  followUpInput.value = "";
}

async function askQuestion(forceQuestion, options = {}) {
  const cleaned = String(forceQuestion || questionInput.value).trim();
  if (!cleaned) {
    showToast("请先输入一个问题");
    return;
  }

  const fallback = buildFallbackAnswer(cleaned, lesson.value);
  const result = await runAiTask({
    type: options.replaceIndex === undefined ? "ask-new" : "ask-regen",
    targetIndex: options.replaceIndex,
    label: options.replaceIndex === undefined ? "正在生成课堂回答..." : "正在重新生成回答...",
    errorText: "课堂回答生成失败，已使用本地模板",
    fallback,
    request: (signal) => requestQuestionAnswer(cleaned, fallback, signal),
  });
  if (!result) {
    return;
  }

  const item = {
    question: cleaned,
    answer: result.answer,
    source: result.source || fallback.source,
    matchedTitle: result.matchedTitle || fallback.matchedTitle,
  };

  if (options.replaceIndex !== undefined) {
    studentQuestions.value.splice(options.replaceIndex, 1, item);
  } else {
    studentQuestions.value.push(item);
    questionInput.value = "";
  }

  await nextTick();
  if (chatStream.value) {
    chatStream.value.scrollTop = chatStream.value.scrollHeight;
  }
}

async function respondToReflection() {
  const response = reflectionInput.value.trim();
  if (!response) {
    showToast("请先输入学生观点");
    return;
  }
  const fallback = buildReflectionFeedback(response, lesson.value);
  const result = await runAiTask({
    type: "reflect-new",
    label: "正在生成点评与追问...",
    errorText: "点评与追问生成失败，已使用本地模板",
    fallback,
    request: (signal) => requestReflectionFeedback(response, fallback, signal),
  });
  if (!result) {
    return;
  }

  reflections.value.push({
    response,
    feedback: result.feedback,
    followUp: result.followUp || fallback.followUp,
    followUpAnswer: "",
    followUpFeedback: "",
  });
  followUpInput.value = "";
}

async function respondToFollowUp() {
  if (!activeReflection.value) {
    return;
  }
  const response = followUpInput.value.trim();
  if (!response) {
    showToast("请先输入学生对追问的回应");
    return;
  }
  const fallback = { response: buildFollowUpResponse(response, lesson.value) };
  const result = await runAiTask({
    type: "follow-up-new",
    label: "正在生成二次回应...",
    errorText: "二次回应生成失败，已使用本地模板",
    fallback,
    request: (signal) => requestFollowUpResponse(activeReflection.value.followUp, response, fallback, signal),
  });
  if (!result) {
    return;
  }
  activeReflection.value.followUpAnswer = response;
  activeReflection.value.followUpFeedback = result.response;
  followUpInput.value = "";
}

async function regenerateQuestion(index) {
  const item = studentQuestions.value[index];
  if (!item) {
    return;
  }
  await askQuestion(item.question, { replaceIndex: index });
}

async function regenerateReflection(index) {
  const item = reflections.value[index];
  if (!item) {
    return;
  }
  const fallback = buildReflectionFeedback(item.response, lesson.value);
  const result = await runAiTask({
    type: "reflect-regen",
    targetIndex: index,
    label: "正在重新生成点评...",
    errorText: "点评重新生成失败，已使用本地模板",
    fallback,
    request: (signal) => requestReflectionFeedback(item.response, fallback, signal),
  });
  if (!result) {
    return;
  }
  reflections.value.splice(index, 1, {
    response: item.response,
    feedback: result.feedback,
    followUp: result.followUp || fallback.followUp,
    followUpAnswer: "",
    followUpFeedback: "",
  });
}

async function regenerateFollowUp(index) {
  const item = reflections.value[index];
  if (!item || !item.followUpAnswer) {
    return;
  }
  const fallback = { response: buildFollowUpResponse(item.followUpAnswer, lesson.value) };
  const result = await runAiTask({
    type: "follow-up-regen",
    targetIndex: index,
    label: "正在重新生成二次回应...",
    errorText: "二次回应重新生成失败，已使用本地模板",
    fallback,
    request: (signal) => requestFollowUpResponse(item.followUp, item.followUpAnswer, fallback, signal),
  });
  if (!result) {
    return;
  }
  reflections.value[index].followUpFeedback = result.response;
}

async function runAiTask({ type, targetIndex = null, label, errorText, request, fallback }) {
  if (activeTask.value) {
    showToast("请等待当前生成结束，或先终止本次生成");
    return null;
  }
  const controller = new AbortController();
  activeTask.value = { type, targetIndex, label, controller };
  runtimeStatus.value = settings.value.aiMode === "llm" ? "大语言模型正在生成..." : "本地模式：使用课堂模板";
  try {
    const result = await request(controller.signal);
    runtimeStatus.value = result.usingRemote ? "大语言模型可用" : "本地模式：使用课堂模板";
    return result;
  } catch (error) {
    if (error.name === "AbortError") {
      runtimeStatus.value = modeStatusText(settings.value.aiMode);
      showToast("已终止本次生成");
      return null;
    }
    runtimeStatus.value = "大语言模型请求失败";
    showToast(errorText);
    return fallback;
  } finally {
    activeTask.value = null;
  }
}

async function testConnection() {
  const config = settingsOpen.value ? { ...settingsDraft } : settings.value;
  if (activeTask.value) {
    showToast("请等待当前生成结束，或先终止本次生成");
    return false;
  }
  if (!config.endpoint || !config.apiKey) {
    showToast("请先填写 API Key");
    runtimeStatus.value = modeStatusText(settings.value.aiMode);
    return false;
  }
  const controller = new AbortController();
  activeTask.value = { type: "connection", targetIndex: null, label: "正在测试 API...", controller };
  try {
    const result = await testRemoteAi(config, controller.signal);
    runtimeStatus.value = result.usingRemote ? "大语言模型可用" : "大语言模型不可用";
    showToast(result.usingRemote ? "大语言模型可用" : "大语言模型不可用");
    return result.usingRemote;
  } catch (error) {
    runtimeStatus.value = "大语言模型不可用";
    if (error.name !== "AbortError") {
      showToast("API 不可用，请检查接口配置、网络或跨域限制");
    }
    return false;
  } finally {
    activeTask.value = null;
  }
}

function requestQuestionAnswer(question, fallback, signal) {
  if (!shouldUseLlm(fallback.source)) {
    return fallback;
  }
  return answerStudentQuestion({ question, lesson: lesson.value, fallback, config: settings.value, signal });
}

function requestReflectionFeedback(response, fallback, signal) {
  if (settings.value.aiMode !== "llm") {
    return fallback;
  }
  return requestReflection({ response, lesson: lesson.value, fallback, config: settings.value, signal });
}

function requestFollowUpResponse(followUp, response, fallback, signal) {
  if (settings.value.aiMode !== "llm") {
    return fallback;
  }
  return requestFollowUp({
    followUp,
    response,
    lesson: lesson.value,
    fallback,
    config: settings.value,
    signal,
  });
}

function shouldUseLlm(source) {
  return settings.value.aiMode === "llm";
}

async function initializeAiMode() {
  runtimeStatus.value = modeStatusText(settings.value.aiMode);
  if (settings.value.aiMode !== "llm") {
    return;
  }
  const ok = await testConnection();
  if (!ok) {
    settings.value = { ...settings.value, aiMode: "local" };
    Object.assign(settingsDraft, settings.value);
    saveSettings(settings.value);
    runtimeStatus.value = modeStatusText("local");
    showToast("API 不可用，已切换为本地模式");
  }
}

async function setAiMode(mode) {
  if (activeTask.value) {
    showToast("请等待当前生成结束，或先终止本次生成");
    return;
  }
  settings.value = { ...settings.value, aiMode: mode };
  Object.assign(settingsDraft, settings.value);
  saveSettings(settings.value);
  runtimeStatus.value = modeStatusText(mode);
  showToast(mode === "llm" ? "已切换为大语言模型模式" : "已切换为本地模式");
  if (mode === "llm") {
    const ok = await testConnection();
    if (!ok) {
      settings.value = { ...settings.value, aiMode: "local" };
      Object.assign(settingsDraft, settings.value);
      saveSettings(settings.value);
      runtimeStatus.value = modeStatusText("local");
      showToast("API 不可用，已切换为本地模式");
    }
  }
}

function cancelActiveTask() {
  activeTask.value?.controller?.abort();
}

function isRunningTask(type, targetIndex = undefined) {
  if (!activeTask.value || activeTask.value.type !== type) {
    return false;
  }
  return targetIndex === undefined || activeTask.value.targetIndex === targetIndex;
}

function openSettings() {
  Object.assign(settingsDraft, settings.value);
  exportedSettingsUrl.value = "";
  settingsOpen.value = true;
}

function saveRecord() {
  if (!studentQuestions.value.length && !reflections.value.length) {
    showToast("当前还没有可保存的课堂记录");
    return;
  }
  downloadSessionMarkdown(lesson.value, studentQuestions.value, reflections.value);
  showToast("课堂记录已下载");
}

async function saveSettingsForm() {
  settings.value = { ...settingsDraft };
  saveSettings(settings.value);
  exportedSettingsUrl.value = "";
  settingsOpen.value = false;
  runtimeStatus.value = modeStatusText(settings.value.aiMode);
  showToast("设置已保存");
  if (settings.value.aiMode === "llm") {
    const ok = await testConnection();
    if (!ok) {
      settings.value = { ...settings.value, aiMode: "local" };
      Object.assign(settingsDraft, settings.value);
      saveSettings(settings.value);
      runtimeStatus.value = modeStatusText("local");
      showToast("API 不可用，已切换为本地模式");
    }
  }
}

function resetSettingsForm() {
  Object.assign(settingsDraft, defaultSettings());
  exportedSettingsUrl.value = "";
}

async function exportSettingsUrl() {
  const url = buildSettingsImportUrl(settingsDraft);
  exportedSettingsUrl.value = url;
  try {
    await navigator.clipboard.writeText(url);
    showToast("配置链接已复制");
  } catch {
    showToast("配置链接已生成，请手动复制");
  }
}

function showToast(text) {
  toastText.value = text;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toastText.value = "";
  }, 2600);
}

function sourceLabel(source) {
  if (source === "preset") {
    return "预设回答";
  }
  if (source === "generated") {
    return "大语言模型";
  }
  return "本地模式";
}

function modeStatusText(mode) {
  return mode === "llm" ? "大语言模型模式：浏览器直连 AI API" : "本地模式：使用课堂模板";
}

function modeHelpText(mode) {
  return mode === "llm" ? "使用真实 AI。每次打开页面会自动测试 API，可用后再进入课堂生成。" : "使用本地假 AI 模板，不请求网络，适合无 API 或网络不稳定时上课。";
}

function normalizeLesson(raw) {
  return {
    stages: [],
    goals: [],
    questionCues: [],
    flowerCards: [],
    thinkingSteps: [],
    reflectionHints: [],
    presets: [],
    ...raw,
  };
}
</script>
