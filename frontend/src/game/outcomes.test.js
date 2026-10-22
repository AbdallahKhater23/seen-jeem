import { describe, expect, it } from 'vitest';
import { getOutcomeAvailability, outcomeForTeam } from './outcomes.js';
import { OUTCOMES } from './scoring.js';

describe('outcome availability', () => {
  it('blocks every result before reveal', () => {
    const availability = getOutcomeAvailability({ question: { revealed: false } });
    expect(availability[OUTCOMES.ACTIVE].available).toBe(false);
    expect(availability[OUTCOMES.DEFENDING].available).toBe(false);
    expect(availability[OUTCOMES.NOBODY].available).toBe(false);
  });

  it('allows both teams and nobody after reveal with no separate steal window', () => {
    const availability = getOutcomeAvailability({ question: { revealed: true } });
    expect(availability[OUTCOMES.ACTIVE].available).toBe(true);
    expect(availability[OUTCOMES.DEFENDING].available).toBe(true);
    expect(availability[OUTCOMES.NOBODY].available).toBe(true);
  });

  it('maps the active team to a normal win and the other team to a steal', () => {
    expect(outcomeForTeam('a', 'a')).toBe(OUTCOMES.ACTIVE);
    expect(outcomeForTeam('b', 'a')).toBe(OUTCOMES.DEFENDING);
  });
});
