import { describe, expect, it } from 'vitest';
import { toFrontendQuestion } from '@trivia-adapter';

const BASE = {
  id: 42,
  category_name: 'فئة',
  difficulty: 400,
  question_type: 'text',
  question_text: 'سؤال؟',
  flag_code: null,
  media_url_a: null,
  media_url_b: null,
  payload: null,
  answer_text: 'جواب',
  tolerance: 'جواب',
  explanation: 'شرح',
  source_name: 'مصدر',
  source_url: 'https://example.test/item',
  source_checked_at: '2026-10-20',
  source_license: 'CC0',
  source_claim: 'claim',
  content_origin: 'api_sourced',
  fact_group_id: 'group:1',
};

describe('frontendAdapter expansion contract', () => {
  it('carries the public visual without inventing an answer before reveal', () => {
    const visual = { version: 1, type: 'career_tree', nodes: [{ label: 'أ' }, { hidden: true }, { label: 'ج' }] };
    const mapped = toFrontendQuestion({ ...BASE, answer_text: null, tolerance: null, visual }, 'tile');
    expect(mapped.visual).toBe(visual);
    expect(mapped.answer).toBeNull();
    expect(mapped.tolerance).toBeNull();
  });

  it('maps every new backend category to the same frontend category id', () => {
    for (const slug of ['quran', 'nicknames', 'technology', 'videogames', 'matchstick']) {
      const mapped = toFrontendQuestion({ ...BASE, category_slug: slug }, 'tile-1');
      expect(mapped.categoryId).toBe(slug);
      expect(mapped.categorySlug).toBe(slug);
    }
  });

  it('overrides a text question to matchstick when payload.kind is matchstick', () => {
    const payload = {
      kind: 'matchstick',
      version: 1,
      equation: '1+1=3',
      solution: '1+1=2',
      moves_required: 1,
      moves: [{ from: { symbol: 4, segment: 'c' }, to: { symbol: 4, segment: 'e' } }],
      symbols: ['1', '+', '1', '=', '3'],
      start: [['b', 'c'], ['mh', 'pv'], ['b', 'c'], ['e1', 'e2'], ['a', 'b', 'c', 'd', 'g']],
      end: [['b', 'c'], ['mh', 'pv'], ['b', 'c'], ['e1', 'e2'], ['a', 'b', 'd', 'e', 'g']],
      difficulty: 200,
    };
    const mapped = toFrontendQuestion(
      {
        ...BASE,
        category_slug: 'matchstick',
        difficulty: 200,
        payload,
        source_license: 'internal deterministic generator',
        source_claim: 'procedural matchstick solver',
        content_origin: 'generated_puzzle',
      },
      'tile-2',
      200,
    );

    expect(mapped.type).toBe('matchstick');
    expect(mapped.matchstick).toBe(payload);
    expect(mapped.points).toBe(200);
    expect(mapped.source.license).toBe('internal deterministic generator');
    expect(mapped.source.claim).toBe('procedural matchstick solver');
  });

  it('keeps ordinary API text questions standard and carries provenance', () => {
    const mapped = toFrontendQuestion(
      { ...BASE, category_slug: 'technology' },
      'tile-3',
    );
    expect(mapped.type).toBe('standard');
    expect(mapped.categoryId).toBe('technology');
    expect(mapped.source).toEqual({
      name: 'مصدر',
      url: 'https://example.test/item',
      checkedAt: '2026-10-20',
      license: 'CC0',
      claim: 'claim',
      origin: 'api_sourced',
    });
  });
});
