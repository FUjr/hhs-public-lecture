const answerHistory = [];
const feedbackHistory = [];
let answerTurn = 0;
let feedbackTurn = 0;

export async function answerStudentQuestion({ question, lesson, fallback, config, signal }) {
  const prompt = buildAnswerPrompt(question, lesson);
  const answer = await requestRemoteText(prompt, config, signal);
  remember(answerHistory, answer);
  return {
    answer,
    source: "generated",
    matchedTitle: fallback?.matchedTitle || "",
    usingRemote: true,
  };
}

export async function respondToReflection({ response, lesson, fallback, config, signal }) {
  const prompt = buildReflectionPrompt(response, lesson);
  const feedback = await requestRemoteText(prompt, config, signal);
  remember(feedbackHistory, feedback);
  return {
    feedback,
    followUp: fallback?.followUp || buildFollowUp(response),
    usingRemote: true,
  };
}

export async function respondToFollowUp({ followUp, response, lesson, config, signal }) {
  const prompt = buildFollowUpPrompt(followUp, response, lesson);
  return {
    response: await requestRemoteText(prompt, config, signal),
    usingRemote: true,
  };
}

export async function testRemoteAi(config, signal) {
  const text = await requestRemoteText("请只回复：已连接", config, signal);
  return {
    connected: Boolean(text.trim()),
    usingRemote: Boolean(text.trim()),
  };
}

async function requestRemoteText(prompt, config = {}, signal) {
  const endpointInfo = normalizeEndpoint(config.endpoint);
  if (!endpointInfo.endpoint || !config.apiKey) {
    throw new Error("missing_config");
  }

  const response = await fetch(endpointInfo.endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify(buildPayload(endpointInfo.mode, config.model, prompt)),
    signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const payload = await response.json();
  const text = extractText(payload).trim();
  if (!text) {
    throw new Error("empty_response");
  }
  return text;
}

function buildPayload(mode, model, prompt) {
  if (mode === "chat_completions") {
    return {
      model,
      messages: [{ role: "user", content: prompt }],
      temperature: 0.8,
      top_p: 0.9,
    };
  }
  return {
    model,
    input: prompt,
  };
}

function extractText(payload) {
  if (typeof payload?.output_text === "string") {
    return payload.output_text;
  }

  if (Array.isArray(payload?.output)) {
    const collected = [];
    for (const item of payload.output) {
      if (!Array.isArray(item?.content)) {
        continue;
      }
      for (const block of item.content) {
        if (block?.type === "output_text" && typeof block.text === "string") {
          collected.push(block.text);
        }
      }
    }
    if (collected.length) {
      return collected.join("\n");
    }
  }

  const firstChoice = Array.isArray(payload?.choices) ? payload.choices[0] : null;
  const content = firstChoice?.message?.content;
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((item) => (typeof item?.text === "string" ? item.text : ""))
      .filter(Boolean)
      .join("\n");
  }
  return "";
}

function buildAnswerPrompt(question, lesson) {
  const questionType = classifyStudentQuestion(question);
  const styleHint = nextAnswerStyle();
  const recentOpeners = formatRecentOpeners(answerHistory);
  const title = lesson?.title || "当前课文";
  return [
    `你是一名七年级下册语文课堂助手，正在辅助《${title}》课堂中的“学生问 AI”环节。`,
    "请像教师在课堂上真实接住学生问题那样回答：自然、明确、有现场感，不要像资料卡片，不要模板腔。",
    `本次问题类型：${questionType}`,
    `本次表达风格：${styleHint}`,
    "回答要求：",
    "1. 120到220字，先正面回答学生真正问的点，再顺势回到课文依据。",
    "2. 结合教案 JSON 和问题设计 JSON，不要脱离本节课目标、活动要求和预设问题方向。",
    "3. 不要空泛复述全文，不要把所有问题都答成同一个模板。",
    "4. 如果是象征类问题，先解释关键意象分别代表什么。",
    "5. 如果是态度类问题，先比较作者对不同对象的态度。",
    "6. 如果是写法类问题，先分析对比、衬托怎样突出主体。",
    "7. 如果是主旨类问题，先点明核心品质或核心观点为什么重要。",
    "8. 如果涉及作者经历，要明确写成“结合背景可这样理解”。",
    "9. 结尾要自然回扣本课核心，不要机械重复同一句话。",
    `最近几次回答的开头请尽量避开这些说法：${recentOpeners}`,
    `课堂简要背景：${lessonContext(lesson)}`,
    `教案 JSON：${lessonJsonForPrompt(lesson)}`,
    `问题设计 JSON：${questionDesignJsonForPrompt(lesson)}`,
    `学生问题：${question}`,
  ].join("\n");
}

