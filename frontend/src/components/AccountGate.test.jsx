import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ me: vi.fn(), login: vi.fn(), register: vi.fn(), logout: vi.fn(), history: vi.fn(), resetSavedMatch: vi.fn(), clearRecoveryNotice: vi.fn() }));
vi.mock('../api/accounts.js', () => ({ accounts: mocks }));
vi.mock('../store/gameStore.js', () => ({ useGameStore: { getState: () => ({
  resetSavedMatch: mocks.resetSavedMatch, clearRecoveryNotice: mocks.clearRecoveryNotice,
}) } }));

import AccountGate from './AccountGate.jsx';

let container;
let root;
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  vi.resetAllMocks();
  localStorage.clear();
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

it('keeps the game behind login and restores a server session', async () => {
  mocks.me.mockResolvedValue({ user: { id: 1, username: 'player' }, questions_seen: 7 });
  await act(async () => root.render(<AccountGate><p>game-content</p></AccountGate>));
  expect(container.textContent).toContain('game-content');
  expect(container.textContent).toContain('player');
  expect(container.textContent).toContain('7');
});

it('shows login for signed-out users and signs up without saving a password', async () => {
  mocks.me.mockRejectedValue(Object.assign(new Error('login'), { status: 401 }));
  mocks.register.mockResolvedValue({ user: { id: 2, username: 'new-player' }, questions_seen: 0 });
  await act(async () => root.render(<AccountGate><p>game-content</p></AccountGate>));
  expect(container.textContent).not.toContain('game-content');
  await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'إنشاء حساب').click());
  const input = (label, value) => {
    const el = container.querySelector(`input[name="${label}"]`);
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  };
  await act(async () => { input('username', 'new-player'); input('password', 'long password 123'); });
  await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  expect(mocks.register).toHaveBeenCalledWith('new-player', 'long password 123');
  expect(container.textContent).toContain('game-content');
  expect(JSON.stringify([...localStorage.store.values()])).not.toContain('long password 123');
});

it('does not unlock game when the server cannot verify the account', async () => {
  mocks.me.mockRejectedValue(new Error('offline'));
  await act(async () => root.render(<AccountGate><p>game-content</p></AccountGate>));
  expect(container.textContent).not.toContain('game-content');
  expect(container.querySelector('[role="alert"]')).not.toBeNull();
});

it('logout clears account UI and hides the game but preserves server history', async () => {
  mocks.me.mockResolvedValue({ user: { id: 1, username: 'player' }, questions_seen: 4 });
  mocks.logout.mockResolvedValue({ ok: true });
  await act(async () => root.render(<AccountGate><p>game-content</p></AccountGate>));
  await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'تسجيل الخروج').click());
  expect(mocks.logout).toHaveBeenCalledOnce();
  expect(container.textContent).not.toContain('game-content');
  expect(container.querySelector('input[name="password"]')).not.toBeNull();
});

it('preserves the same account recovery and resets a different account recovery', async () => {
  localStorage.setItem('seenjeem:account-owner:v1', '1');
  mocks.me.mockResolvedValue({ user: { id: 1, username: 'player' }, questions_seen: 4 });
  await act(async () => root.render(<AccountGate><p>game-content</p></AccountGate>));
  expect(mocks.resetSavedMatch).not.toHaveBeenCalled();
  mocks.me.mockResolvedValue({ user: { id: 2, username: 'other-player' }, questions_seen: 0 });
  await act(async () => window.dispatchEvent(new Event('focus')));
  expect(mocks.resetSavedMatch).toHaveBeenCalledOnce();
  expect(container.textContent).toContain('other-player');
  expect(localStorage.getItem('seenjeem:account-owner:v1')).toBe('2');
});

it('loads only the authenticated question history and updates the count', async () => {
  mocks.me.mockResolvedValue({ user: { id: 1, username: 'player' }, questions_seen: 0 });
  mocks.history.mockResolvedValue({ total: 1, items: [{ question_id: 8, question_text: 'سؤال سابق', played_at: '2026-10-20T12:00:00Z', category_name: 'أعلام', difficulty: 200 }] });
  await act(async () => root.render(<AccountGate><p>game-content</p></AccountGate>));
  await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'سجل أسئلتي').click());
  expect(mocks.history).toHaveBeenCalledWith(0);
  expect(container.textContent).toContain('سؤال سابق');
  expect(container.textContent).toContain('1 سؤال محفوظ');
});

it('keeps the game locked after an incorrect password', async () => {
  mocks.me.mockRejectedValue(Object.assign(new Error('login'), { status: 401 }));
  mocks.login.mockRejectedValue(new Error('كلمة المرور غير صحيحة'));
  await act(async () => root.render(<AccountGate><p>game-content</p></AccountGate>));
  await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  expect(container.textContent).not.toContain('game-content');
  expect(container.querySelector('[role="alert"]').textContent).toContain('كلمة المرور غير صحيحة');
});
