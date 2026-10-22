import {
  BACKUP_BY_ID,
  POWER_BY_ID,
  QUESTION_BY_ID,
  SCHEMA_VERSION,
  TILE_BY_ID,
  TOTAL_PRIMARY_TILES,
} from '../data/mockData.js';
import {
  AVATARS,
  STAGES,
  TEAM_A_ID,
  TEAM_B_ID,
  TEAM_COLORS,
  TEAM_IDS,
} from './constants.js';
import { buildDraftOrder } from './draft.js';
import { PRIMARY_MS, TIMER_PHASES, createTimer } from './timer.js';

export function createDefaultTeams() {
  return [
    {
      id: TEAM_A_ID,
      name: 'فريق الصقور',
      color: 'cyan',
      avatar: 'falcon',
      score: 0,
    },
    {
      id: TEAM_B_ID,
      name: 'فريق الذيابة',
      color: 'pink',
      avatar: 'wolf',
      score: 0,
    },
  ];
}

export function createEmptyStats(teamIds = TEAM_IDS) {
  return Object.fromEntries(
    teamIds.map((teamId) => [
      teamId,
      {
        tilesWon: 0,
        successfulSteals: 0,
        powersUsed: 0,
        biggestSwing: 0,
        correctAnswers: 0,
      },
    ]),
  );
}

export function createInitialGameState() {
  return {
    schemaVersion: SCHEMA_VERSION,
    currentStage: STAGES.LOBBY,
    teams: createDefaultTeams(),
    coinToss: { result: null, completed: false },
    draft: { order: [], picks: [] },
    currentTurnTeamId: null,
    tileResults: {},
    currentQuestion: null,
    usedPowerIds: { [TEAM_A_ID]: [], [TEAM_B_ID]: [] },
    stats: createEmptyStats(),
    manualAdjustments: [],
    matchHistory: [],
    matchStartedAt: null,
    matchFinishedAt: null,
    settings: { muted: false },
    recoveryNotice: null,
    // كتالوج الفئات من الخادم واختيار ست فئات للمباراة.
    categories: { status: 'idle', items: [], error: null },
    selectedCategorySlugs: [],
    // ملفات اللاعبين وإسنادهم للفريقين (نطاق الصالة فقط، لا يُحفَظ).
    profiles: { status: 'idle', items: [], error: null },
    teamProfileIds: { [TEAM_A_ID]: [], [TEAM_B_ID]: [] },
    // مشاركو المباراة المؤكدون من الخادم.
    matchParticipants: [],
    // مصدر المحتوى: الخادم هو المرجع، والمحلي احتياطي/عرض فقط.
    server: {
      matchCode: null,
      version: 0,
      status: 'idle',
      winner: null,
      hostToken: null,
      online: true,
      error: null,
      pending: false,
      syncing: false,
    },
    content: { source: 'local', questions: {}, tiles: [], backups: [] },
  };
}

/** حالة مباراة جديدة بنفس الفريقين والإعدادات، مع تصفير كل شيء خاص بالمباراة. */
export function createFreshMatchState({ teams, settings } = {}) {
  const base = createInitialGameState();
  const safeTeams = Array.isArray(teams) && teams.length === 2
    ? teams.map((team) => ({ ...team, score: 0 }))
    : base.teams;
  return {
    ...base,
    teams: safeTeams,
    settings: settings ? { ...base.settings, ...settings } : base.settings,
  };
}

export function isActiveMatchStage(stage) {
  return stage === STAGES.DRAFT || stage === STAGES.BOARD || stage === STAGES.ARENA;
}

export function isSavedMatchResumable(state) {
  return Boolean(state && isActiveMatchStage(state.currentStage) && state.matchStartedAt);
}

