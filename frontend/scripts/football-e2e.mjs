/** QA-only browser journey against a disposable, verified-content database. */
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE
  || 'C:/Users/pc/AppData/Local/Temp/seenjeem-ui-qa/node_modules/playwright');
const base = process.env.FOOTBALL_QA_URL || 'http://127.0.0.1:5176';
const output = path.resolve('../screenshots/football');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const report = { base, viewport: '1920x1080', journey: [] };
try {
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'إنشاء حساب', exact: true }).click();
  await page.locator('#account-username').fill(`footballqa${Date.now()}`);
  await page.locator('#account-password').fill('QA-only-football-2026!');
  await page.locator('form button[type="submit"]').click();
  await page.waitForSelector('#account-username', { state: 'detached' });
  report.journey.push('Registered disposable QA account through UI');
  const setup = await page.evaluate(async () => {
    const { useGameStore } = await import('/src/store/gameStore.js');
    const store = () => useGameStore.getState();
    window.__footballQaStore = useGameStore;
    await new Promise((resolve, reject) => {
      if (store().categories.status === 'ready' && store().categories.items.length) return resolve();
      const timeout = setTimeout(() => { unsubscribe(); reject(new Error('Catalog did not load')); }, 15000);
      const unsubscribe = useGameStore.subscribe(s => {
        if (s.categories.status === 'ready' && s.categories.items.length) {
          clearTimeout(timeout); unsubscribe(); resolve();
        }
      });
      store().loadCategories();
    });
    store().clearCategorySelection();
    for (const slug of ['football', 'ucl', 'worldcup', 'career', 'clubs', 'arab_ftbl']) {
      const result = store().toggleCategory(slug);
      if (!result.ok) throw new Error(JSON.stringify({ slug, result, categories: store().categories }));
    }
    store().finishCoinToss('team-falcons');
    const result = await store().beginMatch();
    if (!result.ok) throw new Error(JSON.stringify(result));
    for (const power of ['pit', 'trap', 'double', 'noise', 'switch', 'two_answers']) {
      const pick = await store().draftPowerOnline(power);
      if (!pick.ok) throw new Error(JSON.stringify(pick));
    }
    const entered = store().enterBoard();
    if (!entered.ok) throw new Error(JSON.stringify(entered));
    const questions = Object.values(store().content.questions);
    return { questions: questions.length, stage: store().currentStage,
      leaked: questions.some(q => q.answer || q.tolerance),
      visualTypes: [...new Set(questions.map(q => q.visual?.type).filter(Boolean))] };
  });
  assert.equal(setup.stage, 'board');
  assert.equal(setup.leaked, false);
  report.journey.push({ actualServerBoard: setup });
  await page.screenshot({ path: path.join(output, '01-board-tv.png') });

  const selected = await page.evaluate(async () => {
    const { useGameStore } = await import('/src/store/gameStore.js');
    const state = useGameStore.getState();
    const tile = state.content.tiles.find(t => state.content.questions[t.questionId]?.visual?.type === 'career_tree');
    if (!tile) throw new Error('Actual allocated board has no career visual');
    const result = await state.selectTileOnline(tile.id);
    if (!result.ok) throw new Error(JSON.stringify(result));
    const after = useGameStore.getState();
    const q = after.content.questions[after.currentQuestion.questionId];
    return { stage: after.currentStage, questionId: q.id, visualType: q.visual.type, answer: q.answer };
  });
  assert.equal(selected.stage, 'arena');
  assert.ok(!selected.answer);
  await page.locator('figure[dir="rtl"]').waitFor();
  await page.screenshot({ path: path.join(output, '02-career-question-tv.png') });
  await page.getByRole('button', { name: /إظهار الإجابة/ }).click();
  const revealed = await page.waitForFunction(() => {
    const s = window.__footballQaStore.getState();
    return s.currentQuestion?.revealed && s.content.questions[s.currentQuestion.questionId]?.answer;
  });
  const answer = await revealed.jsonValue();
  assert.equal(typeof answer, 'string');
  assert.ok(answer.length > 0);
  await page.screenshot({ path: path.join(output, '03-career-answer-tv.png') });
  report.journey.push('Opened actual allocated career question; answer absent until UI reveal; reveal hydrated answer');

  await page.reload({ waitUntil: 'networkidle' });
  const resume = page.getByRole('button', { name: /استئناف المباراة/ });
  if (await resume.isVisible()) await resume.click();
  await page.locator('figure[dir="rtl"]').waitFor();
  const afterReload = await page.evaluate(async () => {
    const { useGameStore } = await import('/src/store/gameStore.js');
    const s = useGameStore.getState();
    return { revealed: s.currentQuestion.revealed,
      answer: s.content.questions[s.currentQuestion.questionId].answer };
  });
  assert.equal(afterReload.revealed, true);
  assert.equal(afterReload.answer, answer);
  report.journey.push('Reload preserved revealed visual and answer');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(output, '04-career-mobile.png'), fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  assert.equal(overflow, false);
  assert.deepEqual(errors, []);
  report.journey.push('390px RTL layout has no horizontal overflow or page errors');
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  report.error = error.stack;
  await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
  throw error;
} finally {
  report.pageErrors = errors;
  await writeFile(path.join(output, 'browser-results.json'), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}
