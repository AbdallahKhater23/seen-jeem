/**
 * أداة تطوير اختيارية لالتقاط صور الواجهة من متصفح Chrome محلي.
 * التشغيل: node scripts/capture-screenshots.mjs
 * ليست جزءًا من حزمة الإنتاج ولا تعتمد على أي خدمة خارجية.
 */
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { setTimeout as sleep } from 'node:timers/promises';
import path from 'node:path';

const CHROME =
  process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9333;
const APP = 'http://127.0.0.1:5173/';
const outputDir = path.resolve('docs/screenshots');
const profileDir = path.resolve('../.tmp-chrome-trivia');

await mkdir(outputDir, { recursive: true });
const chrome = spawn(
  CHROME,
  [
    '--headless=new',
    '--disable-gpu',
    '--hide-scrollbars',
    '--no-first-run',
    '--no-default-browser-check',
    '--remote-allow-origins=*',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profileDir}`,
    '--window-size=1920,1080',
    APP,
  ],
  { stdio: 'ignore' },
);

async function waitForEndpoint() {
  for (let i = 0; i < 60; i += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      if (response.ok) {
        const pages = await response.json();
        const page = pages.find((item) => item.type === 'page' && item.url.includes('127.0.0.1'));
        if (page) return page;
      }
    } catch {
      // لسه يشتغل.
    }
    await sleep(250);
  }
  throw new Error('Chrome DevTools لم يجهز.');
}

const page = await waitForEndpoint();
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = reject;
});

let nextId = 1;
const pending = new Map();
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (!message.id) return;
  const entry = pending.get(message.id);
  if (!entry) return;
  pending.delete(message.id);
  if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
  else entry.resolve(message.result);
};

function send(method, params = {}) {
  const id = nextId;
  nextId += 1;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

async function evaluate(expression) {
  const result = await send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || 'فشل تنفيذ السكربت');
  }
  return result.result?.value;
}

async function screenshot(name) {
  const result = await send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false,
  });
  await writeFile(path.join(outputDir, name), Buffer.from(result.data, 'base64'));
  console.log(`captured ${name}`);
}

async function reloadAndSettle(ms = 1300, resume = true) {
  await send('Page.reload', { ignoreCache: true });
  await sleep(ms);
  if (resume) {
    const clicked = await evaluate(`(() => {
      const btn = [...document.querySelectorAll('button')]
        .find((item) => item.innerText.includes('استئناف المباراة'));
      if (!btn) return false;
      btn.click();
      return true;
    })()`);
    if (clicked) await sleep(600);
  }
}

await send('Page.enable');
await send('Runtime.enable');
await sleep(2200);

// نبدأ من صالة نظيفة حتى تبقى اللقطات قابلة لإعادة الإنتاج.
await evaluate(`(() => {
  localStorage.removeItem('ya-hala-trivia:match:v1');
  return true;
})()`);
await send('Page.reload', { ignoreCache: true });
await sleep(1600);

await screenshot('lobby.png');

await evaluate(`(async () => {
  const { useGameStore } = await import('/src/store/gameStore.js');
  const s = useGameStore.getState();
  if (!s.coinToss.completed) s.finishCoinToss('team-falcons');
  if (useGameStore.getState().currentStage === 'lobby') s.startDraft();
  const ids = ['pit','trap','rest','double','noise','switch'];
  for (const id of ids) {
    if (useGameStore.getState().draft.picks.length < 6) s.draftPower(id);
  }
  s.enterBoard();
  return useGameStore.getState().currentStage;
})()`);
await reloadAndSettle();
await screenshot('board.png');

await evaluate(`(async () => {
  const { useGameStore } = await import('/src/store/gameStore.js');
  const s = useGameStore.getState();
  s.selectTile('spot-400-1');
  return useGameStore.getState().currentStage;
})()`);
await reloadAndSettle();
await screenshot('arena-spot-diff.png');

await evaluate(`(async () => {
  const { useGameStore } = await import('/src/store/gameStore.js');
  const s = useGameStore.getState();
  s.abandonQuestion();
  s.selectTile('flags-200-1');
  s.revealAnswer();
  return useGameStore.getState().currentStage;
})()`);
await reloadAndSettle();
await screenshot('arena-flag-reveal.png');

await evaluate(`(async () => {
  const { useGameStore } = await import('/src/store/gameStore.js');
  const { TILES } = await import('/src/data/mockData.js');
  const store = useGameStore.getState();
  store.abandonQuestion();
  for (const tile of TILES) {
    const state = useGameStore.getState();
    if (state.currentStage !== 'board') break;
    if (state.tileResults[tile.id]?.played) continue;
    state.selectTile(tile.id);
    state.revealAnswer();
    useGameStore.getState().resolveNobody();
  }
  return useGameStore.getState().currentStage;
})()`);
await reloadAndSettle(1500, false);
await screenshot('podium-tie.png');

socket.close();
chrome.kill();
