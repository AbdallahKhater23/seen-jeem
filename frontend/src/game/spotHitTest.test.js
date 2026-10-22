import { describe, expect, it } from 'vitest';
import { QUESTIONS } from '../data/mockData.js';
import { clientToSvgPoint, distanceToDifference, hitTestDifference } from './spotHitTest.js';

const viewBox = { width: 400, height: 300 };

describe('spot-the-difference hit testing', () => {
  it('maps the same relative point identically at multiple sizes', () => {
    const small = clientToSvgPoint(200, 150, { left: 0, top: 0, width: 400, height: 300 }, viewBox);
    const large = clientToSvgPoint(900, 700, { left: 100, top: 100, width: 1600, height: 1200 }, viewBox);
    const stretched = clientToSvgPoint(500, 400, { left: 100, top: 100, width: 800, height: 600 }, viewBox);
    expect(small).toEqual({ x: 200, y: 150 });
    expect(large.x).toBeCloseTo(200);
    expect(large.y).toBeCloseTo(150);
    expect(stretched.x).toBeCloseTo(200);
    expect(stretched.y).toBeCloseTo(150);
  });

  it('returns null for a zero-sized SVG', () => {
    expect(clientToSvgPoint(10, 10, { left: 0, top: 0, width: 0, height: 0 }, viewBox)).toBeNull();
    expect(clientToSvgPoint(10, 10, null, viewBox)).toBeNull();
  });

  it('hits a difference at its center and misses outside its radius', () => {
    const differences = [{ id: 'd1', x: 100, y: 80, r: 20 }];
    expect(hitTestDifference(differences, 100, 80)?.id).toBe('d1');
    expect(hitTestDifference(differences, 119, 80)?.id).toBe('d1');
    expect(hitTestDifference(differences, 121, 80)).toBeNull();
    expect(distanceToDifference(differences[0], 100, 100)).toBe(20);
  });

  it('matches every dataset difference at equivalent small and large coordinates', () => {
    const spots = QUESTIONS.filter((question) => question.type === 'spot_diff');
    for (const question of spots) {
      for (const difference of question.differences) {
        const small = clientToSvgPoint(
          difference.x,
          difference.y,
          { left: 0, top: 0, width: 400, height: 300 },
          viewBox,
        );
        const large = clientToSvgPoint(
          difference.x * 3,
          difference.y * 3,
          { left: 0, top: 0, width: 1200, height: 900 },
          viewBox,
        );
        expect(hitTestDifference(question.differences, small.x, small.y)?.id).toBe(difference.id);
        expect(hitTestDifference(question.differences, large.x, large.y)?.id).toBe(difference.id);
      }
    }
  });
});
