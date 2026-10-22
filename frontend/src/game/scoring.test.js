import { describe, expect, it } from 'vitest';
import { OUTCOMES, SCORING_REASONS, computeScoreDeltas } from './scoring.js';

const A = 'team-a';
const B = 'team-b';

function score(outcome, powers = [], basePoints = 400) {
  return computeScoreDeltas({
    basePoints,
    outcome,
    activeTeamId: A,
    defendingTeamId: B,
    activePowerIds: powers,
  });
}

describe('computeScoreDeltas', () => {
  it('awards the base value to the active team on a correct answer', () => {
    const result = score(OUTCOMES.ACTIVE);
    expect(result.deltas).toEqual({ [A]: 400, [B]: 0 });
    expect(result.ledger).toHaveLength(1);
  });

  it('awards the base value to the defending team on a legal steal', () => {
    const result = score(OUTCOMES.DEFENDING);
    expect(result.deltas).toEqual({ [A]: 0, [B]: 400 });
  });

  it('awards nothing when nobody scores', () => {
    const result = score(OUTCOMES.NOBODY);
    expect(result.deltas).toEqual({ [A]: 0, [B]: 0 });
    expect(result.ledger).toHaveLength(0);
  });

  it('applies the pit deduction only when the active team wins', () => {
    const win = score(OUTCOMES.ACTIVE, ['pit']);
    expect(win.deltas).toEqual({ [A]: 400, [B]: -400 });
    const steal = score(OUTCOMES.DEFENDING, ['pit']);
    expect(steal.deltas).toEqual({ [A]: 0, [B]: 400 });
    const nobody = score(OUTCOMES.NOBODY, ['pit']);
    expect(nobody.deltas).toEqual({ [A]: 0, [B]: 0 });
  });

  it('combines pit with double: 2x award and one base deduction', () => {
    const result = score(OUTCOMES.ACTIVE, ['pit', 'double']);
    expect(result.deltas).toEqual({ [A]: 800, [B]: -400 });
    expect(result.ledger.map((entry) => entry.reason)).toEqual([
      SCORING_REASONS.DOUBLE_WIN,
      SCORING_REASONS.PIT_DEDUCTION,
    ]);
  });

  it('applies trap on a steal: half the base value (rounded down)', () => {
    const result = score(OUTCOMES.DEFENDING, ['trap'], 600);
    expect(result.deltas).toEqual({ [A]: -300, [B]: 600 });
  });

  it('applies trap when nobody scores', () => {
    const result = score(OUTCOMES.NOBODY, ['trap'], 200);
    expect(result.deltas).toEqual({ [A]: -100, [B]: 0 });
  });

  it('applies double loss and trap together deterministically', () => {
    const result = score(OUTCOMES.DEFENDING, ['double', 'trap'], 600);
    expect(result.deltas).toEqual({ [A]: -900, [B]: 600 });
    expect(result.ledger).toHaveLength(3);
  });

  it('deducts a full base value on a double loss when nobody scores', () => {
    const result = score(OUTCOMES.NOBODY, ['double'], 200);
    expect(result.deltas).toEqual({ [A]: -200, [B]: 0 });
  });

  it('ignores non-scoring powers', () => {
    const result = score(OUTCOMES.ACTIVE, ['steal', 'noise', 'two_answers', 'switch']);
    expect(result.deltas).toEqual({ [A]: 400, [B]: 0 });
  });

  it('rejects invalid input', () => {
    expect(() => score('weird')).toThrow();
    expect(() =>
      computeScoreDeltas({
        basePoints: 0,
        outcome: OUTCOMES.ACTIVE,
        activeTeamId: A,
        defendingTeamId: B,
      }),
    ).toThrow();
    expect(() =>
      computeScoreDeltas({
        basePoints: 200,
        outcome: OUTCOMES.ACTIVE,
        activeTeamId: A,
        defendingTeamId: A,
      }),
    ).toThrow();
  });
});
