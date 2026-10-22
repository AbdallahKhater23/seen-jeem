import { describe, expect, it } from 'vitest';
import { STAGE_ORDER, isTurnChange } from './StageTransition.jsx';
import { categoryArt } from '../ui/categoryArt.js';

describe('StageTransition', () => {
  it('orders all five stages lobby -> podium', () => {
    expect(STAGE_ORDER).toEqual(['lobby', 'draft', 'board', 'arena', 'podium']);
  });

  it('fires the presenter cue only on real turn changes', () => {
    expect(isTurnChange(null, 'team-falcons')).toBe(true);
    expect(isTurnChange('team-falcons', 'team-wolves')).toBe(true);
    expect(isTurnChange('team-falcons', 'team-falcons')).toBe(false);
    expect(isTurnChange('team-falcons', null)).toBe(false);
  });

  it('resolves art for every stage-linked category', () => {
    for (const slug of ['flags', 'football', 'worldcup', 'career', 'riddles', 'spot']) {
      const art = categoryArt(slug);
      expect(art.src).toMatch(/^\/images\//);
    }
  });
});
