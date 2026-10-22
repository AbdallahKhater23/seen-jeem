/**
 * محوّل رفيع بين API الخلفي (snake_case) وعقد الواجهة الحالي (camelCase).
 *
 * هذا الملف لا يعيد كتابة الواجهة ولا يستورد Zustand. وظيفته توثيق الحدود
 * وتوفير دوال قابلة للاختبار. أي استدعاء تغيير يحتاج Idempotency-Key.
 *
 * فروق تعاقدية مقصودة:
 * - category slug الخلفي `spotdiff` ← الواجهة `spot`.
 * - question type الخلفي `text` ← الواجهة `standard`.
 * - outcomes الخلفية `team1|team2|none` ← الواجهة `active_team|defending_team|nobody`.
 * - team keys الخلفية `team1|team2` ← الواجهة `team-falcons|team-wolves`.
 * - power ids متطابقة: pit, trap, steal, two_answers, noise, double, switch.
 *   `rest` و`time_break` ما زالا مقبولين من الخلفي للتوافق مع النسخ الأقدم.
 */

export const TEAM_A_ID = 'team-falcons';
export const TEAM_B_ID = 'team-wolves';
export const TEAM_KEY = Object.freeze({ team1: TEAM_A_ID, team2: TEAM_B_ID });
export const BACKEND_TEAM_KEY = Object.freeze({ [TEAM_A_ID]: 'team1', [TEAM_B_ID]: 'team2' });

export const BACKEND_CATEGORY_TO_FRONTEND = Object.freeze({
  flags: 'flags',
  capitals: 'capitals',
  football: 'football',
  ucl: 'ucl',
  worldcup: 'worldcup',
  career: 'career',
  clubs: 'clubs',
  arab_ftbl: 'arab_ftbl',
  numbers: 'numbers',
  riddles: 'riddles',
  general: 'general',
  spotdiff: 'spot',
  quran: 'quran',
  nicknames: 'nicknames',
  technology: 'technology',
  videogames: 'videogames',
  matchstick: 'matchstick',
  reverse: 'reverse',
});

export const FRONTEND_CATEGORY_TO_BACKEND = Object.freeze(
  Object.fromEntries(
    Object.entries(BACKEND_CATEGORY_TO_FRONTEND).map(([backend, frontend]) => [frontend, backend]),
  ),
);

export const BACKEND_TYPE_TO_FRONTEND = Object.freeze({
  text: 'standard',
  flag: 'flag',
  career: 'career',
  spot_diff: 'spot_diff',
});

export const FRONTEND_TYPE_TO_BACKEND = Object.freeze({
  standard: 'text',
  flag: 'flag',
  career: 'career',
  spot_diff: 'spot_diff',
});

export const ALL_CATEGORY_SLUGS = Object.freeze(Object.keys(BACKEND_CATEGORY_TO_FRONTEND));

/** الاختيار الاحتياطي إن تعذّر تحميل كتالوج الخادم (توافق مع النسخة القديمة). */
export const MATCH_CATEGORY_SLUGS = Object.freeze([
  'flags',
  'football',
  'worldcup',
  'career',
  'riddles',
  'spotdiff',
]);

export function toFrontendCategory(slug) {
  return BACKEND_CATEGORY_TO_FRONTEND[slug] ?? slug;
}

export function toBackendCategorySlug(slug) {
  return FRONTEND_CATEGORY_TO_BACKEND[slug] ?? slug;
}