function buildReflectionPrompt(studentText, lesson) {
  const stance = classifyReflection(studentText);
  const styleHint = nextFeedbackStyle();
  const recentOpeners = formatRecentOpeners(feedbackHistory);
  const title = lesson?.title || "当前课文";
  return [
    `你是一名七年级下册语文课堂助手，正在对学生围绕《${title}》的课堂观点作即时回应。`,
    "请像老师在课堂上真实接话那样点评：先接住学生原话，再推进理解，不要模板腔，不要总重复固定说法。",
    `学生当前立场：${stance}`,
    `本次点评风格：${styleHint}`,
    "点评要求：",
    "1. 80到180字，先接住学生观点，再往深处推进一步。",
    "2. 结合教案 JSON 和问题设计 JSON，围绕本节课的文本依据、表达逻辑和现实思辨推进。",
    "3. 如果学生更强调环境影响，先承认环境影响真实存在，再谈人仍然可以努力作出选择。",
    "4. 如果学生更强调主动坚守，先肯定主动坚守的价值，再提醒这种坚守并不轻松。",
    "5. 如果学生两边都提到，就回应这种辩证看法，并帮助他把重点落到现实选择。",
    "6. 可以适度回扣课文，但不要直接背模板，也不要每次都用同一结构。",
    `教案 JSON：${lessonJsonForPrompt(lesson)}`,
    `问题设计 JSON：${questionDesignJsonForPrompt(lesson)}`,
    `最近几次点评的开头请尽量避开这些说法：${recentOpeners}`,
    `学生观点：${studentText}`,
  ].join("\n");
}

function buildFollowUpPrompt(followUp, response, lesson) {
  return [
    "你是一名七年级下册语文课堂助手。请根据 AI 追问和学生回应，给出 80 到 160 字的课堂式二次回应。",
    "语气要接近课堂即时追评：先接住学生回应，再推进到文本核心或现实选择，不要模板腔。",
    "回应要求：",
    "1. 不要只表扬，要帮助学生把观点说得更清楚。",
    "2. 结合教案 JSON 和问题设计 JSON，回到本节课的核心问题。",
    "3. 语言自然，像老师在课堂上顺势接话。",
    `课文：${lesson?.title || "当前课文"}`,
    `追问：${followUp}`,
    `学生回应：${response}`,
    `教案 JSON：${lessonJsonForPrompt(lesson)}`,
    `问题设计 JSON：${questionDesignJsonForPrompt(lesson)}`,
  ].join("\n");
}

function lessonJsonForPrompt(lesson = {}) {
  return safeJsonStringify({
    id: lesson.id,
    title: lesson.title,
    subtitle: lesson.subtitle,
    goals: lesson.goals,
    keyPoints: lesson.keyPoints,
    difficultPoints: lesson.difficultPoints,
    coreStatement: lesson.coreStatement,
    aiStudentPrompt: lesson.aiStudentPrompt,
    stages: lesson.stages,
    summaryTemplate: lesson.summaryTemplate,
    homeworkTemplate: lesson.homeworkTemplate,
    lessonPlanSource: lesson.lessonPlanSource,
  });
}

function questionDesignJsonForPrompt(lesson = {}) {
  return safeJsonStringify({
    askPanelTitle: lesson.askPanelTitle,
    askPanelDescription: lesson.askPanelDescription,
    questionPrompt: lesson.questionPrompt,
    questionPlaceholder: lesson.questionPlaceholder,
    questionCues: lesson.questionCues,
    flowerCards: lesson.flowerCards,
    thinkingSteps: lesson.thinkingSteps,
    reflectionHints: lesson.reflectionHints,
    presets: lesson.presets,
  });
}

function safeJsonStringify(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "{}";
  }
}

function lessonContext(lesson = {}) {
  return [
    `当前课文：${lesson.title || ""}`,
    `学习目标：${(lesson.goals || []).filter(Boolean).join("；")}`,
    `学习重点：${lesson.keyPoints || ""}`,
    `学习难点：${lesson.difficultPoints || ""}`,
    `核心问题：${lesson.aiStudentPrompt || ""}`,
  ].join("\n");
}