export function countPlayedTiles(tileResults) {
  return Object.values(tileResults ?? {}).filter((result) => result?.played).length;
}

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function normalizeTeams(teams) {
  if (!Array.isArray(teams) || teams.length !== 2) return null;
  const ids = teams.map((team) => team?.id);
  if (ids[0] === ids[1] || !TEAM_IDS.every((id) => ids.includes(id))) return null;
  const colorIds = new Set(TEAM_COLORS.map((color) => color.id));
  const avatarIds = new Set(AVATARS.map((avatar) => avatar.id));
  const ordered = TEAM_IDS.map((id) => teams.find((team) => team.id === id));

  return ordered.map((team) => {
    const name = typeof team.name === 'string' ? team.name.trim().slice(0, 28) : '';
    return {
      id: team.id,
      name: name || (team.id === TEAM_A_ID ? 'فريق الصقر' : 'فريق ذيب'),
      color: colorIds.has(team.color) ? team.color : team.id === TEAM_A_ID ? 'cyan' : 'pink',
      avatar: avatarIds.has(team.avatar) ? team.avatar : team.id === TEAM_A_ID ? 'falcon' : 'wolf',
      score: isFiniteNumber(team.score) ? team.score : 0,
    };
  });
}

const SERVER_STATUSES = new Set(['idle', 'active', 'completed', 'abandoned']);

/**
 * كتالوج الخادم محفوظ كنسخة استرداد محلية: أسئلة الخانات الـ36 والاحتياط الستة.
 * أي عنصر ناقص يُسقط بهدوء حتى لا يفتح واجهة على سؤال غير موجود.
 */
function normalizeContent(raw) {
  const questions = {};
  if (raw?.questions && typeof raw.questions === 'object') {
    for (const [id, question] of Object.entries(raw.questions)) {
      if (!question || typeof question !== 'object') continue;
      if (typeof question.question !== 'string' || typeof question.answer !== 'string') continue;
      questions[id] = question;
    }
  }

  const tiles = [];
  const seen = new Set();
  if (Array.isArray(raw?.tiles)) {
    for (const tile of raw.tiles) {
      if (!tile || typeof tile.id !== 'string' || seen.has(tile.id)) continue;
      if (![200, 400, 600].includes(tile.points)) continue;
      if (typeof tile.categoryId !== 'string') continue;
      if (typeof tile.questionId !== 'string') continue;
      seen.add(tile.id);
      tiles.push({
        id: tile.id,
        categoryId: tile.categoryId,
        points: tile.points,
        questionId: tile.questionId,
        played: tile.played === true,
      });
    }
  }

  const backups = Array.isArray(raw?.backups)
    ? raw.backups.filter((backup) => backup && typeof backup.id === 'string')
    : [];

  return {
    source: tiles.length ? 'server' : 'local',
    questions,
    tiles,
    backups,
  };
}

function normalizeServer(raw) {
  const source = raw && typeof raw === 'object' ? raw : {};
  const matchCode =
    typeof source.matchCode === 'string' && source.matchCode.length > 0 && source.matchCode.length <= 64
      ? source.matchCode
      : null;
  const status = SERVER_STATUSES.has(source.status)
    ? source.status
    : matchCode
      ? 'active'
      : 'idle';
  const hostToken =
    typeof source.hostToken === 'string' &&
    source.hostToken.length >= 32 &&
    source.hostToken.length <= 128
      ? source.hostToken
      : null;
  return {
    matchCode,
    version: isFiniteNumber(source.version) && source.version >= 0 ? Math.round(source.version) : 0,
    status: matchCode ? status : 'idle',
    winner: ['team1', 'team2', 'tie'].includes(source.winner) ? source.winner : null,
    hostToken: matchCode ? hostToken : null,
    online: source.online !== false,
    error: null,
    pending: false,
    syncing: false,
  };
}

function normalizeTimer(timer, now = Date.now(), defaultRunning = false) {
  if (!timer || typeof timer !== 'object') {
    return {
      ...createTimer(),
      running: defaultRunning,
      startedAt: defaultRunning ? now : null,
    };
  }
  let elapsedMs = isFiniteNumber(timer.elapsedMs) ? Math.max(0, timer.elapsedMs) : null;
  // ترحيل لطيف من النسخة القديمة ذات الـ60 ثانية/العد التنازلي.
  if (elapsedMs === null && isFiniteNumber(timer.remainingMs)) {
    elapsedMs = Math.max(0, PRIMARY_MS - timer.remainingMs);
  }
  if (elapsedMs === null && isFiniteNumber(timer.deadline)) {
    elapsedMs = Math.max(0, PRIMARY_MS - Math.max(0, timer.deadline - now));
  }
  const wasClosed = timer.phase === TIMER_PHASES.DONE;
  const running = wasClosed ? defaultRunning : timer.running === true;
  return {
    phase: TIMER_PHASES.PRIMARY,
    running,
    elapsedMs: elapsedMs ?? 0,
    startedAt: running
      ? isFiniteNumber(timer.startedAt)
        ? timer.startedAt
        : now
      : null,
  };
}

