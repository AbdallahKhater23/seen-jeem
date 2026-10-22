import { PRIMARY_SECONDS } from '../data/mockData.js';

/**
 * المؤقت ساعة مفتوحة: يبدأ تلقائيًا بمجرد فتح السؤال، يعدّ للأمام، ولا يوجد
 * سقف زمني ولا انتقال تلقائي لجولة سرقة. الإيقاف المؤقت خيار للمقدم فقط،
 * والاستئناف يكمل من نفس اللحظة.
 */
export const TIMER_PHASES = Object.freeze({
  PRIMARY: 'primary',
  DONE: 'done',
});

/** نافذة عرض واحدة للعقارب (دورة دقيقة) — ليست حدًا للسؤال. */
export const PRIMARY_MS = PRIMARY_SECONDS * 1000;

export function createTimer() {
  return {
    phase: TIMER_PHASES.PRIMARY,
    running: false,
    elapsedMs: 0,
    startedAt: null,
  };
}

export function startTimer(timer, now = Date.now()) {
  if (!timer || timer.running) return timer;
  return { ...timer, phase: TIMER_PHASES.PRIMARY, running: true, startedAt: now };
}

export function getElapsedMs(timer, now = Date.now()) {
  if (!timer) return 0;
  const base = Math.max(0, Number.isFinite(timer.elapsedMs) ? timer.elapsedMs : 0);
  if (!timer.running) return base;
  if (!Number.isFinite(timer.startedAt)) return base;
  return base + Math.max(0, now - timer.startedAt);
}

export function toggleTimer(timer, now = Date.now()) {
  if (!timer) return timer;
  if (timer.running) {
    return {
      ...timer,
      running: false,
      elapsedMs: getElapsedMs(timer, now),
      startedAt: null,
    };
  }
  return { ...timer, phase: TIMER_PHASES.PRIMARY, running: true, startedAt: now };
}

export function pauseTimer(timer, now = Date.now()) {
  if (!timer?.running) return timer;
  return {
    ...timer,
    running: false,
    elapsedMs: getElapsedMs(timer, now),
    startedAt: null,
  };
}

/** لا يوجد انتهاء تلقائي؛ النقرات لا تغيّر طور السؤال. */
export function advanceTimer(timer) {
  return { timer, events: [] };
}

export function recoverTimer(timer) {
  return { timer, events: [] };
}

/** تبديل الميدان يصفّر العدّاد ويعيده للعمل فورًا. */
export function resetPrimaryTimer(timer, now = Date.now()) {
  return {
    phase: TIMER_PHASES.PRIMARY,
    running: true,
    elapsedMs: 0,
    startedAt: now,
  };
}

export function formatClock(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}