function normalizeEndpoint(endpoint) {
  if (!endpoint) {
    return { endpoint: "", mode: "responses" };
  }

  const cleaned = String(endpoint).trim().replace(/\/+$/, "");
  const url = new URL(cleaned);
  const host = url.hostname.toLowerCase();
  const path = url.pathname.replace(/\/+$/, "");
  const lower = cleaned.toLowerCase();

  if (lower.endsWith("/responses")) {
    return { endpoint: cleaned, mode: "responses" };
  }
  if (lower.endsWith("/chat/completions") || lower.endsWith("/completions")) {
    return { endpoint: cleaned, mode: "chat_completions" };
  }
  if (["", "/", "/v1", "/v1beta", "/v1beta1"].includes(path)) {
    if (host.includes("api.openai.com")) {
      return { endpoint: `${cleaned}/responses`, mode: "responses" };
    }
    return { endpoint: `${cleaned}/chat/completions`, mode: "chat_completions" };
  }
  if (host.includes("api.openai.com")) {
    return { endpoint: cleaned, mode: "responses" };
  }
  return { endpoint: cleaned, mode: "chat_completions" };
}

function classifyStudentQuestion(question) {
  const normalized = String(question || "").replace("？", "?").trim();
  if (containsAny(normalized, ["态度", "看法", "情感", "赞美", "独爱", "众爱"])) {
    return "态度类";
  }
  if (containsAny(normalized, ["衬托", "正衬", "反衬", "写法", "手法", "对比"])) {
    return "写法类";
  }
  if (containsAny(normalized, ["经历", "生平", "背景", "周敦颐", "作者自己"])) {
    return "背景类";
  }
  if (containsAny(normalized, ["出淤泥而不染", "主旨", "中心", "核心", "品质", "高洁", "君子品格"])) {
    return "主旨类";
  }
  if (containsAny(normalized, ["象征", "代表", "分别是什么人", "分别代表", "三种花"])) {
    return "象征类";
  }
  return "综合理解类";
}

function classifyReflection(studentText) {
  const stripped = String(studentText || "").trim();
  if (containsAny(stripped, ["都", "两种", "一方面", "另一方面", "既", "也"])) {
    return "辩证比较";
  }
  if (containsAny(stripped, ["近墨者黑", "环境", "影响", "带偏", "很难不受影响"])) {
    return "更强调环境影响";
  }
  if (containsAny(stripped, ["出淤泥而不染", "坚持", "原则", "底线", "守住自己", "不盲从"])) {
    return "更强调主动坚守";
  }
  return "结合经历表达看法";
}

function buildFollowUp(studentText) {
  const text = String(studentText || "");
  if (containsAny(text, ["两种", "辩证", "既", "也", "一方面", "另一方面", "主动选择"])) {
    return "如果环境会影响人，而人也能作选择，你认为“选择环境”和“守住内心”哪一步更关键？";
  }
  if (containsAny(text, ["环境", "影响", "近墨者黑", "带偏", "很难"])) {
    return "当环境确实会影响人时，一个人可以靠哪些具体做法减少被“染”的可能？";
  }
  if (containsAny(text, ["坚持", "原则", "底线", "独立", "不盲从", "拒绝"])) {
    return "把你的例子再推进一步：这种坚守靠的是一时勇气，还是长期形成的判断力？";
  }
  return "请把你的观点和课文中的一句话连起来，再说明这句话为什么能支持你的看法。";
}

function nextAnswerStyle() {
  const styles = [
    "先给结论，再回到课文细节展开",
    "先抓关键词，再解释作者用意",
    "先比较关键对象，再落到本课核心",
  ];
  const style = styles[answerTurn % styles.length];
  answerTurn += 1;
  return style;
}

function nextFeedbackStyle() {
  const styles = [
    "贴近教师即时回应，语气自然",
    "在肯定之后再推进一层理解",
    "联系现实场景，让学生更容易代入",
  ];
  const style = styles[feedbackTurn % styles.length];
  feedbackTurn += 1;
  return style;
}

function formatRecentOpeners(items) {
  const openers = items.map(extractOpener).filter(Boolean);
  return openers.length ? openers.slice(-3).join("；") : "暂无";
}

function extractOpener(text) {
  const buffer = [];
  for (const char of String(text || "").trim()) {
    if ("。！？!?".includes(char)) {
      break;
    }
    buffer.push(char);
    if (buffer.length >= 24) {
      break;
    }
  }
  return buffer.join("");
}

function remember(items, text) {
  const cleaned = String(text || "").trim();
  if (!cleaned) {
    return;
  }
  items.push(cleaned);
  if (items.length > 4) {
    items.shift();
  }
}

function containsAny(text, keywords) {
  return keywords.some((keyword) => text.includes(keyword));
}
