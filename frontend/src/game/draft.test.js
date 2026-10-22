import { describe, expect, it } from 'vitest';
import { POWERS } from '../data/mockData.js';
import {
  buildDraftOrder,
  countTeamPicks,
  getCurrentDraftTeam,
  validateDraft,
} from './draft.js';

const A = 'team-a';
const B = 'team-b';
const POWER_IDS = POWERS.map((power) => power.id);

function squad(picks) {
  return picks.map((powerId, index) => ({
    teamId: buildDraftOrder(A, B)[index],
    powerId,
  }));
}

describe('snake draft', () => {
  it('uses exactly A → B → B → A → A → B', () => {
    expect(buildDraftOrder(A, B)).toEqual([A, B, B, A, A, B]);
    expect(buildDraftOrder(B, A)).toEqual([B, A, A, B, B, A]);
  });

  it('rejects identical team IDs', () => {
    expect(() => buildDraftOrder(A, A)).toThrow();
  });

  it('returns the correct current team for each pick', () => {
    const order = buildDraftOrder(A, B);
    expect(getCurrentDraftTeam(order, [])).toBe(A);
    expect(getCurrentDraftTeam(order, [{}, {}])).toBe(B);
    expect(getCurrentDraftTeam(order, [{}, {}, {}, {}, {}, {}])).toBeNull();
  });

  it('produces exactly three powers per team', () => {
    const picks = squad(POWER_IDS.slice(0, 6));
    const validation = validateDraft(picks, POWER_IDS, [A, B]);
    expect(validation.ok).toBe(true);
    expect(countTeamPicks(picks, A)).toBe(3);
    expect(countTeamPicks(picks, B)).toBe(3);
  });

  it('allows both teams to draft the same power', () => {
    const picks = squad(['pit', 'pit', 'trap', 'double', 'noise', 'switch']);
    const validation = validateDraft(picks, POWER_IDS, [A, B]);
    expect(validation.ok).toBe(true);
    expect(picks.filter((pick) => pick.powerId === 'pit')).toHaveLength(2);
    expect(picks.filter((pick) => pick.powerId === 'pit').map((pick) => pick.teamId)).toEqual([
      A,
      B,
    ]);
  });

  it('rejects duplicate powers within one team, incomplete picks, and wrong team counts', () => {
    const duplicate = squad(['pit', 'trap', 'steal', 'pit', 'noise', 'switch']);
    expect(validateDraft(duplicate, POWER_IDS, [A, B]).ok).toBe(false);

    const incomplete = squad(POWER_IDS.slice(0, 5));
    expect(validateDraft(incomplete, POWER_IDS, [A, B]).ok).toBe(false);

    const skewed = [
      { teamId: A, powerId: 'pit' },
      { teamId: A, powerId: 'trap' },
      { teamId: B, powerId: 'steal' },
      { teamId: A, powerId: 'double' },
      { teamId: A, powerId: 'noise' },
      { teamId: B, powerId: 'switch' },
    ];
    expect(validateDraft(skewed, POWER_IDS, [A, B]).ok).toBe(false);
  });
});
