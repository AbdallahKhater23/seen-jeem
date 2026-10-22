import { describe, expect, it } from 'vitest';
import {
  TIMER_PHASES,
  advanceTimer,
  createTimer,
  formatClock,
  getElapsedMs,
  pauseTimer,
  recoverTimer,
  resetPrimaryTimer,
  startTimer,
  toggleTimer,
} from './timer.js';

describe('open stopwatch timer', () => {
  it('starts at zero and runs forward once started', () => {
    const timer = createTimer();
    expect(timer.phase).toBe(TIMER_PHASES.PRIMARY);
    expect(timer.running).toBe(false);
    expect(getElapsedMs(timer, 1000)).toBe(0);

    const started = startTimer(timer, 1000);
    expect(started.running).toBe(true);
    expect(getElapsedMs(started, 11000)).toBe(10000);
    expect(getElapsedMs(started, 91000)).toBe(90000);
  });

  it('does not stop when the old 60-second mark passes', () => {
    const started = startTimer(createTimer(), 1000);
    const { timer, events } = advanceTimer(started, 500000);
    expect(timer.phase).toBe(TIMER_PHASES.PRIMARY);
    expect(timer.running).toBe(true);
    expect(events).toEqual([]);
    expect(getElapsedMs(timer, 500000)).toBe(499000);
  });

  it('pause/resume preserves the exact elapsed time', () => {
    const started = startTimer(createTimer(), 1000);
    const paused = pauseTimer(started, 11000);
    expect(paused.running).toBe(false);
    expect(paused.elapsedMs).toBe(10000);
    expect(paused.startedAt).toBeNull();
    expect(getElapsedMs(paused, 999999)).toBe(10000);

    const resumed = toggleTimer(paused, 20000);
    expect(resumed.running).toBe(true);
    expect(getElapsedMs(resumed, 25000)).toBe(15000);
  });

  it('toggles without creating a time limit', () => {
    const started = startTimer(createTimer(), 0);
    expect(getElapsedMs(started, 60001)).toBe(60001);
    const paused = toggleTimer(started, 60001);
    expect(paused.phase).toBe(TIMER_PHASES.PRIMARY);
    expect(paused.elapsedMs).toBe(60001);
  });

  it('recovery keeps the open clock running with no new grant or cutoff', () => {
    const started = startTimer(createTimer(), 1000);
    const recovered = recoverTimer(started, 500000);
    expect(recovered.timer.phase).toBe(TIMER_PHASES.PRIMARY);
    expect(recovered.timer.running).toBe(true);
    expect(recovered.events).toEqual([]);
    expect(getElapsedMs(recovered.timer, 500000)).toBe(499000);
  });

  it('switch field resets the stopwatch and starts it again', () => {
    const timer = { ...createTimer(), running: true, elapsedMs: 40000, startedAt: 1000 };
    const reset = resetPrimaryTimer(timer, 50000);
    expect(reset.phase).toBe(TIMER_PHASES.PRIMARY);
    expect(reset.running).toBe(true);
    expect(reset.elapsedMs).toBe(0);
    expect(reset.startedAt).toBe(50000);
    expect(getElapsedMs(reset, 53000)).toBe(3000);
  });

  it('formats elapsed time as minutes and seconds', () => {
    expect(formatClock(0)).toBe('0:00');
    expect(formatClock(61000)).toBe('1:01');
    expect(formatClock(600000)).toBe('10:00');
  });
});
