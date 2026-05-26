const SETTINGS_KEY = "hhs-public-lecture-v2-settings";
const LESSON_KEY = "hhs-public-lecture-v2-lesson-id";
const PREP_TOKEN_KEY = "hhs-public-lecture-v2-prep-token";
const AI_CONFIG_PARAM = "aiConfig";

export function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) {
      return defaultSettings();
    }
    return normalizeSettings(JSON.parse(raw));
  } catch {
    return defaultSettings();
  }
}

export function saveSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ...defaultSettings(), ...settings }));
}

export function buildSettingsImportUrl(settings, baseUrl = window.location.href) {
  const url = new URL(baseUrl);
  url.searchParams.set(AI_CONFIG_PARAM, encodeSettings(settings));
  return url.toString();
}

export function importSettingsFromUrl(urlValue = window.location.href) {
  const url = new URL(urlValue);
  const encoded = url.searchParams.get(AI_CONFIG_PARAM);
  if (!encoded) {
    return { imported: false, settings: loadSettings(), error: "" };
  }

  try {
    const settings = decodeSettings(encoded);
    saveSettings(settings);
    url.searchParams.delete(AI_CONFIG_PARAM);
    window.history.replaceState(window.history.state, "", url.toString());
    return { imported: true, settings, error: "" };
  } catch {
    return { imported: false, settings: loadSettings(), error: "AI 配置链接无效" };
  }
}

export function defaultSettings() {
  return {
    endpoint: "https://api.siliconflow.cn/v1/chat/completions",
    apiKey: "",
    model: "deepseek-ai/DeepSeek-V4-Flash",
    aiMode: "local",
  };
}

export function loadLessonId() {
  return localStorage.getItem(LESSON_KEY) || "";
}

export function saveLessonId(id) {
  if (id) {
    localStorage.setItem(LESSON_KEY, id);
  }
}

export function loadPrepToken() {
  return localStorage.getItem(PREP_TOKEN_KEY) || "";
}

export function savePrepToken(token) {
  const cleaned = String(token || "").trim();
  if (cleaned) {
    localStorage.setItem(PREP_TOKEN_KEY, cleaned);
  } else {
    localStorage.removeItem(PREP_TOKEN_KEY);
  }
}

function encodeSettings(settings) {
  const payload = JSON.stringify({
    version: 1,
    settings: { ...defaultSettings(), ...settings },
  });
  return base64Encode(payload);
}

function decodeSettings(encoded) {
  const normalized = encoded.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
  const payload = JSON.parse(base64Decode(padded));
  const source = payload && typeof payload === "object" && payload.settings ? payload.settings : payload;
  return normalizeSettings(source);
}

function normalizeSettings(source = {}) {
  const defaults = defaultSettings();
  const legacyMode = source.preferRemote === true ? "llm" : "local";
  const aiMode = source.aiMode === "llm" || source.aiMode === "local" ? source.aiMode : legacyMode;
  return {
    ...defaults,
    endpoint: typeof source.endpoint === "string" && source.endpoint ? source.endpoint : defaults.endpoint,
    apiKey: typeof source.apiKey === "string" ? source.apiKey : "",
    model: typeof source.model === "string" && source.model ? source.model : defaults.model,
    aiMode,
  };
}

function base64Encode(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}

function base64Decode(encoded) {
  const binary = window.atob(encoded);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}
