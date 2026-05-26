async function postPrep(path, token, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, token }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

export function validatePrepToken(token) {
  return postPrep("/api/prep/validate-token", token);
}

export function loadPrepTemplates(token) {
  return postPrep("/api/prep/templates", token);
}

export function generatePrepLesson(token, payload) {
  return postPrep("/api/prep/generate", token, payload);
}

export function parsePrepMarkdown(token, payload) {
  return postPrep("/api/prep/parse", token, payload);
}

export function savePrepLesson(token, payload) {
  return postPrep("/api/prep/save", token, payload);
}
