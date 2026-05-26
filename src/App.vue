<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="title-block">
        <h1>{{ lesson.title || "课堂模板平台" }}</h1>
        <p>{{ lesson.subtitle || "对话 AI 课堂互动" }}</p>
      </div>
      <button class="status-pill" :class="{ loading: busy }" type="button" @click="testConnection">
        {{ busy ? "AI思考中..." : runtimeStatus }}
      </button>
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
                  <span class="source-tag">{{ sourceLabel(item.source) }}</span>
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
              @keydown.enter.prevent="askQuestion()"
            />
            <button class="action-button" type="button" :disabled="busy" @click="askQuestion()">提交问题</button>
            <button class="ghost-button" type="button" @click="saveRecord">保存记录</button>
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
            <textarea v-model="reflectionInput" placeholder="输入学生代表观点或小组讨论后的观点"></textarea>
            <div class="reflection-hints" aria-label="思考提示">
              <div v-for="hint in lesson.reflectionHints" :key="hint.title" class="hint-card">
                <strong>{{ hint.title }}</strong>{{ hint.description }}
              </div>
            </div>
            <div class="button-row">
              <button class="action-button" type="button" :disabled="busy" @click="respondToReflection">生成点评</button>
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
                <div class="feedback-box">{{ activeReflection.feedback }}</div>
                <div class="follow-box">追问：{{ activeReflection.followUp }}</div>
                <div v-if="activeReflection.followUpFeedback" class="follow-response-box">
                  学生回应：{{ activeReflection.followUpAnswer }}

                  AI 二次回应：{{ activeReflection.followUpFeedback }}
                </div>
                <div v-else class="follow-up-composer">
                  <textarea v-model="followUpInput" placeholder="学生继续回答 AI 的追问"></textarea>
                  <div class="button-row">
                    <button class="action-button" type="button" :disabled="busy" @click="respondToFollowUp">回应追问</button>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </section>
      </div>
    </section>
  </main>

  <button class="settings-button" type="button" title="设置" @click="settingsOpen = true">⚙</button>

  <section v-if="settingsOpen" class="settings-backdrop" @click.self="settingsOpen = false">
    <form class="settings-panel" @submit.prevent="saveSettingsForm">
      <div class="panel-header">
        <h2>设置</h2>
        <p>默认使用 SiliconFlow 兼容接口，只填写 API Key 即可启用远程 AI。</p>
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
        <input v-model="settingsDraft.model" placeholder="留空则使用服务端默认模型" />
      </label>
      <label class="check-row">
        <input v-model="settingsDraft.preferRemote" type="checkbox" />
        <span>优先使用远程 AI</span>
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
import { callApi, loadLesson, loadLessonIndex } from "./services/api";
import { buildFallbackAnswer, buildFollowUpResponse, buildReflectionFeedback } from "./services/localAi";
import { buildSettingsImportUrl, defaultSettings, importSettingsFromUrl, loadLessonId, loadSettings, saveLessonId, saveSettings } from "./services/storage";
import { downloadSessionMarkdown } from "./services/record";

