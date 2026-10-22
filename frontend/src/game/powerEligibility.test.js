import { describe, expect, it } from 'vitest';
import { BACKUPS } from '../data/mockData.js';
import { getPowerEligibility } from './powerEligibility.js';
import { createTimer } from './timer.js';

const A = 'team-a';
const B = 'team-b';
const now = 100000;
const ALL_POWERS = ['pit', 'trap', 'steal', 'two_answers', 'noise', 'double', 'switch'];

function setup(overrides = {}) {
  const question = {
    activeTeamId: A,
    revealed: false,
    sessionStartedAt: now - 1000,
    categoryId: 'flags',
    points: 400,
    usedBackupIds: [],
    wrongGuesses: 0,
    noiseUntil: null,
    activePowers: [],
    ...overrides.question,
  };
  const timer = { ...createTimer(), ...overrides.timer };
  return {
    question,
    timer,
    draftedPowerIds: overrides.draftedPowerIds ?? ALL_POWERS,
    usedPowerIds: overrides.usedPowerIds ?? [],
    now: overrides.now ?? now,
  };
}

function eligible(powerId, teamId, overrides = {}) {
  const context = setup(overrides);
  return getPowerEligibility({ powerId, teamId, ...context });
}

describe('power eligibility', () => {
  it('rejects unknown powers, missing questions, and undrafted powers', () => {
    expect(eligible('nope', A).eligible).toBe(false);
    expect(
      getPowerEligibility({
        powerId: 'pit',
        teamId: A,
        question: null,
        timer: createTimer(),
        draftedPowerIds: ['pit'],
        usedPowerIds: [],
        now,
      }).eligible,
    ).toBe(false);
    expect(eligible('pit', A, { draftedPowerIds: ['trap'] }).eligible).toBe(false);
  });

  it('rejects used powers and anything after reveal', () => {
    expect(eligible('pit', A, { usedPowerIds: ['pit'] }).eligible).toBe(false);
    expect(eligible('pit', A, { question: { revealed: true } }).eligible).toBe(false);
    expect(eligible('steal', B, { question: { revealed: true } }).eligible).toBe(false);
  });

  it('enforces active vs defending ownership', () => {
    expect(eligible('pit', B).eligible).toBe(false);
    expect(eligible('trap', A).eligible).toBe(false);
    expect(eligible('trap', B).eligible).toBe(true);
    expect(eligible('steal', A).eligible).toBe(false);
    expect(eligible('steal', B).eligible).toBe(true);
    expect(eligible('two_answers', A).eligible).toBe(true);
    expect(eligible('noise', B).eligible).toBe(true);
    expect(eligible('double', A).eligible).toBe(true);
    expect(eligible('switch', A).eligible).toBe(true);
  });

  it('keeps offensive and defensive powers available regardless of elapsed time', () => {
    const late = now + 10 * 60 * 1000;
    expect(eligible('pit', A, { now: late }).eligible).toBe(true);
    expect(eligible('trap', B, { now: late }).eligible).toBe(true);
    expect(eligible('steal', B, { now: late }).eligible).toBe(true);
    expect(eligible('two_answers', A, { now: late }).eligible).toBe(true);
  });

  it('blocks noise while an existing noise effect is running', () => {
    expect(eligible('noise', B, { question: { noiseUntil: now + 5000 } }).eligible).toBe(false);
    expect(eligible('noise', B, { question: { noiseUntil: now - 1 } }).eligible).toBe(true);
  });

  it('enforces the 15-second switch-field window', () => {
    expect(eligible('switch', A, { now: now + 14000 }).eligible).toBe(true);
    expect(eligible('switch', A, { now: now + 15001 }).eligible).toBe(false);
  });

  it('blocks switch field when every compatible backup is used', () => {
    const used = BACKUPS.map((backup) => backup.id);
    expect(eligible('switch', A, { question: { usedBackupIds: used } }).eligible).toBe(false);
  });

  it('blocks a third two-answer attempt', () => {
    expect(eligible('two_answers', A, { question: { wrongGuesses: 2 } }).eligible).toBe(false);
  });
});
