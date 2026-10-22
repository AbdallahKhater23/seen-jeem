import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import FootballVisualRenderer from './FootballVisualRenderer.jsx';

const defaultApiShot = (v, revealed) => revealed ? v : { ...v, answer_label: undefined };

describe('FootballVisualRenderer', () => {
  it('renders an RTL career puzzle without hidden labels in DOM or accessibility text', () => {
    const visual = { version: 1, type: 'career_tree', nodes: [
      { label: 'الأول' }, { label: 'إجابة سرية', hidden: true }, { label: 'الثالث', loan: true },
    ] };
    const html = renderToStaticMarkup(<FootballVisualRenderer visual={visual} />);
    expect(html).toContain('dir="rtl"');
    expect(html).toContain('النادي الناقص');
    expect(html).not.toContain('إجابة سرية');
    expect(html).toContain('إعارة');
    expect(renderToStaticMarkup(<FootballVisualRenderer visual={visual} revealed />)).toContain('إجابة سرية');
  });

  it('renders 11 schematic markers and omits the hidden jersey number', () => {
    const visual = { version: 1, type: 'lineup_svg', formation: '4-4-2', schematic: true,
      players: Array.from({ length: 11 }, (_, i) => ({ label: `لاعب ${i}`, x: 10 + i % 4 * 25,
        y: 10 + Math.floor(i / 4) * 30, hidden: i === 10, number: i + 1 })) };
    const html = renderToStaticMarkup(<FootballVisualRenderer visual={visual} />);
    expect(html.split('<circle r="19"').length - 1).toBe(11);
    expect(html).toContain('رسم توضيحي');
    expect(html).not.toContain('لاعب 10');
    const bottom = { ...visual, players: visual.players.map((player, i) => i === 0 ? { ...player, y: 95 } : player) };
    expect(renderToStaticMarkup(<FootballVisualRenderer visual={bottom} />)).toContain('translate(80 429)');
    for (const number of [{ unsafe: true }, '9', 0, 100]) {
      const malformed = { ...visual, players: visual.players.map((player, i) => i === 0 ? { ...player, number } : player) };
      expect(renderToStaticMarkup(<FootballVisualRenderer visual={malformed} />)).toContain('كمّلوا من السؤال المكتوب');
    }
  });

  it('keeps odd-one-out reason hidden until reveal', () => {
    const visual = { version: 1, type: 'odd_one_out_grid', items: ['أ', 'ب', 'ج', 'د'].map(label => ({ label })),
      common_property: 'شرح سري', odd_index: 2 };
    expect(renderToStaticMarkup(<FootballVisualRenderer visual={visual} />)).not.toContain('شرح سري');
    expect(renderToStaticMarkup(<FootballVisualRenderer visual={visual} revealed />)).toContain('شرح سري');
  });

  it('renders schematic shot radar and reveals answer label only after reveal', () => {
    const visual = { version: 1, type: 'shot_radar', schematic: true,
      shot_x: 72, shot_y: 42, goal_x: 92, goal_y: 48,
      context_label: 'نهائي 2002', answer_label: 'إجابة سرية' };
    const html = renderToStaticMarkup(<FootballVisualRenderer visual={defaultApiShot(visual, false)} />);
    expect(html).toContain('مخطط توضيحي لمكان التسديدة');
    expect(html).not.toContain('إجابة سرية');
    expect(renderToStaticMarkup(<FootballVisualRenderer visual={visual} revealed />)).toContain('إجابة سرية');
  });

  it('offers a text fallback for unsupported/malformed visual payloads', () => {
    for (const visual of [null, { version: 8, type: 'career_tree' }, { version: 1, type: 'lineup_svg', players: [] }]) {
      expect(renderToStaticMarkup(<FootballVisualRenderer visual={visual} />)).toContain('كمّلوا من السؤال المكتوب');
    }
  });
});
