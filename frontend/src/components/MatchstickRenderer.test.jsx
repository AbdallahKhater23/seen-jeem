import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import segments from '@shared/matchstick_segments.json';
import MatchstickRenderer, { buildSticks } from './MatchstickRenderer.jsx';

const DIGITS = segments.digits;
const OPERATORS = segments.operators;

const PAYLOAD = {
  kind: 'matchstick',
  version: 1,
  equation: '1+1=3',
  solution: '1+1=2',
  moves_required: 1,
  difficulty: 200,
  symbols: ['1', '+', '1', '=', '3'],
  start: [
    [...DIGITS['1']],
    [...OPERATORS['+']],
    [...DIGITS['1']],
    [...OPERATORS['=']],
    [...DIGITS['3']],
  ],
  end: [
    [...DIGITS['1']],
    [...OPERATORS['+']],
    [...DIGITS['1']],
    [...OPERATORS['=']],
    [...DIGITS['2']],
  ],
  moves: [{ from: { symbol: 4, segment: 'c' }, to: { symbol: 4, segment: 'e' } }],
};

function count(haystack, needle) {
  return haystack.split(needle).length - 1;
}

describe('MatchstickRenderer', () => {
  it('renders one SVG stick per start segment and the move hint', () => {
    const html = renderToStaticMarkup(
      <MatchstickRenderer question={{ matchstick: PAYLOAD }} />,
    );

    // 1 (2) + + (2) + 1 (2) + = (2) + 3 (5) = 13 sticks.
    expect(count(html, '<line ')).toBe(13);
    expect(count(html, '<circle')).toBe(13);
    expect(html).toContain('معادلة أعواد الثقاب 1+1=3');
    expect(html).toContain('حرّك عودًا واحدًا');
    expect(html).not.toContain('الحل:');
  });

  it('animates a moved stick to the destination column in global coordinates', () => {
    const crossColumn = {
      ...PAYLOAD,
      moves: [{ from: { symbol: 4, segment: 'c' }, to: { symbol: 2, segment: 'e' } }],
    };
    const moved = buildSticks(crossColumn).find((stick) => stick.moved);

    // المصدر: العمود 4، القطعة c (x=90). الهدف: العمود 2، القطعة e (x=10).
    expect(moved.from[0]).toBe(4 * 110 + 12 + 90);
    expect(moved.to[0]).toBe(2 * 110 + 12 + 10);
    expect(moved.sourceSymbolIndex).toBe(4);
    expect(moved.targetSymbolIndex).toBe(2);
  });

  it('shows the solution and updates the accessible label when revealed', () => {
    const html = renderToStaticMarkup(
      <MatchstickRenderer question={{ matchstick: PAYLOAD }} revealed />,
    );

    expect(html).toContain('الحل: 1+1=2');
    expect(html).toContain('معادلة أعواد الثقاب 1+1=3، الحل 1+1=2');
  });

  it('shows the two-move caption for difficulty 600', () => {
    const html = renderToStaticMarkup(
      <MatchstickRenderer
        question={{ matchstick: { ...PAYLOAD, moves_required: 2, difficulty: 600 } }}
      />,
    );
    expect(html).toContain('حرّك عودين فقط');
  });

  it('degrades safely when the payload is missing', () => {
    const html = renderToStaticMarkup(<MatchstickRenderer question={{}} />);
    expect(html).toContain('تعذّر عرض لغز الأعواد.');
  });
});