function normalizeQuestion(raw, teams, pickedPowerIds, now = Date.now(), catalog = null) {
  if (!raw || typeof raw !== 'object') return null;
  const tilesById = catalog?.tilesById ?? TILE_BY_ID;
  const questionsById = catalog?.questions ?? QUESTION_BY_ID;
  const tile = tilesById[raw.tileId];
  if (!tile) return null;
  if (!teams.some((team) => team.id === raw.activeTeamId)) return null;

  let payload = questionsById[raw.questionId];
  if (!payload && BACKUP_BY_ID[raw.questionId]) payload = BACKUP_BY_ID[raw.questionId];
  if (!payload) {
    payload = questionsById[tile.questionId];
  }
  if (!payload) return null;

  // لو كان السؤال احتياطيًا، لازم تكون فئته وقيمته متوافقة مع الخانة الأصلية.
  if (BACKUP_BY_ID[raw.questionId]) {
    if (
      !payload.compatibleCategoryIds.includes(tile.categoryId) ||
      !payload.compatiblePoints.includes(tile.points)
    ) {
      return null;
    }
  }

  const usedBackupIds = Array.isArray(raw.usedBackupIds)
    ? raw.usedBackupIds.filter((id) => Boolean(BACKUP_BY_ID[id]))
    : [];
  const activePowers = Array.isArray(raw.activePowers)
    ? Array.from(
        new Set(
          raw.activePowers
            .map((entry) => (typeof entry === 'string' ? entry : entry?.powerId))
            .filter((powerId) => Boolean(POWER_BY_ID[powerId])),
        ),
      )
    : [];

  const revealed = raw.revealed === true;
  return {
    tileId: tile.id,
    questionId: payload.id,
    categoryId: tile.categoryId,
    points: tile.points,
    sourceBackupId: BACKUP_BY_ID[payload.id] ? payload.id : null,
    activeTeamId: raw.activeTeamId,
    originalActiveTeamId: teams.some((team) => team.id === raw.originalActiveTeamId)
      ? raw.originalActiveTeamId
      : raw.activeTeamId,
    stolenByTeamId: teams.some((team) => team.id === raw.stolenByTeamId)
      ? raw.stolenByTeamId
      : null,
    sessionStartedAt: isFiniteNumber(raw.sessionStartedAt) ? raw.sessionStartedAt : now,
    revealed,
    revealedAt: isFiniteNumber(raw.revealedAt) ? raw.revealedAt : null,
    activePowers,
    usedBackupIds,
    noiseUntil: isFiniteNumber(raw.noiseUntil) ? raw.noiseUntil : null,
    wrongGuesses: isFiniteNumber(raw.wrongGuesses)
      ? Math.min(2, Math.max(0, Math.round(raw.wrongGuesses)))
      : 0,
    twoAnswerExtensionUsed: raw.twoAnswerExtensionUsed === true,
    timer: normalizeTimer(raw.timer, now, !revealed),
    pickedPowerIdsAtOpen: Array.isArray(raw.pickedPowerIdsAtOpen)
      ? raw.pickedPowerIdsAtOpen.filter((id) => pickedPowerIds.has(id))
      : [],
  };
}

function normalizeTileResults(raw, tilesById = TILE_BY_ID) {
  if (!raw || typeof raw !== 'object') return {};
  const results = {};
  for (const [tileId, result] of Object.entries(raw)) {
    const tile = tilesById[tileId];
    if (!tile || result?.played !== true) continue;
    results[tileId] = {
      ...result,
      played: true,
      tileId,
      winningTeamId:
        result.winningTeamId && TEAM_IDS.includes(result.winningTeamId)
          ? result.winningTeamId
          : null,
      outcome: result.outcome ?? 'nobody',
      basePoints: tile.points,
      deltas:
        result.deltas && typeof result.deltas === 'object' ? result.deltas : {},
      ledger: Array.isArray(result.ledger) ? result.ledger : [],
      activePowers: Array.isArray(result.activePowers) ? result.activePowers : [],
      resolvedAt: isFiniteNumber(result.resolvedAt) ? result.resolvedAt : null,
      questionId: typeof result.questionId === 'string' ? result.questionId : null,
    };
  }
  return results;
}