const tabs = [
  { key: "overview", label: "课堂脉络" },
  { key: "ask", label: "学生问 AI" },
  { key: "reflect", label: "AI 问学生" },
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
const busy = ref(false);
const toastText = ref("");
const exportedSettingsUrl = ref("");
const questionInput = ref("");
const reflectionInput = ref("");
const followUpInput = ref("");
const studentQuestions = ref([]);
const reflections = ref([]);
const chatStream = ref(null);

const activeReflection = computed(() => reflections.value[reflections.value.length - 1] || null);

onMounted(async () => {
  try {
    const index = await loadLessonIndex();
    lessonIndex.lessons = Array.isArray(index.lessons) ? index.lessons : [];
    selectedLessonId.value = loadLessonId() || lessonIndex.lessons[0]?.id || "";
    await switchLesson(selectedLessonId.value);
    runtimeStatus.value = settings.value.preferRemote ? "远程 AI 优先" : "课堂模式：本地";
    if (importedSettingsResult.imported) {
      showToast("AI 配置已从链接导入");
    } else if (importedSettingsResult.error) {
      showToast(importedSettingsResult.error);
    }
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

async function askQuestion(forceQuestion) {
  const cleaned = String(forceQuestion || questionInput.value).trim();
  if (!cleaned) {
    showToast("请先输入一个问题");
    return;
  }

  const fallback = buildFallbackAnswer(cleaned, lesson.value);
  const result = await runAiTask("正在生成课堂回答", async (signal) => {
    if (!shouldUseRemote(fallback.source)) {
      return fallback;
    }
    return callApi("/api/ask", buildAiPayload({ question: cleaned, lesson: lesson.value, fallback }), signal);
  }, fallback);

  studentQuestions.value.push({
    question: cleaned,
    answer: result.answer,
    source: result.source || fallback.source,
    matchedTitle: result.matchedTitle || fallback.matchedTitle,
  });
  questionInput.value = "";
  await nextTick();
  if (chatStream.value) {
    chatStream.value.scrollTop = chatStream.value.scrollHeight;
  }
}

async function respondToReflection() {
  const response = reflectionInput.value.trim();
  const fallback = buildReflectionFeedback(response, lesson.value);
  const result = await runAiTask("正在生成点评与追问", async (signal) => {
    if (!settings.value.preferRemote) {
      return fallback;
    }
    return callApi("/api/reflect", buildAiPayload({ response, lesson: lesson.value, fallback }), signal);
  }, fallback);

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
  const result = await runAiTask("正在生成追问回应", async (signal) => {
    if (!settings.value.preferRemote) {
      return fallback;
    }
    return callApi("/api/follow-up", buildAiPayload({
      followUp: activeReflection.value.followUp,
      response,
      lesson: lesson.value,
      fallback,
    }), signal);
  }, fallback);
  activeReflection.value.followUpAnswer = response;
  activeReflection.value.followUpFeedback = result.response;
  followUpInput.value = "";
}

async function runAiTask(detail, request, fallback) {
  busy.value = true;
  runtimeStatus.value = settings.value.preferRemote ? "AI思考中..." : "课堂模式：本地";
  try {
    const result = await request();
    runtimeStatus.value = result.usingRemote ? "AI后端已连接" : (settings.value.preferRemote ? "远程 AI 优先" : "课堂模式：本地");
    return result;
  } catch (error) {
    runtimeStatus.value = "AI后端请求错误";
    showToast(`${detail}失败，已使用本地模板`);
    return fallback;
  } finally {
    busy.value = false;
  }
}

async function testConnection() {
  const config = settingsOpen.value ? { ...settingsDraft } : settings.value;
  if (!config.endpoint || !config.apiKey) {
    showToast("请先填写 API Key");
    runtimeStatus.value = "课堂模式：本地";
    return;
  }
  busy.value = true;
  try {
    const result = await callApi("/api/runtime/test", buildAiPayload({ lesson: lesson.value }, config));
    runtimeStatus.value = result.usingRemote ? "AI后端已连接" : "AI后端请求错误";
    showToast(result.usingRemote ? "AI后端已连接" : "AI后端不可用");
  } catch {
    runtimeStatus.value = "AI后端请求错误";
    showToast("AI后端连接失败");
  } finally {
    busy.value = false;
  }
}

function buildAiPayload(payload, config = settings.value) {
  return {
    ...payload,
    clientConfig: {
      endpoint: config.endpoint,
      apiKey: config.apiKey,
      model: config.model,
    },
  };
}

function shouldUseRemote(source) {
  return settings.value.preferRemote && source !== "preset";
}

function saveRecord() {
  if (!studentQuestions.value.length && !reflections.value.length) {
    showToast("当前还没有可保存的课堂记录");
    return;
  }
  downloadSessionMarkdown(lesson.value, studentQuestions.value, reflections.value);
  showToast("课堂记录已下载");
}

function saveSettingsForm() {
  settings.value = { ...settingsDraft };
  saveSettings(settings.value);
  exportedSettingsUrl.value = "";
  settingsOpen.value = false;
  runtimeStatus.value = settings.value.preferRemote ? "远程 AI 优先" : "课堂模式：本地";
  showToast("设置已保存");
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
    return "远程生成";
  }
  return "本地模板";
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
