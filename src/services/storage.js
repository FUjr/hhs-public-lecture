const SETTINGS_KEY = "hhs-public-lecture-v2-settings";
const LESSON_KEY = "hhs-public-lecture-v2-lesson-id";

export function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) {
      return defaultSettings();
    }
    return { ...defaultSettings(), ...JSON.parse(raw) };
  } catch {
    return defaultSettings();
  }
}

export function saveSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ...defaultSettings(), ...settings }));
}

export function defaultSettings() {
  return {
    endpoint: "",
    apiKey: "",
    model: "",
    preferRemote: false,
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
