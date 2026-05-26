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
