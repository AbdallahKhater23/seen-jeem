import { describe, expect, it } from 'vitest';
import { TILES, TILE_BY_ID } from '../data/mockData.js';
import { STAGES, TEAM_A_ID as A, TEAM_B_ID as B } from './constants.js';
import { buildDraftOrder } from './draft.js';
import {
  createInitialGameState,
  sanitizePersistedState,
} from './state.js';

const PICKS = ['pit', 'trap', 'steal', 'double', 'noise', 'switch'].map((powerId, index) => ({
  teamId: buildDraftOrder(A, B)[index],
  powerId,
}));

function makeActiveState() {
  const state = createInitialGameState();
  state.currentStage = STAGES.BOARD;
  state.coinToss = { result: A, completed: true };
  state.draft = {
    order: buildDraftOrder(A, B),
    picks: PICKS.map((pick) => ({ ...pick })),
  };
  state.currentTurnTeamId = A;
  state.matchStartedAt = 1000;
  state.teams[0].score = 400;
  state.usedPowerIds[A] = ['pit'];
  return state;
}

const SERVER_TILE = {
  id: 'flags-200-1',
  categoryId: 'flags',
  points: 200,
  questionId: 'backend-9001',
};

const SERVER_QUESTION = {
  id: 'backend-9001',
  tileId: 'flags-200-1',
  categoryId: 'flags',
  points: 200,
  type: 'standard',
  question: 'سؤال من السيرفر',
  answer: 'جواب السيرفر',
  tolerance: '',
  explanation: '',
};

function makeServerState() {
  const state = makeActiveState();
  state.server = {
    matchCode: 'srv-code',
    version: 4,
    status: 'active',
    winner: null,
    online: true,
    error: null,
    pending: false,
    syncing: false,
  };
  state.content = {
    source: 'server',
    questions: { [SERVER_QUESTION.id]: { ...SERVER_QUESTION } },
    tiles: [{ ...SERVER_TILE }],
    backups: [],
  };
  state.tileResults = {};
  state.currentStage = STAGES.ARENA;
  state.currentQuestion = {
    ...makeArenaQuestion(5000),
    tileId: SERVER_TILE.id,
    questionId: SERVER_QUESTION.id,
    categoryId: SERVER_TILE.categoryId,
    points: SERVER_TILE.points,
    usedBackupIds: ['backup-1'],
  };
  return state;
}

function makeArenaQuestion(now = 5000) {
  const tile = TILES.find((item) => item.categoryId === 'football' && item.points === 400);
  return {
    tileId: tile.id,
    questionId: TILE_BY_ID[tile.id].questionId,
    categoryId: tile.categoryId,
    points: tile.points,
    sourceBackupId: null,
    activeTeamId: A,
    originalActiveTeamId: A,
    stolenByTeamId: null,
    sessionStartedAt: now - 3000,
    revealed: false,
    revealedAt: null,
    activePowers: ['pit'],
    usedBackupIds: [],
    noiseUntil: null,
    wrongGuesses: 1,
    twoAnswerExtensionUsed: true,
    timer: {
      phase: 'primary',
      running: true,
      elapsedMs: 18000,
      startedAt: now - 18000,
    },
  };
}

