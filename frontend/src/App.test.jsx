import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { createInitialGameState } from './game/state.js';
import { useGameStore } from './store/gameStore.js';
import App from './App.jsx';

vi.mock('./views/LobbyView.jsx', () => ({ default: () => <p>setup screen</p> }));
vi.mock('./views/DraftView.jsx', () => ({ default: () => <p>power screen</p> }));
vi.mock('./views/BoardView.jsx', () => ({ default: () => <p>board screen</p> }));
vi.mock('./views/ArenaView.jsx', () => ({ default: () => <p>question screen</p> }));
vi.mock('./views/PodiumView.jsx', () => ({ default: () => <p>results screen</p> }));
vi.mock('./utils/soundEngine.js', () => ({ default: { setMuted: vi.fn(), unlock: vi.fn(), turn: vi.fn() } }));

let root;
let container;
afterEach(async () => {
  if (root) await act(async () => root.unmount());
  container?.remove();
  vi.unstubAllGlobals();
});

it('keeps revisited screens mounted after repeated question-to-board transitions', async () => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  vi.stubGlobal('matchMedia', () => ({ matches: true, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
  useGameStore.setState(createInitialGameState());
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => root.render(<App />));
  expect(container.textContent).toContain('setup screen');
  for (const [stage, label] of [
    ['draft', 'power screen'], ['board', 'board screen'], ['arena', 'question screen'],
    ['board', 'board screen'], ['arena', 'question screen'], ['board', 'board screen'],
    ['podium', 'results screen'], ['lobby', 'setup screen'],
  ]) {
    await act(async () => useGameStore.setState({ currentStage: stage }));
    expect(container.textContent).toContain(label);
  }
});
