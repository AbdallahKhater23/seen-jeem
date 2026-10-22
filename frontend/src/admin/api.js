const API_BASE_URL = (import.meta.env?.VITE_API_URL || '/api/v1').replace(/\/$/, '');

export class AdminApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.name = 'AdminApiError';
    this.status = status;
    this.code = code;
  }
}

async function adminRequest(path, token, { signal } = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: 'application/json',
      'X-Admin-Token': token,
    },
    signal,
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const error = payload?.error ?? {};
    throw new AdminApiError(
      error.message || `فشل طلب الإدارة (${response.status}).`,
      response.status,
      error.code || `HTTP_${response.status}`,
    );
  }
  return payload;
}

export function fetchQuestionBank(token, options) {
  return adminRequest('/admin/question-bank', token, options);
}

export function fetchSeedHistory(token, options) {
  return adminRequest('/admin/seed-history?limit=20', token, options);
}

export function fetchMatches(token, options) {
  return adminRequest('/admin/matches?limit=50', token, options);
}

export function fetchMatchEvents(token, matchCode, options) {
  return adminRequest(
    `/admin/matches/${encodeURIComponent(matchCode)}/events?limit=100`,
    token,
    options,
  );
}
