import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  STAGES,
  STORAGE_KEY,
  TEAM_A_ID as A,
  TEAM_B_ID as B,
} from '../game/constants.js';
import { createInitialGameState } from '../game/state.js';

const mocks = vi.hoisted(() => ({
  createMatch: vi.fn(),
  getMatch: vi.fn(),
  resolve: vi.fn(),
  reroll: vi.fn(),
  adjustScore: vi.fn(),
  revealTile: vi.fn(),
}));

vi.mock('../api/server.js', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, api: { ...actual.api, ...mocks } };
});

vi.mock('../api/installation.js', () => ({
  ensureInstallation: vi.fn(async () => ({
    credential: 'test-install-token',
    installationId: 1,
    shadowUserId: 2,
    regKey: 'test-reg-key',
  })),
  getStoredInstallation: vi.fn(() => null),
  installationTokenSync: vi.fn(() => 'test-install-token'),
}));

const { useGameStore } = await import('./gameStore.js');
const api = () => useGameStore.getState();
const STANDARD = ['pit', 'trap', 'steal', 'double', 'noise', 'switch'];
const CATEGORIES = ['flags', 'football', 'worldcup', 'career', 'riddles', 'spot'];
const TILE_KEY = 'football-400-1';
const QUESTION_ID = 7;

function question(id = QUESTION_ID) {
  return {
    id,
    category_slug: 'football',
    category_name: 'كورة عامة',
    difficulty: 400,
    question_type: 'text',
    question_text: 'من فاز بكأس العالم 2010؟',
    flag_code: null,
    media_url_a: null,
    media_url_b: null,
    payload: null,
    answer_text: 'إسبانيا',
    tolerance: 'Spain',
    explanation: 'فازت إسبانيا على هولندا.',
    source_name: 'اختبار',
    source_url: null,
    source_checked_at: '2026-10-19',
    content_origin: 'test',
  };
}

function createBoard({ version = 1, status = 'active', scoreTeam1 = 0, scoreTeam2 = 0 } = {}) {
  return {
    match: {
      match_code: 'ABC123',
      team1_name: 'الصقور',
      team2_name: 'الذئاب',
      score_team1: scoreTeam1,
      score_team2: scoreTeam2,
      current_turn: 'team1',
      status,
      winner: null,
      coin_toss_winner: 'team1',
      version,
    },
    tiles: [
      {
        tile_key: TILE_KEY,
        category_slug: 'football',
        difficulty: 400,
        status: 'unplayed',
        outcome: null,
        delta_team1: 0,
        delta_team2: 0,
        powers_applied: [],
        answered_at: null,
        compatible_categories: [],
        compatible_difficulties: [],
        question: question(),
      },
    ],
    backups: [],
  };
}

function resolvedBoard({ outcome = 'team2', version = 2 } = {}) {
  const board = createBoard({ version });
  const tile = board.tiles[0];
  tile.status = 'played';
  tile.outcome = outcome;
  tile.delta_team1 = outcome === 'team1' ? 400 : 0;
  tile.delta_team2 = outcome === 'team2' ? 400 : 0;
  tile.answered_at = '2026-10-20T10:00:00.000Z';
  board.match.score_team1 = tile.delta_team1;
  board.match.score_team2 = tile.delta_team2;
  board.match.current_turn = 'team1';
  return { match: board.match, tile, score_ledger: [] };
}

async function beginServerMatch() {
  expect(api().updateTeam(A, { name: 'الصقور' }).ok).toBe(true);
  expect(api().updateTeam(B, { name: 'الذئاب' }).ok).toBe(true);
  expect(api().finishCoinToss(A, 1000).ok).toBe(true);
  // اختيار ست فئات مطلوب الآن لإنشاء المباراة على الخادم.
  useGameStore.setState({ selectedCategorySlugs: CATEGORIES });
  const started = await api().beginMatch(1000);
  expect(started.ok, started.reason ?? '').toBe(true);
  return started;
}

async function enterArenaOnServer() {
  await beginServerMatch();
  STANDARD.forEach((powerId, index) => {
    expect(api().draftPower(powerId, 1100 + index).ok).toBe(true);
  });
  expect(api().enterBoard().ok).toBe(true);
  expect(api().selectTile(TILE_KEY, 2000).ok).toBe(true);
  expect(api().revealAnswer(3000).ok).toBe(true);
}

beforeEach(() => {
  window.localStorage.clear();
  useGameStore.setState({ ...createInitialGameState() });
  Object.values(mocks).forEach((mock) => mock.mockReset());
});

