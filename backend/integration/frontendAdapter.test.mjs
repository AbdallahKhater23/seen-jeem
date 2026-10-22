import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ALL_CATEGORY_SLUGS,
  BACKEND_CATEGORY_TO_FRONTEND,
  MATCH_CATEGORY_SLUGS,
  createApiClient,
  toFrontendCategory,
  toBackendOutcome,
  toBackendTileKey,
  toFrontendBoard,
  toFrontendOutcome,
  toFrontendRerollResult,
  toFrontendResolveResult,
  toFrontendTileKey,
} from './frontendAdapter.js';

const spotQuestion = {
  id: 7,
  category_slug: 'spotdiff',
  category_name: 'طلع الفرق',
  difficulty: 400,
  question_type: 'spot_diff',
  question_text: 'وين الفروق الثلاثة؟',
  flag_code: null,
  media_url_a: null,
  media_url_b: null,
  payload: {
    sceneId: 'scene-1',
    variantSeed: 5,
    differences: [
      { id: 'a', x: 10, y: 20 },
      { id: 'b', x: 30, y: 40 },
      { id: 'c', x: 50, y: 60 },
    ],
  },
  answer_text: 'ثلاثة',
  tolerance: 'مطابق تماماً',
  explanation: 'ثلاثة فروق.',
  source_name: null,
  source_url: null,
  source_checked_at: null,
  content_origin: 'generated_puzzle',
};

const textQuestion = {
  ...spotQuestion,
  id: 8,
  category_slug: 'riddles',
  category_name: 'ألغاز وفوازير',
  question_type: 'text',
  question_text: 'ما الشيء الذي كلما زاد نقص؟',
  payload: null,
  content_origin: 'curated',
};

function tile(overrides = {}) {
  return {
    tile_key: 'spotdiff-400-1',
    category_slug: 'spotdiff',
    difficulty: 400,
    is_backup: false,
    status: 'unplayed',
    outcome: null,
    delta_team1: 0,
    delta_team2: 0,
    powers_applied: [],
    question: spotQuestion,
    answered_at: null,
    compatible_categories: [],
    compatible_difficulties: [],
    ...overrides,
  };
}

function match(overrides = {}) {
  return {
    match_code: 'demo-code',
    team1_name: 'الصقور',
    team2_name: 'الذئاب',
    score_team1: 0,
    score_team2: 0,
    current_turn: 'team1',
    status: 'active',
    winner: null,
    coin_toss_winner: 'team1',
    version: 1,
    created_at: '2026-10-19T20:00:00.000Z',
    updated_at: '2026-10-19T20:00:00.000Z',
    ...overrides,
  };
}

test('translates canonical categories, types, outcomes, and tile keys', () => {
  const board = toFrontendBoard({
    match: match(),
    tiles: [tile(), tile({ tile_key: 'riddles-200-1', category_slug: 'riddles', question: textQuestion })],
    backups: [],
  });

  assert.equal(board.tiles[0].id, 'spot-400-1');
  assert.equal(board.tiles[0].categoryId, 'spot');
  assert.equal(board.questions['backend-7'].categorySlug, 'spot');
  assert.equal(board.questions['backend-7'].categoryName, 'طلع الفرق');
  assert.equal(board.questions['backend-7'].type, 'spot_diff');
  assert.equal(board.questions['backend-7'].tileId, 'spot-400-1');
  assert.equal(board.questions['backend-7'].sceneId, 'scene-1');
  assert.deepEqual(board.questions['backend-7'].differences, spotQuestion.payload.differences);
  assert.equal(board.tiles[1].categoryId, 'riddles');
  assert.equal(board.questions['backend-8'].type, 'standard');

  assert.equal(toFrontendTileKey('spotdiff-600-2'), 'spot-600-2');
  assert.equal(toBackendTileKey('spot-600-2'), 'spotdiff-600-2');
  assert.equal(toBackendOutcome('defending_team', 'team-falcons'), 'team2');
  assert.equal(toFrontendOutcome('team2', 'team-falcons'), 'defending_team');
});

test('maps universal backups to the frontend backup shape', () => {
  const board = toFrontendBoard({
    match: match(),
    tiles: [tile()],
    backups: [
      tile({
        tile_key: 'backup-1',
        category_slug: null,
        difficulty: null,
        is_backup: true,
        question: textQuestion,
        compatible_categories: ['flags', 'spotdiff'],
        compatible_difficulties: [200, 400, 600],
      }),
    ],
  });

  assert.deepEqual(board.backups[0], {
    id: 'backup-1',
    backupKey: 'backup-1',
    type: 'standard',
    question: textQuestion.question_text,
    answer: textQuestion.answer_text,
    tolerance: textQuestion.tolerance,
    explanation: textQuestion.explanation,
    status: 'unplayed',
    compatibleCategoryIds: ['flags', 'spot'],
    compatiblePoints: [200, 400, 600],
    source: { name: null, url: null, checkedAt: null, license: textQuestion.source_license,
      claim: textQuestion.source_claim, origin: 'curated' },
  });
});