function normalizeStats(raw, teams) {
  const base = createEmptyStats(teams.map((team) => team.id));
  if (!raw || typeof raw !== 'object') return base;
  for (const team of teams) {
    const source = raw[team.id];
    if (!source || typeof source !== 'object') continue;
    base[team.id] = {
      tilesWon: isFiniteNumber(source.tilesWon) ? source.tilesWon : 0,
      successfulSteals: isFiniteNumber(source.successfulSteals) ? source.successfulSteals : 0,
      powersUsed: isFiniteNumber(source.powersUsed) ? source.powersUsed : 0,
      biggestSwing: isFiniteNumber(source.biggestSwing) ? source.biggestSwing : 0,
      correctAnswers: isFiniteNumber(source.correctAnswers) ? source.correctAnswers : 0,
    };
  }
  return base;
}

function normalizePicks(rawPicks, teams, order) {
  if (!Array.isArray(rawPicks)) return [];
  const picks = [];
  const seenByTeam = Object.fromEntries(teams.map((team) => [team.id, new Set()]));
  for (const pick of rawPicks.slice(0, 6)) {
    if (!pick || !POWER_BY_ID[pick.powerId]) return null;
    if (!teams.some((team) => team.id === pick.teamId)) return null;
    if (order[picks.length] !== pick.teamId) return null;
    if (seenByTeam[pick.teamId]?.has(pick.powerId)) return null;
    seenByTeam[pick.teamId].add(pick.powerId);
    picks.push({ teamId: pick.teamId, powerId: pick.powerId, pickedAt: pick.pickedAt ?? null });
  }
  return picks;
}

/**
 * ينظّف أي حالة محفوظة قبل دمجها مع المتجر. أي خلل جوهري يعيد حالة لوبي جديدة
 * مع إشعار غير معطّل بدل الانهيار أو استئناف مباراة مكسورة.
 */