describe('server-backed match flow', () => {
  it('fetches the answer and revealed visual only on server-authorized reveal', async () => {
    const board = createBoard();
    board.tiles[0].question.answer_text = null;
    board.tiles[0].question.tolerance = null;
    board.tiles[0].question.explanation = null;
    board.tiles[0].question.visual = { version: 1, type: 'career_tree', nodes: [
      { label: 'النادي الأول' }, { hidden: true }, { label: 'النادي الثالث' },
    ] };
    mocks.createMatch.mockResolvedValue(board);
    await beginServerMatch();
    STANDARD.forEach((powerId, index) => api().draftPower(powerId, 1100 + index));
    expect(api().enterBoard().ok).toBe(true);
    expect(api().selectTile(TILE_KEY, 2000).ok).toBe(true);
    expect(api().content.questions[`backend-${QUESTION_ID}`].answer).toBeNull();
    expect(api().content.questions[`backend-${QUESTION_ID}`].visual.nodes[1]).toEqual({ hidden: true });
    const revealedTile = { ...board.tiles[0], question: question(),
      revealed_at: '2026-10-20T10:00:02Z', opened_at: '2026-10-20T10:00:00Z', active_team: 'team1' };
    revealedTile.question.visual = { ...board.tiles[0].question.visual,
      nodes: [{ label: 'النادي الأول' }, { hidden: true, label: 'النادي الثاني' }, { label: 'النادي الثالث' }] };
    mocks.revealTile.mockResolvedValue({ match: { ...board.match, version: 2 }, tile: revealedTile,
      session: { revealed_at: revealedTile.revealed_at, opened_at: revealedTile.opened_at, active_team: 'team1' } });
    expect((await api().revealAnswerOnline(3000)).ok).toBe(true);
    expect(api().content.questions[`backend-${QUESTION_ID}`].answer).toBe('إسبانيا');
    expect(api().content.questions[`backend-${QUESTION_ID}`].visual.nodes[1].label).toBe('النادي الثاني');
    expect(api().currentQuestion.revealed).toBe(true);
  });

  it('creates the match on FastAPI and stores the board as a recovery copy', async () => {
    mocks.createMatch.mockResolvedValue(createBoard());
    const catalog = {
      status: 'ready',
      error: null,
      items: [{ id: 'football', backendSlug: 'football', name: 'كورة عالمية وأوروبية', icon: 'Trophy', eligibleCount: 300 }],
    };
    useGameStore.setState({ categories: catalog });

    const started = await beginServerMatch();

    // كتالوج الخادم يبقى محمّلًا بعد إنشاء المباراة كي تعرض اللوحة أسماء الفئات الحقيقية.
    expect(api().categories).toBe(catalog);

    expect(started.matchCode).toBe('ABC123');
    expect(mocks.createMatch).toHaveBeenCalledWith({
      team1Name: 'الصقور',
      team2Name: 'الذئاب',
      startingTurn: A,
      categorySlugs: CATEGORIES,
      team1UserIds: [],
      team2UserIds: [],
      installToken: 'test-install-token',
    });
    expect(api().selectedCategorySlugs).toEqual(CATEGORIES);
    expect(api().content.tiles[0].categoryId).toBe('football');
    expect(api().currentStage).toBe(STAGES.DRAFT);
    expect(api().server).toMatchObject({ matchCode: 'ABC123', version: 1, online: true });
    expect(api().content.source).toBe('server');
    expect(api().content.tiles).toHaveLength(1);
    expect(api().content.questions[`backend-${QUESTION_ID}`].answer).toBe('إسبانيا');
    expect(api().teams.map((team) => team.name)).toEqual(['الصقور', 'الذئاب']);

    const cached = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
    expect(cached.state.server.matchCode).toBe('ABC123');
    expect(cached.state.content.tiles).toHaveLength(1);
  });

  it('sends a defending-team answer as the backend team2 outcome and commits the server score', async () => {
    mocks.createMatch.mockResolvedValue(createBoard());
    mocks.resolve.mockResolvedValue(resolvedBoard({ outcome: 'team2' }));
    await enterArenaOnServer();

    const result = await api().resolveTeamWinOnline(B, 4000);

    expect(result.ok).toBe(true);
    expect(result.outcome).toBe('defending_team');
    expect(mocks.resolve).toHaveBeenCalledWith(
      expect.objectContaining({
        matchCode: 'ABC123',
        tileKey: TILE_KEY,
        outcome: 'defending_team',
        activeTeamId: A,
        expectedVersion: 1,
      }),
    );
    expect(api().teams.find((team) => team.id === B).score).toBe(400);
    expect(api().tileResults[TILE_KEY]).toMatchObject({
      played: true,
      winningTeamId: B,
      outcome: 'defending_team',
    });
    expect(api().server.version).toBe(2);
    expect(api().currentTurnTeamId).toBe(A);
    expect(api().currentStage).toBe(STAGES.BOARD);
  });

  it('treats the server as authoritative when syncing a cached match', async () => {
    mocks.createMatch.mockResolvedValue(createBoard());
    await beginServerMatch();
    useGameStore.setState({
      teams: api().teams.map((team) => ({ ...team, score: 999 })),
      currentTurnTeamId: B,
    });
    mocks.getMatch.mockResolvedValue(createBoard({ scoreTeam1: 600, scoreTeam2: 200 }));

    const result = await api().syncServerMatch();

    expect(result.ok).toBe(true);
    expect(api().teams.find((team) => team.id === A).score).toBe(600);
    expect(api().teams.find((team) => team.id === B).score).toBe(200);
    expect(api().currentTurnTeamId).toBe(A);
    expect(api().server.online).toBe(true);
  });
});
