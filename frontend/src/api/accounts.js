import { API_BASE_URL } from './server.js';

async function request(path, body) {
  const response = await fetch(`${API_BASE_URL}/auth/${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'X-Requested-With': 'SeenJeem',
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw Object.assign(new Error(payload.error?.message || 'تعذّر الاتصال بالسيرفر.'), {
      status: response.status, code: payload.error?.code,
    });
  }
  return payload;
}

export const accounts = {
  me: () => request('me'),
  register: (username, password) => request('register', { username, password }),
  login: (username, password) => request('login', { username, password }),
  logout: () => request('logout', {}),
  history: (offset = 0) => request(`history?limit=20&offset=${offset}`),
};