export function sanitizePersistedState(raw, now = Date.now()) {
  const initial = createInitialGameState();
  const fail = (notice) => ({ valid: false, state: initial, notice });
  if (!raw || typeof raw !== 'object') return fail('');

  const source = raw.state && typeof raw.state === 'object' ? raw.state : raw;
  if (![STAGES.LOBBY, STAGES.DRAFT, STAGES.BOARD, STAGES.ARENA, STAGES.PODIUM].includes(source.currentStage)) {
    return fail('الملف المحفوظ غير مفهوم، بدأنا مباراة جديدة بأمان.');
  }
  if (source.schemaVersion !== undefined && source.schemaVersion > SCHEMA_VERSION) {
    return fail('الملف المحفوظ من إصدار أحدث، ما نقدر نستأنفه. بدأنا من جديد.');
  }

  const teams = normalizeTeams(source.teams);
  if (!teams) return fail('بيانات الفرق المحفوظة غير صالحة، بدأنا مباراة جديدة.');

  const coinToss = {
    result:
      source.coinToss?.result && TEAM_IDS.includes(source.coinToss.result)
        ? source.coinToss.result
        : null,
    completed: source.coinToss?.completed === true && Boolean(source.coinToss?.result),
  };
  if (coinToss.result) coinToss.completed = true;

  let order = [];
  if (coinToss.result) {
    const other = coinToss.result === TEAM_A_ID ? TEAM_B_ID : TEAM_A_ID;
    order = buildDraftOrder(coinToss.result, other);
  }
  const picks = order.length ? normalizePicks(source.draft?.picks ?? [], teams, order) : [];
  if (picks === null) {
    return fail('اختيارات السحب المحفوظة غير متوافقة، بدأنا من جديد.');
  }

  let currentTurnTeamId =
    source.currentTurnTeamId && TEAM_IDS.includes(source.currentTurnTeamId)
      ? source.currentTurnTeamId
      : null;

  const pickedPowerIds = new Set(picks.map((pick) => pick.powerId));
  const usedPowerIds = {
    [TEAM_A_ID]: [],
    [TEAM_B_ID]: [],
  };
  for (const teamId of TEAM_IDS) {
    const draftedForTeam = picks.filter((pick) => pick.teamId === teamId).map((pick) => pick.powerId);
    const rawUsed = Array.isArray(source.usedPowerIds?.[teamId]) ? source.usedPowerIds[teamId] : [];
    usedPowerIds[teamId] = Array.from(
      new Set(rawUsed.filter((powerId) => pickedPowerIds.has(powerId) && draftedForTeam.includes(powerId))),
    );
  }

  // كتالوج الخادم يُستعاد من نسخة الاسترداد حتى تظل الخانات والأسئلة معروفة.
  const content = normalizeContent(source.content);
  const tilesById = { ...TILE_BY_ID };
  for (const tile of content.tiles) tilesById[tile.id] = tile;
  const questionsById = { ...QUESTION_BY_ID, ...content.questions };
  const server = normalizeServer(source.server);

  const tileResults = normalizeTileResults(source.tileResults, tilesById);
  let currentQuestion = null;
  if (source.currentQuestion) {
    currentQuestion = normalizeQuestion(source.currentQuestion, teams, pickedPowerIds, now, {
      tilesById,
      questions: questionsById,
    });
    if (currentQuestion && tileResults[currentQuestion.tileId]) {
      currentQuestion = null;
    }
  }

  let stage = source.currentStage;
  let notice = '';
  if (stage === STAGES.ARENA && !currentQuestion) {
    stage = STAGES.BOARD;
    notice = 'جلسة السؤال المحفوظة كانت ناقصة، رجعناك للوحة بأمان.';
  }
  if ((stage === STAGES.BOARD || stage === STAGES.ARENA || stage === STAGES.DRAFT) && !currentTurnTeamId) {
    currentTurnTeamId = coinToss.result ?? TEAM_A_ID;
  }
  if (stage === STAGES.DRAFT && !coinToss.completed) {
    stage = STAGES.LOBBY;
    notice = 'بيانات القرعة ناقصة، رجعناك لصالة البداية.';
  }
  if (stage === STAGES.PODIUM && countPlayedTiles(tileResults) < TOTAL_PRIMARY_TILES) {
    stage = STAGES.BOARD;
    notice = 'المنصة ما تنفتح إلا بعد كل الخانات، رجعناك للوحة.';
  }
  if (stage === STAGES.BOARD && countPlayedTiles(tileResults) === TOTAL_PRIMARY_TILES) {
    stage = STAGES.PODIUM;
    currentQuestion = null;
  }
  if (stage === STAGES.LOBBY || !server.matchCode) {
    server.matchCode = null;
    server.version = 0;
    server.status = 'idle';
    server.winner = null;
    server.hostToken = null;
  } else if (stage === STAGES.PODIUM && server.status === 'active') {
    // المباراة المحفوظة انتهت شكليًا قبل وصول حالة الخادم؛ المزامنة تصحّحها.
    server.status = 'completed';
  }

  const stats = normalizeStats(source.stats, teams);
  const manualAdjustments = Array.isArray(source.manualAdjustments)
    ? source.manualAdjustments
        .filter(
          (entry) =>
            entry &&
            TEAM_IDS.includes(entry.teamId) &&
            isFiniteNumber(entry.amount) &&
            isFiniteNumber(entry.at),
        )
        .slice(-200)
    : [];
  const matchHistory = Array.isArray(source.matchHistory)
    ? source.matchHistory.filter((entry) => entry && typeof entry === 'object').slice(-36)
    : [];

  const sanitized = {
    ...initial,
    schemaVersion: SCHEMA_VERSION,
    currentStage: stage,
    teams,
    coinToss,
    draft: { order, picks },
    currentTurnTeamId,
    tileResults,
    currentQuestion,
    usedPowerIds,
    stats,
    manualAdjustments,
    matchHistory,
    matchStartedAt: isFiniteNumber(source.matchStartedAt) ? source.matchStartedAt : null,
    matchFinishedAt: isFiniteNumber(source.matchFinishedAt) ? source.matchFinishedAt : null,
    settings: { muted: source.settings?.muted === true },
    server,
    content,
    recoveryNotice: notice || null,
  };

  return { valid: true, state: sanitized, notice: notice || null };
}

export function stageLabel(stage) {
  return (
    {
      [STAGES.LOBBY]: 'صالة البداية',
      [STAGES.DRAFT]: 'سحب القوى',
      [STAGES.BOARD]: 'لوحة البث',
      [STAGES.ARENA]: 'ساحة السؤال',
      [STAGES.PODIUM]: 'المنصة',
    }[stage] ?? stage
  );
}
