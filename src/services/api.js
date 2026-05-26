export async function callApi(path, payload = {}, signal) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

export async function loadLessonIndex() {
  const response = await fetch("/generated-lessons/index.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Unable to load lesson index: HTTP ${response.status}`);
  }
  return response.json();
}

export async function loadLesson(id) {
  const response = await fetch(`/generated-lessons/${encodeURIComponent(id)}.json`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Unable to load lesson: HTTP ${response.status}`);
  }
  return response.json();
}