describe('sanitizePersistedState', () => {
  it('restores a valid active board match', () => {
    const result = sanitizePersistedState({ state: makeActiveState(), version: 1 });
    expect(result.valid).toBe(true);
    expect(result.state.currentStage).toBe(STAGES.BOARD);
    expect(result.state.currentTurnTeamId).toBe(A);
    expect(result.state.teams[0].score).toBe(400);
    expect(result.notice).toBeNull();
  });

  it('accepts a bare state object as well as a persisted wrapper', () => {
    const result = sanitizePersistedState(makeActiveState());
    expect(result.valid).toBe(true);
    expect(result.state.draft.picks).toHaveLength(6);
  });

  it('recovers a corrupt stage to a fresh lobby with a notice', () => {
    const result = sanitizePersistedState({ state: { currentStage: '__corrupt__' }, version: 1 });
    expect(result.valid).toBe(false);
    expect(result.state.currentStage).toBe(STAGES.LOBBY);
    expect(result.notice.length).toBeGreaterThan(0);
  });

  it('rejects a future schema version', () => {
    const raw = makeActiveState();
    raw.schemaVersion = 999;
    const result = sanitizePersistedState(raw);
    expect(result.valid).toBe(false);
    expect(result.notice).toContain('إصدار');
  });

  it('falls from arena to board when the question snapshot is missing', () => {
    const raw = makeActiveState();
    raw.currentStage = STAGES.ARENA;
    raw.currentQuestion = null;
    const result = sanitizePersistedState(raw);
    expect(result.valid).toBe(true);
    expect(result.state.currentStage).toBe(STAGES.BOARD);
    expect(result.notice).toContain('السؤال');
  });

  it('keeps a running open stopwatch intact', () => {
    const raw = makeActiveState();
    raw.currentStage = STAGES.ARENA;
    raw.currentQuestion = makeArenaQuestion(5000);
    const result = sanitizePersistedState(raw, 5000);
    expect(result.valid).toBe(true);
    expect(result.state.currentStage).toBe(STAGES.ARENA);
    expect(result.state.currentQuestion.timer.running).toBe(true);
    expect(result.state.currentQuestion.timer.phase).toBe('primary');
    expect(result.state.currentQuestion.timer.elapsedMs).toBe(18000);
    expect(result.state.currentQuestion.wrongGuesses).toBe(1);
    expect(result.state.currentQuestion.twoAnswerExtensionUsed).toBe(true);
  });

  it('migrates an old closed countdown into a running open clock', () => {
    const raw = makeActiveState();
    raw.currentStage = STAGES.ARENA;
    raw.currentQuestion = makeArenaQuestion(5000);
    raw.currentQuestion.timer = {
      phase: 'done',
      running: false,
      remainingMs: 0,
      deadline: 5000,
    };
    const result = sanitizePersistedState(raw, 5000);
    expect(result.state.currentQuestion.timer.phase).toBe('primary');
    expect(result.state.currentQuestion.timer.running).toBe(true);
    expect(result.state.currentQuestion.timer.elapsedMs).toBe(60000);
    expect(result.state.currentQuestion.timer.startedAt).toBe(5000);
  });

  it('drops an arena question that refers to an already-played tile', () => {
    const raw = makeActiveState();
    raw.currentStage = STAGES.ARENA;
    raw.currentQuestion = makeArenaQuestion(5000);
    raw.tileResults[raw.currentQuestion.tileId] = {
      played: true,
      outcome: 'nobody',
      winningTeamId: null,
    };
    const result = sanitizePersistedState(raw);
    expect(result.state.currentStage).toBe(STAGES.BOARD);
    expect(result.state.currentQuestion).toBeNull();
  });

  it('filters used powers to powers actually drafted by that team', () => {
    const raw = makeActiveState();
    raw.usedPowerIds[A] = ['pit', 'steal', 'switch'];
    const result = sanitizePersistedState(raw);
    expect(result.state.usedPowerIds[A]).toEqual(['pit']);
    expect(result.state.usedPowerIds[B]).toEqual([]);
  });

  it('accepts the same power on both teams but not twice on one team', () => {
    const raw = makeActiveState();
    raw.draft.picks[1] = { teamId: B, powerId: 'pit' };
    const shared = sanitizePersistedState(raw);
    expect(shared.valid).toBe(true);
    expect(shared.state.draft.picks.filter((pick) => pick.powerId === 'pit')).toHaveLength(2);

    const duplicate = makeActiveState();
    duplicate.draft.picks[3] = { teamId: A, powerId: 'pit' };
    const rejected = sanitizePersistedState(duplicate);
    expect(rejected.valid).toBe(false);
  });

  it('rejects malformed draft picks and out-of-order teams', () => {
    const raw = makeActiveState();
    raw.draft.picks[0] = { teamId: B, powerId: 'pit' };
    const result = sanitizePersistedState(raw);
    expect(result.valid).toBe(false);
    expect(result.state.currentStage).toBe(STAGES.LOBBY);
  });

  it('refuses to restore podium before all 36 tiles are played', () => {
    const raw = makeActiveState();
    raw.currentStage = STAGES.PODIUM;
    const result = sanitizePersistedState(raw);
    expect(result.state.currentStage).toBe(STAGES.BOARD);
    expect(result.notice).toContain('المنصة');
  });

  it('normalizes invalid team data or falls back safely', () => {
    const raw = makeActiveState();
    raw.teams[1].score = Number.NaN;
    const result = sanitizePersistedState(raw);
    expect(result.valid).toBe(true);
    expect(result.state.teams[1].score).toBe(0);
  });

  it('returns a lobby for null input without throwing', () => {
    const result = sanitizePersistedState(null);
    expect(result.valid).toBe(false);
    expect(result.state.currentStage).toBe(STAGES.LOBBY);
  });

  it('restores a server-backed catalog and open question from the recovery cache', () => {
    const raw = makeServerState();
    const result = sanitizePersistedState(raw, 5000);

    expect(result.valid).toBe(true);
    expect(result.state.currentStage).toBe(STAGES.ARENA);
    expect(result.state.currentQuestion.questionId).toBe(SERVER_QUESTION.id);
    expect(result.state.currentQuestion.tileId).toBe(SERVER_TILE.id);
    expect(result.state.content.tiles).toHaveLength(1);
    expect(result.state.content.questions[SERVER_QUESTION.id].answer).toBe('جواب السيرفر');
    expect(result.state.server).toMatchObject({
      matchCode: 'srv-code',
      version: 4,
      status: 'active',
    });
  });

  it('drops the server match code when the cached state is a lobby', () => {
    const raw = makeServerState();
    raw.currentStage = STAGES.LOBBY;
    raw.currentQuestion = null;
    const result = sanitizePersistedState(raw);
    expect(result.state.server.matchCode).toBeNull();
    expect(result.state.server.status).toBe('idle');
  });
});