export class ApiError extends Error {
  constructor(status, payload) {
    const body = payload?.error ?? {};
    super(body.message || `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code || 'UNKNOWN_ERROR';
    this.details = body.details || {};
  }
}

export function makeIdempotencyKey(prefix = 'ui') {
  const random =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}:${random}`;
}

export function toFrontendTeamId(teamKey) {
  return TEAM_KEY[teamKey] ?? null;
}

export function toFrontendTileKey(tileKey) {
  return tileKey?.startsWith('spotdiff-') ? `spot-${tileKey.slice('spotdiff-'.length)}` : tileKey;
}

export function toBackendTileKey(tileKey) {
  return tileKey?.startsWith('spot-') ? `spotdiff-${tileKey.slice('spot-'.length)}` : tileKey;
}

export function toBackendTeamKey(teamId) {
  return BACKEND_TEAM_KEY[teamId] ?? null;
}

export function toFrontendOutcome(outcome, activeTeamId) {
  if (outcome === 'none') return 'nobody';
  return toFrontendTeamId(outcome) === activeTeamId ? 'active_team' : 'defending_team';
}

export function toBackendOutcome(outcome, activeTeamId) {
  if (outcome === 'nobody') return 'none';
  if (outcome === 'active_team') return toBackendTeamKey(activeTeamId);
  if (outcome === 'defending_team') {
    return activeTeamId === TEAM_A_ID ? 'team2' : 'team1';
  }
  throw new Error(`outcome غير معروف: ${outcome}`);
}

export function toFrontendQuestion(question, tileKey, slotPoints = question.difficulty) {
  const matchstickPayload = question.payload?.kind === 'matchstick' ? question.payload : null;
  const reversePayload = question.payload?.kind === 'reverse' ? question.payload : null;
  const mapped = {
    id: `backend-${question.id}`,
    tileId: tileKey,
    categoryId: BACKEND_CATEGORY_TO_FRONTEND[question.category_slug] ?? question.category_slug,
    categorySlug: BACKEND_CATEGORY_TO_FRONTEND[question.category_slug] ?? question.category_slug,
    categoryName: question.category_name,
    points: slotPoints,
    type: matchstickPayload
      ? 'matchstick'
      : reversePayload
        ? 'reverse'
        : BACKEND_TYPE_TO_FRONTEND[question.question_type] ?? 'standard',
    question: question.question_text,
    answer: question.answer_text,
    tolerance: question.tolerance,
    explanation: question.explanation ?? '',
    visual: question.visual ?? null,
    source: {
      name: question.source_name,
      url: question.source_url,
      checkedAt: question.source_checked_at,
      license: question.source_license,
      claim: question.source_claim,
      origin: question.content_origin,
    },
  };
  if (question.question_type === 'flag') {
    mapped.iso2 = question.flag_code;
  }
  if (matchstickPayload) {
    mapped.matchstick = matchstickPayload;
  }
  if (reversePayload) {
    mapped.reverse = reversePayload;
  }
  if (question.question_type === 'career') {
    mapped.career = question.payload?.career ?? [];
  }
  if (question.question_type === 'spot_diff') {
    mapped.sceneId = question.payload?.sceneId;
    mapped.sceneVersion = question.payload?.sceneVersion;
    mapped.variantSeed = question.payload?.variantSeed;
    mapped.combo = question.payload?.combo ?? [];
    mapped.anchors = question.payload?.anchors ?? [];
    mapped.mutations = question.payload?.mutations ?? [];
    mapped.differences = question.payload?.differences ?? [];
  }
  mapped.factGroupId = question.fact_group_id ?? null;
  return mapped;
}

export function toFrontendTile(tile) {
  return {
    id: toFrontendTileKey(tile.tile_key),
    categoryId: BACKEND_CATEGORY_TO_FRONTEND[tile.category_slug] ?? tile.category_slug,
    points: tile.difficulty,
    questionId: `backend-${tile.question.id}`,
    played: tile.status === 'played',
    openedAt: tile.opened_at ?? null,
    revealedAt: tile.revealed_at ?? null,
    activeTeamId: toFrontendTeamId(tile.active_team),
    noiseUntil: tile.noise_until ?? null,
    activePowers: tile.powers_applied ?? [],
    result: tile.status === 'played'
      ? {
          played: true,
          winningTeamId: tile.outcome === 'none' ? null : toFrontendTeamId(tile.outcome),
          deltas: {
            [TEAM_A_ID]: tile.delta_team1,
            [TEAM_B_ID]: tile.delta_team2,
          },
          activePowers: tile.powers_applied,
        }
      : null,
  };
}

export function toFrontendLedgerEntry(entry, activeTeamId) {
  let reason;
  if (entry.power === 'pit') reason = 'pit_deduction';
  else if (entry.power === 'trap') reason = 'trap_deduction';
  else if (entry.power === 'double') reason = entry.delta > 0 ? 'double_win' : 'double_loss';
  else reason = entry.team === toBackendTeamKey(activeTeamId) ? 'base_win' : 'steal_win';
  return {
    teamId: toFrontendTeamId(entry.team),
    delta: entry.delta,
    reason,
    reasonLabel: entry.reason,
    powerId: entry.power ?? null,
  };
}

/**
 * Converts a resolve response into the shape the arena can commit to Zustand.
 * The backend alternates turns after every resolve, so the active team from the
 * request is the opposite of `match.current_turn` in the response.
 */
export function toFrontendResolveResult(result) {
  const nextTurnTeamId = toFrontendTeamId(result.match.current_turn);
  const activeTeamId = nextTurnTeamId === TEAM_A_ID ? TEAM_B_ID : TEAM_A_ID;
  const defendingTeamId = nextTurnTeamId;
  const backendOutcome = result.tile.outcome;
  const outcome = backendOutcome
    ? toFrontendOutcome(backendOutcome, activeTeamId)
    : null;
  const ledger = (result.score_ledger ?? []).map((entry) =>
    toFrontendLedgerEntry(entry, activeTeamId),
  );
  const deltas = {
    [TEAM_A_ID]: result.tile.delta_team1,
    [TEAM_B_ID]: result.tile.delta_team2,
  };
  return {
    match: {
      status: result.match.status,
      winner: result.match.winner,
      currentTurnTeamId: nextTurnTeamId,
      scores: {
        [TEAM_A_ID]: result.match.score_team1,
        [TEAM_B_ID]: result.match.score_team2,
      },
      version: result.match.version,
    },
    tile: toFrontendTile(result.tile),
    question: toFrontendQuestion(
      result.tile.question,
      toFrontendTileKey(result.tile.tile_key),
      result.tile.difficulty,
    ),
    tileResult: {
      played: true,
      tileId: toFrontendTileKey(result.tile.tile_key),
      questionId: `backend-${result.tile.question.id}`,
      sourceBackupId: null,
      categoryId: BACKEND_CATEGORY_TO_FRONTEND[result.tile.category_slug] ?? result.tile.category_slug,
      basePoints: result.tile.difficulty,
      activeTeamId,
      defendingTeamId,
      outcome,
      winningTeamId: backendOutcome && backendOutcome !== 'none' ? toFrontendTeamId(backendOutcome) : null,
      deltas,
      ledger,
      activePowers: result.tile.powers_applied ?? [],
      resolvedAt: result.tile.answered_at,
    },
    scoreLedger: ledger,
    idempotentReplay: Boolean(result.idempotent_replay),
  };
}

/** Maps a reroll response; the backup question is already on `tile`. */
export function toFrontendRerollResult(result) {
  return {
    match: {
      status: result.match.status,
      currentTurnTeamId: toFrontendTeamId(result.match.current_turn),
      scores: {
        [TEAM_A_ID]: result.match.score_team1,
        [TEAM_B_ID]: result.match.score_team2,
      },
      version: result.match.version,
    },
    tile: toFrontendTile(result.tile),
    question: toFrontendQuestion(
      result.tile.question,
      toFrontendTileKey(result.tile.tile_key),
      result.tile.difficulty,
    ),
    backupUsed: result.backup_used,
    idempotentReplay: Boolean(result.idempotent_replay),
  };
}

export function toFrontendDraft(draft) {
  if (!draft) return null;
  return {
    order: (draft.order ?? []).map(toFrontendTeamId),
    picks: (draft.picks ?? []).map((pick) => ({
      teamId: toFrontendTeamId(pick.team),
      powerId: pick.power_id,
      pickIndex: pick.pick_index,
      pickedAt: pick.drafted_at ?? null,
      usedAt: pick.used_at ?? null,
      usedTileId: pick.used_tile_key ? toFrontendTileKey(pick.used_tile_key) : null,
    })),
    currentTeamId: toFrontendTeamId(draft.current_team),
    complete: Boolean(draft.complete),
    remaining: draft.remaining ?? 0,
  };
}

export function toFrontendSession(session) {
  return {
    openedAt: session?.opened_at ?? null,
    revealedAt: session?.revealed_at ?? null,
    activeTeamId: toFrontendTeamId(session?.active_team),
    noiseUntil: session?.noise_until ?? null,
  };
}

function toFrontendMatchState(match) {
  return {
    status: match.status,
    winner: match.winner,
    currentTurnTeamId: toFrontendTeamId(match.current_turn),
    scores: {
      [TEAM_A_ID]: match.score_team1,
      [TEAM_B_ID]: match.score_team2,
    },
    version: match.version,
  };
}

/** Maps open/reveal responses, where the tile carries the authoritative session. */
export function toFrontendTileSessionResult(result) {
  return {
    match: toFrontendMatchState(result.match),
    tile: toFrontendTile(result.tile),
    question: toFrontendQuestion(
      result.tile.question,
      toFrontendTileKey(result.tile.tile_key),
      result.tile.difficulty,
    ),
    session: result.session ? toFrontendSession(result.session) : null,
    idempotentReplay: Boolean(result.idempotent_replay),
  };
}

/** Maps a draft pick response. */
export function toFrontendDraftResult(result) {
  return {
    match: toFrontendMatchState(result.match),
    draft: toFrontendDraft(result.draft),
    pick: result.pick
      ? {
          teamId: toFrontendTeamId(result.pick.team),
          powerId: result.pick.power_id,
          pickIndex: result.pick.pick_index,
          pickedAt: result.pick.drafted_at ?? null,
        }
      : null,
    idempotentReplay: Boolean(result.idempotent_replay),
  };
}

/** Maps a server power activation, including a switch reroll. */
export function toFrontendActivationResult(result) {
  const activation = result.activation ?? {};
  return {
    match: toFrontendMatchState(result.match),
    tile: toFrontendTile(result.tile),
    question: toFrontendQuestion(
      result.tile.question,
      toFrontendTileKey(result.tile.tile_key),
      result.tile.difficulty,
    ),
    activation: {
      powerId: activation.power_id,
      teamId: toFrontendTeamId(activation.team),
      activatedAt: activation.activated_at ?? null,
      elapsedMs: activation.elapsed_ms ?? 0,
      activeTeamId: toFrontendTeamId(activation.active_team),
      noiseUntil: activation.noise_until ?? null,
      switched: Boolean(activation.switched),
    },
    backupUsed: result.backup_used ?? null,
    idempotentReplay: Boolean(result.idempotent_replay),
  };
}

export function toFrontendBackup(tile) {
  const question = toFrontendQuestion(tile.question, toFrontendTileKey(tile.tile_key));
  return {
    id: tile.tile_key,
    backupKey: tile.tile_key,
    type: question.type,
    question: question.question,
    answer: question.answer,
    tolerance: question.tolerance,
    explanation: question.explanation,
    status: tile.status,
    compatibleCategoryIds: tile.compatible_categories.map(
      (slug) => BACKEND_CATEGORY_TO_FRONTEND[slug] ?? slug,
    ),
    compatiblePoints: tile.compatible_difficulties,
    source: question.source,
  };
}

export function toFrontendParticipant(entry) {
  if (!entry) return null;
  return {
    userId: entry.user_id,
    username: entry.username ?? null,
    displayName: entry.display_name ?? '',
    kind: entry.kind ?? 'named',
    teamId: toFrontendTeamId(entry.team),
  };
}

export function toFrontendBoard(board) {
  const questions = {};
  const tiles = [];
  for (const tile of board.tiles) {
    const question = toFrontendQuestion(
      tile.question,
      toFrontendTileKey(tile.tile_key),
      tile.difficulty,
    );
    questions[question.id] = question;
    tiles.push(toFrontendTile(tile));
  }
  return {
    server: {
      matchCode: board.match.match_code,
      version: board.match.version,
      // يُكشف مرة واحدة في رد الإنشاء فقط؛ القراءات لا تعيده أبدًا.
      hostToken: board.host_token ?? null,
    },
    match: {
      status: board.match.status,
      winner: board.match.winner,
      coinTossWinner: toFrontendTeamId(board.match.coin_toss_winner),
    },
    selectedCategories: (board.match.selected_categories ?? []).map(toFrontendCategory),
    teams: [
      {
        id: TEAM_A_ID,
        name: board.match.team1_name,
        score: board.match.score_team1,
        color: 'cyan',
        avatar: 'falcon',
      },
      {
        id: TEAM_B_ID,
        name: board.match.team2_name,
        score: board.match.score_team2,
        color: 'pink',
        avatar: 'wolf',
      },
    ],
    currentTurnTeamId: toFrontendTeamId(board.match.current_turn),
    questions,
    tiles,
    backups: board.backups.map(toFrontendBackup),
    draft: toFrontendDraft(board.draft),
    participants: (board.participants ?? []).map(toFrontendParticipant).filter(Boolean),
  };
}

export function createApiClient({ baseUrl = '/api/v1', fetchImpl = fetch } = {}) {
  // توكن المضيف يخص شاشة التلفاز وحدها؛ كل عمليات التغيير تحمله تلقائيًا.
  let hostToken = null;
  async function request(path, { method = 'GET', body, key, hostToken: callToken, headers = {} } = {}) {
    const effectiveToken = callToken === undefined ? hostToken : callToken;
    const response = await fetchImpl(`${baseUrl}${path}`, {
      method,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'SeenJeem',
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(key ? { 'Idempotency-Key': key } : {}),
        ...(effectiveToken ? { 'X-Host-Token': effectiveToken } : {}),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = null;
    }
    if (!response.ok) {
      if (response.status === 401 && payload?.error?.code === 'LOGIN_REQUIRED' && typeof window !== 'undefined') {
        window.dispatchEvent(new Event('seenjeem:session-expired'));
      }
      throw new ApiError(response.status, payload);
    }
    if (method === 'POST' && /\/(open|reroll|resolve)$/.test(path) && typeof window !== 'undefined') {
      window.dispatchEvent(new Event('seenjeem:history-updated'));
    }
    return payload;
  }

  return {
    setHostToken: (token) => {
      hostToken = typeof token === 'string' && token.length > 0 ? token : null;
    },
    health: () => request('/health'),
    categories: () => request('/categories'),
    listUsers: () => request('/users'),
    createUser: ({ username, displayName, key = makeIdempotencyKey('profile') }) =>
      request('/users', {
        method: 'POST',
        key,
        body: { username, display_name: displayName ?? username },
      }),
    registerInstallation: ({ key = makeIdempotencyKey('install') } = {}) =>
      request('/installations/register', { method: 'POST', key }),
    installationMe: ({ installToken } = {}) =>
      request('/installations/me', {
        headers: installToken ? { 'X-Install-Token': installToken } : {},
      }),
    createMatch: ({
      team1Name,
      team2Name,
      coinTossWinner,
      startingTurn,
      categorySlugs,
      team1UserIds = [],
      team2UserIds = [],
      installToken,
      key = makeIdempotencyKey('create'),
    }) =>
      request('/matches', {
        method: 'POST',
        key,
        headers: { 'X-Account-Required': '1', ...(installToken ? { 'X-Install-Token': installToken } : {}) },
        body: {
          team1_name: team1Name,
          team2_name: team2Name,
          starting_turn: startingTurn ? toBackendTeamKey(startingTurn) : null,
          coin_toss_winner: coinTossWinner ? toBackendTeamKey(coinTossWinner) : null,
          category_slugs: (categorySlugs?.length ? categorySlugs : [...MATCH_CATEGORY_SLUGS]).map(
            toBackendCategorySlug,
          ),
          team1_user_ids: team1UserIds,
          team2_user_ids: team2UserIds,
        },
      }),
    poolSync: ({ source = 'restcountries' } = {}) =>
      request(`/pool/sync?source=${encodeURIComponent(source)}`, { method: 'POST' }),
    poolSyncStatus: () => request('/pool/sync'),
    getMatch: (matchCode) => request(`/matches/${encodeURIComponent(matchCode)}`),
    draftPower: ({
      matchCode,
      powerId,
      expectedVersion,
      key = makeIdempotencyKey('draft'),
    }) =>
      request(`/matches/${encodeURIComponent(matchCode)}/draft/picks`, {
        method: 'POST',
        key,
        body: { power_id: powerId, expected_version: expectedVersion },
      }),
    openTile: ({ matchCode, tileKey, expectedVersion, key = makeIdempotencyKey('open') }) =>
      request(
        `/matches/${encodeURIComponent(matchCode)}/tiles/${encodeURIComponent(toBackendTileKey(tileKey))}/open`,
        { method: 'POST', key, body: { expected_version: expectedVersion } },
      ),
    revealTile: ({ matchCode, tileKey, expectedVersion, key = makeIdempotencyKey('reveal') }) =>
      request(
        `/matches/${encodeURIComponent(matchCode)}/tiles/${encodeURIComponent(toBackendTileKey(tileKey))}/reveal`,
        { method: 'POST', key, body: { expected_version: expectedVersion } },
      ),
    abandonTile: ({ matchCode, tileKey, expectedVersion, key = makeIdempotencyKey('abandon-tile') }) =>
      request(
        `/matches/${encodeURIComponent(matchCode)}/tiles/${encodeURIComponent(toBackendTileKey(tileKey))}/abandon`,
        { method: 'POST', key, body: { expected_version: expectedVersion } },
      ),
    activatePower: ({
      matchCode,
      tileKey,
      powerId,
      teamId,
      expectedVersion,
      key = makeIdempotencyKey('power'),
    }) =>
      request(
        `/matches/${encodeURIComponent(matchCode)}/tiles/${encodeURIComponent(toBackendTileKey(tileKey))}/powers/${encodeURIComponent(powerId)}/activate`,
        {
          method: 'POST',
          key,
          body: { team: toBackendTeamKey(teamId), expected_version: expectedVersion },
        },
      ),
    resolve: ({
      matchCode,
      tileKey,
      outcome,
      activeTeamId,
      powersApplied = [],
      expectedVersion,
      key = makeIdempotencyKey('resolve'),
    }) =>
      request(`/matches/${encodeURIComponent(matchCode)}/tiles/${encodeURIComponent(toBackendTileKey(tileKey))}/resolve`, {
        method: 'POST',
        key,
        body: {
          outcome: toBackendOutcome(outcome, activeTeamId),
          powers_applied: powersApplied,
          expected_version: expectedVersion,
        },
      }),
    reroll: ({ matchCode, tileKey, expectedVersion, key = makeIdempotencyKey('reroll') }) =>
      request(`/matches/${encodeURIComponent(matchCode)}/tiles/${encodeURIComponent(toBackendTileKey(tileKey))}/reroll`, {
        method: 'POST',
        key,
        body: { expected_version: expectedVersion },
      }),
    adjustScore: ({ matchCode, teamId, delta, reason, expectedVersion, key = makeIdempotencyKey('adjust') }) =>
      request(`/matches/${encodeURIComponent(matchCode)}/score-adjustments`, {
        method: 'POST',
        key,
        body: {
          team: toBackendTeamKey(teamId),
          delta,
          reason,
          expected_version: expectedVersion,
        },
      }),
    abandon: ({ matchCode, expectedVersion, key = makeIdempotencyKey('abandon') }) =>
      request(`/matches/${encodeURIComponent(matchCode)}/abandon`, {
        method: 'POST',
        key,
        body: { expected_version: expectedVersion },
      }),
    events: ({ matchCode, limit = 50, beforeId }) => {
      const query = new URLSearchParams({ limit: String(limit) });
      if (beforeId) query.set('before_id', String(beforeId));
      return request(`/matches/${encodeURIComponent(matchCode)}/events?${query}`);
    },
  };
}