test('maps a resolve response into frontend tileResult shape', () => {
  const result = toFrontendResolveResult({
    match: match({ current_turn: 'team2', score_team1: 400, version: 2 }),
    tile: tile({
      status: 'played',
      outcome: 'team1',
      delta_team1: 400,
      delta_team2: -400,
      powers_applied: ['pit'],
      answered_at: '2026-10-19T20:01:00.000Z',
    }),
    score_ledger: [
      { team: 'team1', delta: 400, reason: 'جائزة الخانة لصاحب الدور' },
      { team: 'team2', delta: -400, reason: 'الحفرة', power: 'pit' },
    ],
    idempotent_replay: false,
  });

  assert.equal(result.tileResult.tileId, 'spot-400-1');
  assert.equal(result.tileResult.activeTeamId, 'team-falcons');
  assert.equal(result.tileResult.defendingTeamId, 'team-wolves');
  assert.equal(result.tileResult.outcome, 'active_team');
  assert.equal(result.tileResult.winningTeamId, 'team-falcons');
  assert.deepEqual(result.tileResult.deltas, {
    'team-falcons': 400,
    'team-wolves': -400,
  });
  assert.equal(result.scoreLedger[0].reason, 'base_win');
  assert.equal(result.scoreLedger[1].teamId, 'team-wolves');
  assert.equal(result.scoreLedger[1].reason, 'pit_deduction');
  assert.equal(result.scoreLedger[1].powerId, 'pit');
  assert.equal(result.match.currentTurnTeamId, 'team-wolves');
});

test('createMatch sends the six UI categories the backend requires', async () => {
  const calls = [];
  const client = createApiClient({
    baseUrl: '/api/v1',
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ match: match() }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      });
    },
  });

  await client.createMatch({
    team1Name: 'الصقور',
    team2Name: 'الذئاب',
    coinTossWinner: 'team-falcons',
    key: 'create-test-1',
  });

  const body = JSON.parse(calls[0].init.body);
  assert.equal(calls[0].init.headers['Idempotency-Key'], 'create-test-1');
  assert.deepEqual(body.category_slugs, [...MATCH_CATEGORY_SLUGS]);
  assert.deepEqual(body.category_slugs, [
    'flags',
    'football',
    'worldcup',
    'career',
    'riddles',
    'spotdiff',
  ]);
  assert.equal(body.coin_toss_winner, 'team1');
});

test('maps every canonical category and forwards explicit six', async () => {
  // الكتالوج في المحوّل هو مصدر الحقيقة: كل slug في الخريطة يظهر مرة واحدة،
  // والفئات الاثنتي عشرة الأصلية باقية. لا عدد مكتوب يجمّد المحتوى.
  assert.deepEqual(
    [...ALL_CATEGORY_SLUGS].sort(),
    Object.keys(BACKEND_CATEGORY_TO_FRONTEND).sort(),
  );
  assert.equal(ALL_CATEGORY_SLUGS.length, Object.keys(BACKEND_CATEGORY_TO_FRONTEND).length);
  for (const slug of ALL_CATEGORY_SLUGS) {
    assert.equal(toFrontendCategory(slug), BACKEND_CATEGORY_TO_FRONTEND[slug]);
  }
  for (const core of [
    'flags',
    'capitals',
    'football',
    'ucl',
    'worldcup',
    'career',
    'clubs',
    'arab_ftbl',
    'numbers',
    'riddles',
    'general',
    'spotdiff',
  ]) {
    assert.ok(ALL_CATEGORY_SLUGS.includes(core), `الفئة الأساسية مفقودة: ${core}`);
  }
  assert.equal(toFrontendCategory('spotdiff'), 'spot');
  assert.equal(toFrontendCategory('arab_ftbl'), 'arab_ftbl');
  assert.equal(toFrontendCategory('unknown'), 'unknown');

  const calls = [];
  const client = createApiClient({
    baseUrl: '/api/v1',
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ match: match() }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      });
    },
  });
  await client.createMatch({
    team1Name: 'أ',
    team2Name: 'ب',
    startingTurn: 'team-wolves',
    categorySlugs: ['flags', 'capitals', 'ucl', 'clubs', 'general', 'spot'],
    key: 'explicit-six',
  });
  const body = JSON.parse(calls[0].init.body);
  assert.deepEqual(body.category_slugs, [
    'flags',
    'capitals',
    'ucl',
    'clubs',
    'general',
    'spotdiff',
  ]);
  assert.equal(body.starting_turn, 'team2');
  assert.equal(body.category_slugs.length, 6);
});

test('carries the host token from create responses and sends it on mutations', async () => {
  const board = toFrontendBoard({
    match: match(),
    tiles: [],
    backups: [],
    host_token: 'host-secret-token-value',
  });
  assert.equal(board.server.hostToken, 'host-secret-token-value');

  const plain = toFrontendBoard({ match: match(), tiles: [], backups: [] });
  assert.equal(plain.server.hostToken, null);

  const calls = [];
  const client = createApiClient({
    baseUrl: '/api/v1',
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    },
  });
  client.setHostToken(board.server.hostToken);
  await client.reroll({
    matchCode: 'demo-code',
    tileKey: 'spot-400-1',
    expectedVersion: 1,
    key: 'reroll-host',
  });
  assert.equal(calls[0].init.headers['X-Host-Token'], 'host-secret-token-value');

  client.setHostToken(null);
  await client.getMatch('demo-code');
  assert.equal(calls[1].init.headers['X-Host-Token'], undefined);
});

test('maps a reroll response and preserves backend team scores', () => {
  const result = toFrontendRerollResult({
    match: match({ current_turn: 'team2', score_team1: 200, score_team2: 100, version: 3 }),
    tile: tile({
      tile_key: 'spotdiff-400-1',
      difficulty: 600,
      question: { ...textQuestion, difficulty: 200 },
    }),
    backup_used: 'backup-1',
    idempotent_replay: false,
  });

  assert.equal(result.tile.id, 'spot-400-1');
  assert.equal(result.tile.points, 600);
  assert.equal(result.question.id, 'backend-8');
  assert.equal(result.question.tileId, 'spot-400-1');
  assert.equal(result.question.points, 600);
  assert.equal(result.backupUsed, 'backup-1');
  assert.equal(result.match.scores['team-falcons'], 200);
  assert.equal(result.match.scores['team-wolves'], 100);
});
