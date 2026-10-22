import { describe, expect, it } from 'vitest';
import { getPodiumResult } from './podium.js';

describe('podium result', () => {
  it('declares no winner on a tie', () => {
    const result = getPodiumResult([
      { id: 'a', name: 'A', score: 1200 },
      { id: 'b', name: 'B', score: 1200 },
    ]);
    expect(result.tie).toBe(true);
    expect(result.winner).toBeNull();
    expect(result.margin).toBe(0);
  });

  it('selects the higher score even when negative', () => {
    const result = getPodiumResult([
      { id: 'a', name: 'A', score: -300 },
      { id: 'b', name: 'B', score: -100 },
    ]);
    expect(result.tie).toBe(false);
    expect(result.winner.id).toBe('b');
    expect(result.margin).toBe(200);
  });

  it('handles invalid team arrays defensively', () => {
    expect(getPodiumResult([]).tie).toBe(true);
    expect(getPodiumResult(null).winner).toBeNull();
  });
});
