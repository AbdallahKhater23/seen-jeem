import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  NOISE_DURATION_MS,
  POWERS,
  POWER_BY_ID,
  QUESTION_BY_ID,
  TILE_BY_ID,
  TOTAL_PRIMARY_TILES,
  getCompatibleBackups,
  getSessionQuestion,
} from '../data/mockData.js';
import {
  STAGES,
  STORAGE_KEY,
  TEAM_A_ID,
  TEAM_B_ID,
  TEAM_IDS,
  TEAM_NAME_MAX_LENGTH,
} from '../game/constants.js';
import {
  api,
  apiErrorCode,
  apiErrorDetails,
  apiErrorMessage,
  isVersionConflict,
  toFrontendActivationResult,
  toFrontendBoard,
  toFrontendDraftResult,
  toFrontendResolveResult,
  toFrontendTileSessionResult,
} from '../api/server.js';
import { ensureInstallation } from '../api/installation.js';
import { fetchCategories } from '../api/client.js';
import { buildDraftOrder, validateDraft } from '../game/draft.js';
import { getOutcomeAvailability } from '../game/outcomes.js';
import { getPowerEligibility } from '../game/powerEligibility.js';
import { OUTCOMES, computeScoreDeltas } from '../game/scoring.js';
import {
  createFreshMatchState,
  createInitialGameState,
  countPlayedTiles,
  sanitizePersistedState,
} from '../game/state.js';
import {
  advanceTimer,
  createTimer,
  getElapsedMs,
  pauseTimer,
  resetPrimaryTimer,
  startTimer,
  toggleTimer,
} from '../game/timer.js';

const POWER_IDS = POWERS.map((power) => power.id);

function browserStorage() {
  try {
    if (typeof window !== 'undefined' && window.localStorage) return window.localStorage;
  } catch {
    // قد يكون التخزين محظورًا.
  }
  try {
    if (typeof globalThis !== 'undefined' && globalThis.localStorage) return globalThis.localStorage;
  } catch {
    // تجاهل.
  }
  return null;
}

/**
 * تخزين آمن: أي JSON تالف يتحول لكائن غير صالح يلتقطه sanitizePersistedState
 * ويعرض إشعارًا، بدل رمي استثناء أثناء الهيدرشن. فشل الكتابة (وضع خاص/امتلاء)
 * لا يوقف اللعب في الذاكرة.
 */
const safeStorage = {
  getItem(name) {
    try {
      const storage = browserStorage();
      if (!storage) return null;
      const raw = storage.getItem(name);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') {
        return { state: { currentStage: '__corrupt__' }, version: 1 };
      }
      return parsed;
    } catch {
      return { state: { currentStage: '__corrupt__' }, version: 1 };
    }
  },
  setItem(name, value) {
    try {
      const storage = browserStorage();
      if (!storage) return;
      storage.setItem(name, JSON.stringify(value));
    } catch {
      // اللعب يكمل في الذاكرة.
    }
  },
  removeItem(name) {
    try {
      const storage = browserStorage();
      if (!storage) return;
      storage.removeItem(name);
    } catch {
      // تجاهل.
    }
  },
};

function otherTeamId(teamId) {
  if (teamId === TEAM_A_ID) return TEAM_B_ID;
  if (teamId === TEAM_B_ID) return TEAM_A_ID;
  return TEAM_IDS.find((id) => id !== teamId) ?? null;
}

function getActiveAndDefending(state) {
  const question = state.currentQuestion;
  const activeTeamId = question?.activeTeamId;
  const defendingTeamId = otherTeamId(activeTeamId);
  const activeTeam = state.teams.find((team) => team.id === activeTeamId);
  const defendingTeam = state.teams.find((team) => team.id === defendingTeamId);
  return { activeTeamId, defendingTeamId, activeTeam, defendingTeam };
}

function powerOwner(picks, powerId) {
  return picks.find((pick) => pick.powerId === powerId)?.teamId ?? null;
}

/** خانات الخادم تأخذ الأولوية، والبيانات المحلية احتياط عند غياب المزامنة. */
function tileForState(state, tileId) {
  return state.content?.tiles?.find((tile) => tile.id === tileId) ?? TILE_BY_ID[tileId] ?? null;
}

function questionForState(state, questionId, tile = null) {
  return (
    state.content?.questions?.[questionId] ??
    QUESTION_BY_ID[questionId] ??
    (tile ? QUESTION_BY_ID[tile.questionId] : null) ??
    null
  );
}

function serverScores(match, fallbackTeams = []) {
  const scores = {
    [TEAM_A_ID]: match?.score_team1,
    [TEAM_B_ID]: match?.score_team2,
  };
  return fallbackTeams.map((team) => ({
    ...team,
    score: Number.isFinite(scores[team.id]) ? scores[team.id] : team.score,
  }));
}

function resultOutcome(result, activeTeamId) {
  if (!result?.winningTeamId) return OUTCOMES.NOBODY;
  return result.winningTeamId === activeTeamId ? OUTCOMES.ACTIVE : OUTCOMES.DEFENDING;
}

/** يحوّل خانات اللوحة من الخادم إلى سجل نتائج محلي خفيف للاسترداد. */
function usedPowersFromPicks(picks = []) {
  const used = { [TEAM_A_ID]: [], [TEAM_B_ID]: [] };
  for (const pick of picks) {
    if (!pick.usedAt || !pick.teamId) continue;
    used[pick.teamId] = Array.from(new Set([...(used[pick.teamId] ?? []), pick.powerId]));
  }
  return used;
}

function boardTileResults(tiles, previous = {}) {
  const results = { ...previous };
  for (const tile of tiles) {
    if (!tile.result?.played) continue;
    results[tile.id] = {
      ...(previous[tile.id] ?? {}),
      played: true,
      tileId: tile.id,
      questionId: tile.questionId,
      categoryId: tile.categoryId,
      basePoints: tile.points,
      winningTeamId: tile.result.winningTeamId ?? null,
      deltas: tile.result.deltas ?? {},
      activePowers: tile.result.activePowers ?? [],
      outcome: tile.result.winningTeamId
        ? resultOutcome(tile.result, previous[tile.id]?.activeTeamId ?? null)
        : OUTCOMES.NOBODY,
      resolvedAt: tile.result.resolvedAt ?? previous[tile.id]?.resolvedAt ?? null,
    };
  }
  return results;
}

export const useGameStore = create(
  persist(
    (set, get) => ({
      ...createInitialGameState(),

      // ── صالة البداية ────────────────────────────────────────────
      updateTeam(teamId, patch, now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.LOBBY) return { ok: false, reason: 'تعديل الفرق متاح بالصالة فقط.' };
        const team = state.teams.find((item) => item.id === teamId);
        if (!team) return { ok: false, reason: 'الفريق غير موجود.' };

        const next = { ...team };
        if (typeof patch.name === 'string') {
          next.name = patch.name.slice(0, TEAM_NAME_MAX_LENGTH);
        }
        if (typeof patch.color === 'string') {
          const taken = state.teams.some((item) => item.id !== teamId && item.color === patch.color);
          if (taken) return { ok: false, reason: 'اللون محجوز للفريق الثاني.' };
          next.color = patch.color;
        }
        if (typeof patch.avatar === 'string') next.avatar = patch.avatar;

        set({
          teams: state.teams.map((item) => (item.id === teamId ? next : item)),
          recoveryNotice: null,
        });
        return { ok: true };
      },

      finishCoinToss(winnerTeamId, now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.LOBBY) return { ok: false, reason: 'القرعة بالصالة فقط.' };
        if (state.coinToss.completed) return { ok: false, reason: 'القرعة انتهت من قبل.' };
        if (!TEAM_IDS.includes(winnerTeamId)) return { ok: false, reason: 'الفريق غير معروف.' };
        const loser = otherTeamId(winnerTeamId);
        set({
          coinToss: { result: winnerTeamId, completed: true },
          draft: { order: buildDraftOrder(winnerTeamId, loser), picks: [] },
          currentTurnTeamId: null,
          recoveryNotice: null,
        });
        return { ok: true, winnerTeamId };
      },

      /** يجلب ملفات اللاعبين المسماة من الخادم لاختيار المشاركين. */
      async loadProfiles(force = false) {
        const state = get();
        if (state.profiles.status === 'loading') {
          return { ok: false, reason: 'جاري تحميل اللاعبين…' };
        }
        if (!force && state.profiles.status === 'ready') {
          return { ok: true, cached: true };
        }
        set({ profiles: { ...state.profiles, status: 'loading', error: null } });
        try {
          const items = await api.listUsers();
          const known = new Set((items ?? []).map((user) => user.id));
          const current = get();
          const teamProfileIds = { ...current.teamProfileIds };
          for (const teamId of TEAM_IDS) {
            teamProfileIds[teamId] = (teamProfileIds[teamId] ?? []).filter((id) =>
              known.has(id),
            );
          }
          set({
            profiles: { status: 'ready', items: items ?? [], error: null },
            teamProfileIds,
          });
          return { ok: true, count: (items ?? []).length };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({ profiles: { ...get().profiles, status: 'error', error: message } });
          return { ok: false, reason: message };
        }
      },

      /** ينشئ ملف لاعب مسمى جديدًا. */
      async createProfile(username) {
        const name = (username ?? '').trim();
        if (!name) return { ok: false, reason: 'اكتب اسم المستخدم أولًا.' };
        try {
          const user = await api.createUser({ username: name });
          const current = get();
          set({
            profiles: {
              status: 'ready',
              items: [...current.profiles.items, user],
              error: null,
            },
          });
          return { ok: true, user };
        } catch (error) {
          return { ok: false, reason: apiErrorMessage(error) };
        }
      },

      /** يبدّل إسناد ملف لفريق؛ النقل من الفريق الآخر تلقائي لمنع الازدواج. */
      toggleTeamProfile(teamId, userId) {
        const state = get();
        if (state.currentStage !== STAGES.LOBBY) {
          return { ok: false, reason: 'اختيار اللاعبين متاح بالصالة فقط.' };
        }
        if (!TEAM_IDS.includes(teamId)) return { ok: false, reason: 'الفريق غير معروف.' };
        const id = Number(userId);
        if (!Number.isInteger(id) || id < 1) {
          return { ok: false, reason: 'ملف اللاعب غير صالح.' };
        }
        const next = {
          [TEAM_A_ID]: [...(state.teamProfileIds[TEAM_A_ID] ?? [])],
          [TEAM_B_ID]: [...(state.teamProfileIds[TEAM_B_ID] ?? [])],
        };
        const other = teamId === TEAM_A_ID ? TEAM_B_ID : TEAM_A_ID;
        next[other] = next[other].filter((item) => item !== id);
        if (next[teamId].includes(id)) {
          next[teamId] = next[teamId].filter((item) => item !== id);
        } else {
          if (next[teamId].length >= 8) {
            return { ok: false, reason: 'الفريق الواحد يستوعب 8 لاعبين حدًا أقصى.' };
          }
          next[teamId] = [...next[teamId], id];
        }
        set({ teamProfileIds: next, recoveryNotice: null });
        return { ok: true };
      },

      /** يجلب الفئات الاثنتي عشرة الحقيقية وأعدادها المتاحة من الخادم. */
      async loadCategories(force = false) {
        const state = get();
        if (state.categories.status === 'loading') {
          return { ok: false, reason: 'جاري تحميل الفئات…' };
        }
        if (!force && state.categories.items.length > 0) {
          return { ok: true, cached: true };
        }
        set({ categories: { ...state.categories, status: 'loading', error: null } });
        try {
          const items = await fetchCategories();
          if (items.length < 6) throw new Error('كتالوج الفئات غير مكتمل على الخادم.');
          const current = get();
          const valid = new Set(items.map((item) => item.id));
          set({
            categories: { status: 'ready', items, error: null },
            selectedCategorySlugs: current.selectedCategorySlugs.filter((slug) => valid.has(slug)),
          });
          return { ok: true, count: items.length };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({ categories: { ...get().categories, status: 'error', error: message } });
          return { ok: false, reason: message };
        }
      },

      toggleCategory(categoryId) {
        const state = get();
        if (state.currentStage !== STAGES.LOBBY) {
          return { ok: false, reason: 'اختيار الفئات متاح بالصالة فقط.' };
        }
        const category = state.categories.items.find((item) => item.id === categoryId);
        if (!category) return { ok: false, reason: 'الفئة غير موجودة بالكتالوج.' };
        const selected = state.selectedCategorySlugs;
        if (selected.includes(categoryId)) {
          set({ selectedCategorySlugs: selected.filter((slug) => slug !== categoryId) });
          return { ok: true, selected: false };
        }
        if (selected.length >= 6) {
          return { ok: false, reason: 'اخترت ست فئات بالفعل. شِل وحدة قبل ما تضيف.' };
        }
        if (category.eligibleCount < 3) {
          return { ok: false, reason: 'هالفئة ما عندها أسئلة كافية متاحة حاليًا.' };
        }
        set({ selectedCategorySlugs: [...selected, categoryId] });
        return { ok: true, selected: true };
      },

      clearCategorySelection() {
        set({ selectedCategorySlugs: [] });
      },

      /** اختيار عشوائي لست فئات مختلفة من الكتالوج الحقيقي. */
      pickRandomCategories() {
        const state = get();
        if (state.currentStage !== STAGES.LOBBY) {
          return { ok: false, reason: 'اختيار الفئات متاح بالصالة فقط.' };
        }
        const pool = state.categories.items.filter((item) => item.eligibleCount >= 3);
        if (pool.length < 6) {
          return { ok: false, reason: 'ما في ست فئات متاحة بأسئلة كافية.' };
        }
        const shuffled = [...pool];
        for (let index = shuffled.length - 1; index > 0; index -= 1) {
          const swap = Math.floor(Math.random() * (index + 1));
          [shuffled[index], shuffled[swap]] = [shuffled[swap], shuffled[index]];
        }
        set({ selectedCategorySlugs: shuffled.slice(0, 6).map((item) => item.id) });
        return { ok: true };
      },

      startDraft(now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.LOBBY) return { ok: false, reason: 'ابدأ السحب من الصالة.' };
        if (!state.coinToss.completed || !TEAM_IDS.includes(state.coinToss.result)) {
          return { ok: false, reason: 'ارمِ العملة أولًا.' };
        }
        if (state.teams.some((team) => !team.name.trim())) {
          return { ok: false, reason: 'سمّوا الفريقين قبل البدء.' };
        }
        const loser = otherTeamId(state.coinToss.result);
        const base = createInitialGameState();
        set({
          ...base,
          teams: state.teams.map((team) => ({ ...team, score: 0 })),
          settings: state.settings,
          // كتالوج الفئات يبقى محمّلًا من الخادم بعد مغادرة الصالة.
          categories: state.categories,
          currentStage: STAGES.DRAFT,
          coinToss: { result: state.coinToss.result, completed: true },
          draft: { order: buildDraftOrder(state.coinToss.result, loser), picks: [] },
          matchStartedAt: now,
          recoveryNotice: null,
        });
        return { ok: true };
      },

      /**
       * ينشئ المباراة على FastAPI ثم يحفظ اللوحة كنسخة استرداد محلية.
       * السحب (القوى) يبقى محليًا لأن الخادم لا يديره، لكن كل تسجيل نتيجة يمر به.
       */
      async beginMatch(now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.LOBBY) {
          return { ok: false, reason: 'ابدأ المباراة من الصالة فقط.' };
        }
        if (!state.coinToss.completed || !TEAM_IDS.includes(state.coinToss.result)) {
          return { ok: false, reason: 'ارمِ العملة أولًا.' };
        }
        const names = state.teams.map((team) => team.name.trim());
        if (names.some((name) => !name)) {
          return { ok: false, reason: 'سمّوا الفريقين قبل البدء.' };
        }
        if (names[0] === names[1]) {
          return { ok: false, reason: 'أسماء الفريقين لازم تكون مختلفة.' };
        }
        if (state.server.pending) {
          return { ok: false, reason: 'جاري تجهيز المباراة…' };
        }
        if (state.selectedCategorySlugs.length !== 6) {
          return { ok: false, reason: 'اختاروا ست فئات مختلفة قبل البدء.' };
        }

        let installation = null;
        try {
          installation = await ensureInstallation();
        } catch {
          return { ok: false, reason: 'تعذّر تحديد هوية الجهاز — تحقق من السيرفر وحاول مجددًا.' };
        }

        set({ server: { ...state.server, pending: true, error: null } });
        try {
          const raw = await api.createMatch({
            team1Name: names[0],
            team2Name: names[1],
            startingTurn: state.coinToss.result,
            categorySlugs: state.selectedCategorySlugs,
            team1UserIds: state.teamProfileIds[TEAM_A_ID] ?? [],
            team2UserIds: state.teamProfileIds[TEAM_B_ID] ?? [],
            installToken: installation?.credential ?? null,
          });
          const board = toFrontendBoard(raw);
          const base = createInitialGameState();
          const winnerId = board.match.coinTossWinner ?? state.coinToss.result;
          const loserId = otherTeamId(winnerId);

          set({
            ...base,
            teams: state.teams.map((team) => {
              const serverTeam = board.teams.find((item) => item.id === team.id);
              return { ...team, score: serverTeam?.score ?? 0 };
            }),
            settings: state.settings,
            // أسماء وأيقونات الفئات تُعرض من كتالوج الخادم لا من بيانات ثابتة.
            categories: state.categories,
            currentStage: STAGES.DRAFT,
            coinToss: { result: winnerId, completed: true },
            draft: board.draft
              ? { order: board.draft.order, picks: board.draft.picks }
              : { order: buildDraftOrder(winnerId, loserId), picks: [] },
            usedPowerIds: board.draft
              ? usedPowersFromPicks(board.draft.picks)
              : { [TEAM_A_ID]: [], [TEAM_B_ID]: [] },
            currentTurnTeamId: board.currentTurnTeamId,
            matchStartedAt: now,
            server: {
              matchCode: board.server.matchCode,
              version: board.server.version,
              status: board.match.status,
              winner: board.match.winner ?? null,
              hostToken: board.server.hostToken ?? null,
              online: true,
              error: null,
              pending: false,
              syncing: false,
            },
            selectedCategorySlugs: board.selectedCategories?.length
              ? board.selectedCategories
              : state.selectedCategorySlugs,
            matchParticipants: board.participants ?? [],
            content: {
              source: 'server',
              questions: board.questions,
              tiles: board.tiles,
              backups: board.backups,
            },
            recoveryNotice: null,
          });
          return { ok: true, matchCode: board.server.matchCode };
        } catch (error) {
          let message = apiErrorMessage(error);
          if (apiErrorCode(error) === 'INSUFFICIENT_QUESTIONS') {
            const details = apiErrorDetails(error);
            const bucket = details.bucket ? ` (الدلو ${details.bucket})` : '';
            message = `${message}${bucket} جرّبوا فئات مختلفة أو لاعبين بلا سجل طويل.`;
          }
          set({ server: { ...get().server, pending: false, online: false, error: message } });
          return { ok: false, reason: message };
        }
      },

      /** يزامن المباراة المحفوظة مع الخادم؛ فشل الشبكة يبقي نسخة الاسترداد. */
      async syncServerMatch() {
        const state = get();
        const matchCode = state.server.matchCode;
        if (!matchCode) return { ok: false, reason: 'ما في مباراة مرتبطة بالسيرفر.' };
        if (state.server.syncing) return { ok: false, reason: 'المزامنة شغّالة.' };

        set({ server: { ...state.server, syncing: true, error: null } });
        try {
          const board = toFrontendBoard(await api.getMatch(matchCode));
          const current = get();
          const tileResults = boardTileResults(board.tiles, current.tileResults);
          const playedCount = countPlayedTiles(tileResults);

          let stage = current.currentStage;
          let currentQuestion = current.currentQuestion;
          if (playedCount >= TOTAL_PRIMARY_TILES) {
            stage = STAGES.PODIUM;
            currentQuestion = null;
          } else if (stage === STAGES.PODIUM) {
            stage = STAGES.BOARD;
          }
          if (stage === STAGES.ARENA) {
            const tile = board.tiles.find((item) => item.id === currentQuestion?.tileId);
            const payload = tile ? board.questions[tile.questionId] : null;
            if (!tile || !payload || tile.result?.played) {
              stage = STAGES.BOARD;
              currentQuestion = null;
            } else {
              const openedAt = tile.openedAt
                ? Date.parse(tile.openedAt)
                : currentQuestion.sessionStartedAt;
              const revealedAt = tile.revealedAt ? Date.parse(tile.revealedAt) : null;
              currentQuestion = {
                ...currentQuestion,
                questionId: tile.questionId,
                categoryId: tile.categoryId,
                points: tile.points,
                sessionStartedAt: openedAt,
                activeTeamId: tile.activeTeamId ?? currentQuestion.activeTeamId,
                activePowers: tile.activePowers ?? currentQuestion.activePowers,
                noiseUntil: tile.noiseUntil
                  ? Date.parse(tile.noiseUntil)
                  : currentQuestion.noiseUntil,
                revealed: revealedAt ? true : currentQuestion.revealed,
                revealedAt: revealedAt ?? currentQuestion.revealedAt,
                timer:
                  revealedAt && !currentQuestion.revealed
                    ? pauseTimer(currentQuestion.timer, revealedAt)
                    : currentQuestion.timer,
              };
            }
          }

          set({
            teams: current.teams.map((team) => {
              const serverTeam = board.teams.find((item) => item.id === team.id);
              return serverTeam
                ? { ...team, name: serverTeam.name || team.name, score: serverTeam.score }
                : team;
            }),
            draft: board.draft
              ? { order: board.draft.order, picks: board.draft.picks }
              : current.draft,
            usedPowerIds: board.draft
              ? usedPowersFromPicks(board.draft.picks)
              : current.usedPowerIds,
            selectedCategorySlugs: board.selectedCategories?.length
              ? board.selectedCategories
              : current.selectedCategorySlugs,
            content: {
              source: 'server',
              questions: board.questions,
              tiles: board.tiles,
              backups: board.backups,
            },
            server: {
              matchCode: board.server.matchCode,
              version: board.server.version,
              status: board.match.status,
              winner: board.match.winner ?? null,
              hostToken: current.server.hostToken ?? null,
              online: true,
              error: null,
              pending: false,
              syncing: false,
            },
            currentTurnTeamId: board.currentTurnTeamId,
            tileResults,
            currentQuestion,
            currentStage: stage,
            matchParticipants: board.participants ?? current.matchParticipants ?? [],
            matchFinishedAt:
              stage === STAGES.PODIUM
                ? current.matchFinishedAt ?? Date.now()
                : current.matchFinishedAt,
            recoveryNotice: null,
          });
          return { ok: true, status: board.match.status };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({
            server: { ...get().server, syncing: false, online: false, error: message },
            recoveryNotice: `${message} نكمل من النسخة المحفوظة.`,
          });
          return { ok: false, reason: message };
        }
      },

      draftPower(powerId, now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.DRAFT) return { ok: false, reason: 'ما إحنا بمرحلة السحب.' };
        if (!POWER_BY_ID[powerId]) return { ok: false, reason: 'قوة غير معروفة.' };
        if (state.draft.picks.length >= 6) return { ok: false, reason: 'السحب مكتمل.' };
        const currentTeamId = state.draft.order[state.draft.picks.length];
        if (!currentTeamId) return { ok: false, reason: 'ترتيب السحب غير جاهز.' };
        // كل فريق له ثلاث قوى فريدة؛ الفريق الثاني يقدر ياخذ نفس قوة الأول.
        if (
          state.draft.picks.some(
            (pick) => pick.teamId === currentTeamId && pick.powerId === powerId,
          )
        ) {
          return { ok: false, reason: 'هالقوة انسحبت من قبل لنفس الفريق.' };
        }
        const pick = { teamId: currentTeamId, powerId, pickedAt: now };
        set({
          draft: { ...state.draft, picks: [...state.draft.picks, pick] },
          recoveryNotice: null,
        });
        return { ok: true, teamId: currentTeamId };
      },

      /** يسجّل اختيار القوة على الخادم؛ الملكية وترتيب الأدوار سلطة السيرفر. */
      async draftPowerOnline(powerId, now = Date.now()) {
        const state = get();
        if (!state.server.matchCode) return get().draftPower(powerId, now);
        if (state.currentStage !== STAGES.DRAFT) {
          return { ok: false, reason: 'ما إحنا بمرحلة السحب.' };
        }
        if (!POWER_BY_ID[powerId]) return { ok: false, reason: 'قوة غير معروفة.' };
        if (state.server.pending) return { ok: false, reason: 'السيرفر يسجّل الاختيار…' };

        set({ server: { ...state.server, pending: true, error: null } });
        try {
          const raw = await api.draftPower({
            matchCode: state.server.matchCode,
            powerId,
            expectedVersion: state.server.version,
          });
          const mapped = toFrontendDraftResult(raw);
          const current = get();
          set({
            draft: mapped.draft
              ? { order: mapped.draft.order, picks: mapped.draft.picks }
              : current.draft,
            server: {
              ...current.server,
              version: mapped.match.version,
              status: mapped.match.status,
              winner: mapped.match.winner ?? null,
              online: true,
              error: null,
              pending: false,
            },
            recoveryNotice: null,
          });
          return {
            ok: true,
            teamId: mapped.pick?.teamId ?? null,
            powerId,
            complete: mapped.draft?.complete ?? false,
          };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({
            server: { ...get().server, pending: false, online: false, error: message },
          });
          if (isVersionConflict(error)) await get().syncServerMatch();
          return { ok: false, reason: message };
        }
      },

      enterBoard() {
        const state = get();
        if (state.currentStage !== STAGES.DRAFT) return { ok: false, reason: 'ما إحنا بمرحلة السحب.' };
        const validation = validateDraft(state.draft.picks, POWER_IDS, TEAM_IDS);
        if (!validation.ok) return { ok: false, reason: validation.errors[0] };
        set({
          currentStage: STAGES.BOARD,
          currentTurnTeamId: state.coinToss.result,
          currentQuestion: null,
          recoveryNotice: null,
        });
        return { ok: true };
      },

      resetSavedMatch(now = Date.now()) {
        try {
          browserStorage()?.removeItem(STORAGE_KEY);
        } catch {
          // التخزين قد يكون معطلًا (وضع خاص)؛ نكمل بتصفير الحالة في الذاكرة.
        }
        set({
          ...createInitialGameState(),
          recoveryNotice: 'تم حذف المباراة المحفوظة وبدأنا من جديد.',
        });
        return { ok: true };
      },

      newMatch(now = Date.now()) {
        const state = get();
        set({
          ...createFreshMatchState({ teams: state.teams, settings: state.settings }),
          currentStage: STAGES.LOBBY,
          recoveryNotice: null,
        });
        return { ok: true };
      },

      setMuted(muted) {
        set((state) => ({ settings: { ...state.settings, muted: Boolean(muted) } }));
      },

      clearRecoveryNotice() {
        set({ recoveryNotice: null });
      },

      // ── اللوحة ─────────────────────────────────────────────────
      selectTile(tileId, now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.BOARD) return { ok: false, reason: 'الخانات تنفتح من اللوحة فقط.' };
        const tile = tileForState(state, tileId);
        if (!tile) return { ok: false, reason: 'الخانة غير موجودة.' };
        if (state.tileResults[tileId]?.played) return { ok: false, reason: 'هالخانة انلعبت من قبل.' };
        if (state.currentQuestion) return { ok: false, reason: 'في سؤال مفتوح بالفعل.' };
        if (!TEAM_IDS.includes(state.currentTurnTeamId)) return { ok: false, reason: 'الدور غير محدد.' };
        const payload = questionForState(state, tile.questionId, tile);
        if (!payload) return { ok: false, reason: 'سؤال الخانة غير موجود.' };

        const pickedPowerIdsAtOpen = state.draft.picks
          .filter((pick) => pick.teamId === state.currentTurnTeamId)
          .map((pick) => pick.powerId);

        set({
          currentStage: STAGES.ARENA,
          currentQuestion: {
            tileId,
            questionId: payload.id,
            categoryId: tile.categoryId,
            points: tile.points,
            sourceBackupId: null,
            activeTeamId: state.currentTurnTeamId,
            originalActiveTeamId: state.currentTurnTeamId,
            stolenByTeamId: null,
            sessionStartedAt: now,
            revealed: false,
            revealedAt: null,
            activePowers: [],
            usedBackupIds: [],
            noiseUntil: null,
            wrongGuesses: 0,
            twoAnswerExtensionUsed: false,
            // الساعة تبدأ تلقائيًا لحظة فتح السؤال، وتعدّ للأمام بلا سقف.
            timer: startTimer(createTimer(), now),
            pickedPowerIdsAtOpen,
          },
          recoveryNotice: null,
        });
        return { ok: true };
      },

      /** يفتح الخانة محليًا ثم يثبت جلسة السؤال على الخادم. */
      async selectTileOnline(tileId, now = Date.now()) {
        const state = get();
        if (!state.server.matchCode) return get().selectTile(tileId, now);
        const opened = get().selectTile(tileId, now);
        if (!opened.ok) return opened;
        const question = get().currentQuestion;
        if (!question) return { ok: false, reason: 'ما انفتح السؤال.' };

        set({ server: { ...get().server, pending: true, error: null } });
        try {
          const raw = await api.openTile({
            matchCode: state.server.matchCode,
            tileKey: tileId,
            expectedVersion: state.server.version,
          });
          const mapped = toFrontendTileSessionResult(raw);
          const current = get();
          const active = current.currentQuestion;
          if (!active) return { ok: false, reason: 'ما انفتح السؤال.' };
          const openedAt = mapped.session?.openedAt
            ? Date.parse(mapped.session.openedAt)
            : now;
          const serverActiveTeamId = mapped.tile.activeTeamId ?? active.activeTeamId;
          set({
            currentQuestion: {
              ...active,
              questionId: mapped.question.id,
              activeTeamId: serverActiveTeamId,
              originalActiveTeamId: serverActiveTeamId,
              activePowers: mapped.tile.activePowers ?? [],
              sessionStartedAt: openedAt,
              noiseUntil: mapped.session?.noiseUntil
                ? Date.parse(mapped.session.noiseUntil)
                : null,
              timer: startTimer(createTimer(), openedAt),
            },
            content: {
              ...current.content,
              questions: { ...current.content.questions, [mapped.question.id]: mapped.question },
              tiles: current.content.tiles.map((tile) =>
                tile.id === tileId
                  ? { ...tile, questionId: mapped.question.id, openedAt: mapped.tile.openedAt }
                  : tile,
              ),
            },
            server: {
              ...current.server,
              version: mapped.match.version,
              status: mapped.match.status,
              winner: mapped.match.winner ?? null,
              online: true,
              error: null,
              pending: false,
            },
            recoveryNotice: null,
          });
          return { ok: true, session: mapped.session };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({
            currentQuestion: null,
            currentStage: STAGES.BOARD,
            server: { ...get().server, pending: false, online: false, error: message },
            recoveryNotice: message,
          });
          if (isVersionConflict(error)) await get().syncServerMatch();
          return { ok: false, reason: message };
        }
      },

      adjustScore(teamId, amount, now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.BOARD) return { ok: false, reason: 'التعديل اليدوي من اللوحة.' };
        if (!TEAM_IDS.includes(teamId)) return { ok: false, reason: 'الفريق غير معروف.' };
        if (amount !== 100 && amount !== -100) return { ok: false, reason: 'التعديل ±100 فقط.' };
        const team = state.teams.find((item) => item.id === teamId);
        if (!team) return { ok: false, reason: 'الفريق غير موجود.' };
        set({
          teams: state.teams.map((item) =>
            item.id === teamId ? { ...item, score: item.score + amount } : item,
          ),
          manualAdjustments: [
            ...state.manualAdjustments,
            { teamId, amount, at: now },
          ].slice(-200),
        });
        return { ok: true };
      },

      // ── الساحة: المؤقت ─────────────────────────────────────────
      toggleQuestionTimer(now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.ARENA || !state.currentQuestion) {
          return { ok: false, reason: 'ما في سؤال مفتوح.' };
        }
        if (state.currentQuestion.revealed) return { ok: false, reason: 'الإجابة ظهرت.' };
        const timer = toggleTimer(state.currentQuestion.timer, now);
        if (timer === state.currentQuestion.timer) {
          return { ok: false, reason: 'المؤقت ما يقدر يتحرك بهالحالة.' };
        }
        set({
          currentQuestion: { ...state.currentQuestion, timer },
        });
        return { ok: true, running: timer.running };
      },

      tickQuestionTimer(now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.ARENA || !state.currentQuestion) return [];
        if (state.currentQuestion.revealed) return [];
        const { timer, events } = advanceTimer(state.currentQuestion.timer, now);
        if (events.length > 0) {
          set({
            currentQuestion: { ...state.currentQuestion, timer },
          });
        }
        return events;
      },

      recoverQuestionTimer(now = Date.now()) {
        return get().tickQuestionTimer(now);
      },

      revealAnswer(now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.ARENA || !state.currentQuestion) {
          return { ok: false, reason: 'ما في سؤال مفتوح.' };
        }
        if (state.currentQuestion.revealed) return { ok: false, reason: 'الإجابة ظاهرة بالفعل.' };
        const timer = pauseTimer(state.currentQuestion.timer, now);
        set({
          currentQuestion: {
            ...state.currentQuestion,
            revealed: true,
            revealedAt: now,
            timer,
          },
        });
        return { ok: true };
      },

      /** يظهر الإجابة على الخادم أولًا، فتتوقف نافذة القوى هناك. */
      async revealAnswerOnline(now = Date.now()) {
        const state = get();
        const question = state.currentQuestion;
        if (!state.server.matchCode) return get().revealAnswer(now);
        if (state.currentStage !== STAGES.ARENA || !question) {
          return { ok: false, reason: 'ما في سؤال مفتوح.' };
        }
        if (question.revealed) return { ok: false, reason: 'الإجابة ظاهرة بالفعل.' };
        if (state.server.pending) return { ok: false, reason: 'السيرفر يحدّث السؤال…' };

        set({ server: { ...state.server, pending: true, error: null } });
        try {
          const raw = await api.revealTile({
            matchCode: state.server.matchCode,
            tileKey: question.tileId,
            expectedVersion: state.server.version,
          });
          const mapped = toFrontendTileSessionResult(raw);
          const revealedAt = mapped.session?.revealedAt
            ? Date.parse(mapped.session.revealedAt)
            : now;
          const revealed = get().revealAnswer(revealedAt);
          if (!revealed.ok) return revealed;
          const current = get();
          set({
              content: {
                ...current.content,
                questions: { ...current.content.questions, [mapped.question.id]: mapped.question },
              },
            currentQuestion: current.currentQuestion
              ? {
                  ...current.currentQuestion,
                  questionId: mapped.question.id,
                  activePowers: mapped.tile.activePowers ?? current.currentQuestion.activePowers,
                  activeTeamId: mapped.tile.activeTeamId ?? current.currentQuestion.activeTeamId,
                  noiseUntil: mapped.session?.noiseUntil
                    ? Date.parse(mapped.session.noiseUntil)
                    : current.currentQuestion.noiseUntil,
                }
              : null,
            server: {
              ...current.server,
              version: mapped.match.version,
              status: mapped.match.status,
              winner: mapped.match.winner ?? null,
              online: true,
              error: null,
              pending: false,
            },
            recoveryNotice: null,
          });
          return { ok: true };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({
            server: { ...get().server, pending: false, online: false, error: message },
            recoveryNotice: message,
          });
          if (isVersionConflict(error)) await get().syncServerMatch();
          return { ok: false, reason: message };
        }
      },

      registerWrongGuess(now = Date.now()) {
        const state = get();
        const question = state.currentQuestion;
        if (state.currentStage !== STAGES.ARENA || !question) {
          return { ok: false, reason: 'ما في سؤال مفتوح.' };
        }
        if (question.revealed) return { ok: false, reason: 'الإجابة ظهرت.' };
        if (!question.activePowers.includes('two_answers')) {
          return { ok: false, reason: 'قوة «جاوب جوابين» مو مفعّلة.' };
        }
        if ((question.wrongGuesses ?? 0) >= 2) {
          return { ok: false, reason: 'المحاولتان خلصتا.' };
        }

        const nextWrong = (question.wrongGuesses ?? 0) + 1;
        set({
          currentQuestion: {
            ...question,
            wrongGuesses: nextWrong,
            twoAnswerExtensionUsed: false,
          },
        });
        return {
          ok: true,
          wrongGuesses: nextWrong,
        };
      },

      // ── الساحة: القوى ──────────────────────────────────────────
      activatePower(powerId, teamId = null, now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.ARENA || !state.currentQuestion) {
          return { ok: false, reason: 'القوى تنفع داخل السؤال فقط.' };
        }
        const question = state.currentQuestion;
        const owner = teamId ?? powerOwner(state.draft.picks, powerId);
        if (!owner) return { ok: false, reason: 'هالقوة ما انسحبت بهالمباراة.' };
        const ownsPower = state.draft.picks.some(
          (pick) => pick.teamId === owner && pick.powerId === powerId,
        );
        if (!ownsPower) return { ok: false, reason: 'هالقوة مو من اختيار هالفريق.' };
        const activatingTeamId = owner;
        const draftedPowerIds = state.draft.picks
          .filter((pick) => pick.teamId === owner)
          .map((pick) => pick.powerId);

        const eligibility = getPowerEligibility({
          powerId,
          teamId: owner,
          question,
          timer: question.timer,
          draftedPowerIds,
          usedPowerIds: state.usedPowerIds[owner] ?? [],
          now,
        });
        if (!eligibility.eligible) return { ok: false, reason: eligibility.reason };

        let timer = question.timer;
        let noiseUntil = question.noiseUntil;
        let questionId = question.questionId;
        let sourceBackupId = question.sourceBackupId;
        let usedBackupIds = [...question.usedBackupIds];
        let wrongGuesses = question.wrongGuesses;
        let activeTeamId = question.activeTeamId;
        let stolenByTeamId = question.stolenByTeamId ?? null;
        const activePowers = Array.from(new Set([...question.activePowers, powerId]));
        let switchedBackup = null;
        let stoleQuestion = false;

        if (powerId === 'steal') {
          // الفريق الثاني ياخذ السؤال بدال صاحب الدور الأصلي.
          activeTeamId = owner;
          stolenByTeamId = owner;
          stoleQuestion = true;
        } else if (powerId === 'noise') {
          noiseUntil = now + NOISE_DURATION_MS;
        } else if (powerId === 'switch') {
          const backups = getCompatibleBackups(
            question.categoryId,
            question.points,
            question.usedBackupIds,
          );
          const backup = backups[0];
          if (!backup) return { ok: false, reason: 'ما بقى سؤال احتياطي متوافق.' };
          switchedBackup = backup;
          questionId = backup.id;
          sourceBackupId = backup.id;
          usedBackupIds = [...question.usedBackupIds, backup.id];
          timer = resetPrimaryTimer(timer, now);
          noiseUntil = null;
          wrongGuesses = 0;
        }

        const nextUsed = Array.from(new Set([...(state.usedPowerIds[owner] ?? []), powerId]));
        const stats = {
          ...state.stats,
          [owner]: {
            ...state.stats[owner],
            powersUsed: (state.stats[owner]?.powersUsed ?? 0) + 1,
          },
        };

        set({
          currentQuestion: {
            ...question,
            questionId,
            sourceBackupId,
            usedBackupIds,
            activePowers,
            timer,
            noiseUntil,
            wrongGuesses,
            activeTeamId,
            stolenByTeamId,
          },
          currentTurnTeamId: activeTeamId,
          usedPowerIds: { ...state.usedPowerIds, [owner]: nextUsed },
          stats,
          teams: state.teams,
        });

        return {
          ok: true,
          powerId,
          teamId: owner,
          stoleQuestion,
          activeTeamId,
          backup: switchedBackup ? { id: switchedBackup.id, question: switchedBackup.question } : null,
        };
      },

      // ── الساحة: الحسم ─────────────────────────────────────────
      resolveQuestion(outcome, now = Date.now()) {
        const state = get();
        const question = state.currentQuestion;
        if (state.currentStage !== STAGES.ARENA || !question) {
          return { ok: false, reason: 'ما في سؤال مفتوح.' };
        }
        if (!question.revealed) {
          return { ok: false, reason: 'أظهروا الإجابة قبل تسجيل النتيجة.' };
        }
        const availability = getOutcomeAvailability({
          question,
          timer: question.timer,
        });
        if (!availability[outcome]?.available) {
          return { ok: false, reason: availability[outcome]?.reason ?? 'نتيجة غير مسموحة.' };
        }
        const { activeTeamId, defendingTeamId } = getActiveAndDefending(state);
        if (!activeTeamId || !defendingTeamId) {
          return { ok: false, reason: 'الفريقان غير محددين.' };
        }

        const scoring = computeScoreDeltas({
          basePoints: question.points,
          outcome,
          activeTeamId,
          defendingTeamId,
          activePowerIds: question.activePowers,
        });

        const winningTeamId =
          outcome === OUTCOMES.ACTIVE
            ? activeTeamId
            : outcome === OUTCOMES.DEFENDING
              ? defendingTeamId
              : null;

        const teams = state.teams.map((team) => ({
          ...team,
          score: team.score + (scoring.deltas[team.id] ?? 0),
        }));

        const stats = {
          [TEAM_A_ID]: { ...state.stats[TEAM_A_ID] },
          [TEAM_B_ID]: { ...state.stats[TEAM_B_ID] },
        };
        for (const teamId of TEAM_IDS) {
          const delta = Math.abs(scoring.deltas[teamId] ?? 0);
          stats[teamId].biggestSwing = Math.max(stats[teamId].biggestSwing ?? 0, delta);
        }
        if (winningTeamId) {
          stats[winningTeamId].tilesWon = (stats[winningTeamId].tilesWon ?? 0) + 1;
          stats[winningTeamId].correctAnswers =
            (stats[winningTeamId].correctAnswers ?? 0) + 1;
        }
        const stoleAndWon =
          Boolean(question.stolenByTeamId) && winningTeamId === question.stolenByTeamId;
        const ordinarySteal = outcome === OUTCOMES.DEFENDING && !question.stolenByTeamId;
        if (ordinarySteal || stoleAndWon) {
          stats[winningTeamId].successfulSteals =
            (stats[winningTeamId].successfulSteals ?? 0) + 1;
        }

        const tileResult = {
          played: true,
          tileId: question.tileId,
          questionId: question.questionId,
          sourceBackupId: question.sourceBackupId,
          categoryId: question.categoryId,
          basePoints: question.points,
          activeTeamId,
          outcome,
          winningTeamId,
          deltas: scoring.deltas,
          ledger: scoring.ledger,
          activePowers: [...question.activePowers],
          stolenByTeamId: question.stolenByTeamId ?? null,
          resolvedAt: now,
        };
        const tileResults = { ...state.tileResults, [question.tileId]: tileResult };
        const playedCount = countPlayedTiles(tileResults);
        const nextStage =
          playedCount >= TOTAL_PRIMARY_TILES ? STAGES.PODIUM : STAGES.BOARD;
        // الدور يظل مرتبطًا بصاحب السؤال الأصلي، حتى لو سرقه الفريق الثاني.
        const nextTurn = otherTeamId(question.originalActiveTeamId ?? activeTeamId);
        const historyEntry = {
          tileId: question.tileId,
          categoryId: question.categoryId,
          points: question.points,
          questionId: question.questionId,
          outcome,
          winningTeamId,
          deltas: scoring.deltas,
          ledger: scoring.ledger,
          activePowers: [...question.activePowers],
          resolvedAt: now,
        };

        set({
          teams,
          stats,
          tileResults,
          currentQuestion: null,
          currentStage: nextStage,
          currentTurnTeamId: nextTurn,
          matchFinishedAt: nextStage === STAGES.PODIUM ? now : state.matchFinishedAt,
          matchHistory: [...state.matchHistory, historyEntry].slice(-36),
          recoveryNotice: null,
        });

        return {
          ok: true,
          outcome,
          winningTeamId,
          deltas: scoring.deltas,
          ledger: scoring.ledger,
          stage: nextStage,
        };
      },

      /**
       * تسجيل النتيجة على الخادم. النتيجة في الواجهة نسبية للفريق المجاوب حاليًا
       * (بعد السرقة)، والخادم يحسبها نسبة لصاحب الدور الأصلي، فنترجمها قبل الإرسال.
       */
      async resolveOnServer(outcome, now = Date.now()) {
        const state = get();
        const question = state.currentQuestion;
        if (!state.server.matchCode) return get().resolveQuestion(outcome, now);
        if (state.currentStage !== STAGES.ARENA || !question) {
          return { ok: false, reason: 'ما في سؤال مفتوح.' };
        }
        if (!question.revealed) {
          return { ok: false, reason: 'أظهروا الإجابة قبل تسجيل النتيجة.' };
        }
        const availability = getOutcomeAvailability({ question, timer: question.timer });
        if (!availability[outcome]?.available) {
          return { ok: false, reason: availability[outcome]?.reason ?? 'نتيجة غير مسموحة.' };
        }
        if (state.server.pending) {
          return { ok: false, reason: 'النتيجة قيد الحفظ على السيرفر…' };
        }

        const originalActiveTeamId = question.originalActiveTeamId ?? question.activeTeamId;
        const activeTeamId = question.activeTeamId;
        const defendingTeamId = otherTeamId(activeTeamId);
        const uiWinnerId =
          outcome === OUTCOMES.ACTIVE
            ? activeTeamId
            : outcome === OUTCOMES.DEFENDING
              ? defendingTeamId
              : null;
        const backendOutcome =
          outcome === OUTCOMES.NOBODY
            ? OUTCOMES.NOBODY
            : uiWinnerId === originalActiveTeamId
              ? OUTCOMES.ACTIVE
              : OUTCOMES.DEFENDING;

        set({ server: { ...state.server, pending: true, error: null } });
        try {
          const raw = await api.resolve({
            matchCode: state.server.matchCode,
            tileKey: question.tileId,
            outcome: backendOutcome,
            activeTeamId: originalActiveTeamId,
            powersApplied: question.activePowers,
            expectedVersion: state.server.version,
          });
          const mapped = toFrontendResolveResult(raw);
          const current = get();
          const winningTeamId = mapped.tileResult.winningTeamId;
          const deltas = mapped.tileResult.deltas ?? {};
          const ledger = mapped.tileResult.ledger ?? [];

          const stats = {
            [TEAM_A_ID]: { ...current.stats[TEAM_A_ID] },
            [TEAM_B_ID]: { ...current.stats[TEAM_B_ID] },
          };
          for (const teamId of TEAM_IDS) {
            stats[teamId].biggestSwing = Math.max(
              stats[teamId].biggestSwing ?? 0,
              Math.abs(deltas[teamId] ?? 0),
            );
          }
          if (winningTeamId) {
            stats[winningTeamId].tilesWon = (stats[winningTeamId].tilesWon ?? 0) + 1;
            stats[winningTeamId].correctAnswers =
              (stats[winningTeamId].correctAnswers ?? 0) + 1;
            if (winningTeamId !== originalActiveTeamId) {
              stats[winningTeamId].successfulSteals =
                (stats[winningTeamId].successfulSteals ?? 0) + 1;
            }
          }

          const tileResult = {
            ...mapped.tileResult,
            tileId: question.tileId,
            questionId: mapped.tileResult.questionId ?? question.questionId,
            categoryId: question.categoryId,
            basePoints: question.points,
            activeTeamId,
            defendingTeamId,
            outcome: resultOutcome({ winningTeamId }, activeTeamId),
            stolenByTeamId: question.stolenByTeamId ?? null,
            sourceBackupId: question.sourceBackupId ?? null,
            resolvedAt: now,
          };
          const tileResults = { ...current.tileResults, [question.tileId]: tileResult };
          const playedCount = countPlayedTiles(tileResults);
          const nextStage =
            mapped.match.status === 'completed' || playedCount >= TOTAL_PRIMARY_TILES
              ? STAGES.PODIUM
              : STAGES.BOARD;
          const historyEntry = {
            tileId: question.tileId,
            categoryId: question.categoryId,
            points: question.points,
            questionId: tileResult.questionId,
            outcome: tileResult.outcome,
            winningTeamId,
            deltas,
            ledger,
            activePowers: tileResult.activePowers,
            resolvedAt: now,
          };

          set({
            teams: current.teams.map((team) => ({
              ...team,
              score: mapped.match.scores[team.id] ?? team.score,
            })),
            stats,
            tileResults,
            currentQuestion: null,
            currentStage: nextStage,
            currentTurnTeamId: mapped.match.currentTurnTeamId,
            matchFinishedAt:
              nextStage === STAGES.PODIUM ? now : current.matchFinishedAt,
            matchHistory: [...current.matchHistory, historyEntry].slice(-36),
            content: {
              ...current.content,
              questions: {
                ...current.content.questions,
                [mapped.question.id]: mapped.question,
              },
              tiles: current.content.tiles.map((tile) =>
                tile.id === question.tileId
                  ? { ...tile, played: true, questionId: mapped.question.id }
                  : tile,
              ),
            },
            server: {
              ...current.server,
              version: mapped.match.version,
              status: mapped.match.status,
              winner: mapped.match.winner ?? null,
              online: true,
              error: null,
              pending: false,
            },
            recoveryNotice: null,
          });

          return {
            ok: true,
            outcome,
            winningTeamId,
            deltas,
            ledger,
            stage: nextStage,
          };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({
            server: { ...get().server, pending: false, online: false, error: message },
            recoveryNotice: message,
          });
          if (isVersionConflict(error)) await get().syncServerMatch();
          return { ok: false, reason: message };
        }
      },

      resolveTeamWinOnline(teamId, now = Date.now()) {
        const question = get().currentQuestion;
        if (!question) return Promise.resolve({ ok: false, reason: 'ما في سؤال مفتوح.' });
        if (!TEAM_IDS.includes(teamId)) return Promise.resolve({ ok: false, reason: 'الفريق غير معروف.' });
        return get().resolveOnServer(
          teamId === question.activeTeamId ? OUTCOMES.ACTIVE : OUTCOMES.DEFENDING,
          now,
        );
      },

      resolveNobodyOnline(now = Date.now()) {
        return get().resolveOnServer(OUTCOMES.NOBODY, now);
      },

      /** تعديل المقدم يمر بالخادم، ويحدث النقاط من رده الرسمي. */
      async adjustScoreOnline(teamId, amount, now = Date.now()) {
        const state = get();
        if (!state.server.matchCode) return get().adjustScore(teamId, amount, now);
        if (state.currentStage !== STAGES.BOARD) {
          return { ok: false, reason: 'التعديل اليدوي من اللوحة.' };
        }
        if (!TEAM_IDS.includes(teamId)) return { ok: false, reason: 'الفريق غير معروف.' };
        if (amount !== 100 && amount !== -100) return { ok: false, reason: 'التعديل ±100 فقط.' };
        if (state.server.pending) return { ok: false, reason: 'السيرفر يحدّث النقاط…' };

        set({ server: { ...state.server, pending: true, error: null } });
        try {
          const raw = await api.adjustScore({
            matchCode: state.server.matchCode,
            teamId,
            delta: amount,
            reason: 'تعديل يدوي من المقدم',
            expectedVersion: state.server.version,
          });
          const current = get();
          set({
            teams: serverScores(raw.match, current.teams),
            manualAdjustments: [...current.manualAdjustments, { teamId, amount, at: now }].slice(-200),
            server: {
              ...current.server,
              version: raw.match.version,
              status: raw.match.status,
              winner: raw.match.winner ?? null,
              online: true,
              error: null,
              pending: false,
            },
          });
          return { ok: true };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({
            server: { ...get().server, pending: false, online: false, error: message },
            recoveryNotice: message,
          });
          if (isVersionConflict(error)) await get().syncServerMatch();
          return { ok: false, reason: message };
        }
      },

      /**
       * كل قوة تُفعّل على الخادم. الخادم يتحقق من الملكية والجانب والنافذة
       * الزمنية ومن أنها ما استُخدمت، ويرجع الحالة الرسمية للسؤال والمباراة.
       */
      async activatePowerOnline(powerId, teamId = null, now = Date.now()) {
        const state = get();
        if (!state.server.matchCode) return get().activatePower(powerId, teamId, now);
        const question = state.currentQuestion;
        if (state.currentStage !== STAGES.ARENA || !question) {
          return { ok: false, reason: 'القوى تنفع داخل السؤال فقط.' };
        }
        const owner = teamId ?? powerOwner(state.draft.picks, powerId);
        if (!owner) return { ok: false, reason: 'هالقوة ما انسحبت بهالمباراة.' };
        const ownsPower = state.draft.picks.some(
          (pick) => pick.teamId === owner && pick.powerId === powerId,
        );
        if (!ownsPower) return { ok: false, reason: 'هالقوة مو من اختيار هالفريق.' };
        const draftedPowerIds = state.draft.picks
          .filter((pick) => pick.teamId === owner)
          .map((pick) => pick.powerId);
        const eligibility = getPowerEligibility({
          powerId,
          teamId: owner,
          question,
          timer: question.timer,
          draftedPowerIds,
          usedPowerIds: state.usedPowerIds[owner] ?? [],
          now,
        });
        if (!eligibility.eligible) return { ok: false, reason: eligibility.reason };
        if (state.server.pending) return { ok: false, reason: 'السيرفر يحدّث السؤال…' };

        set({ server: { ...state.server, pending: true, error: null } });
        try {
          const raw = await api.activatePower({
            matchCode: state.server.matchCode,
            tileKey: question.tileId,
            powerId,
            teamId: owner,
            expectedVersion: state.server.version,
          });
          const mapped = toFrontendActivationResult(raw);
          const current = get();
          const active = current.currentQuestion ?? question;
          const nextQuestion = mapped.question;
          const used = Array.from(new Set([...(current.usedPowerIds[owner] ?? []), powerId]));
          const stats = {
            ...current.stats,
            [owner]: {
              ...current.stats[owner],
              powersUsed: (current.stats[owner]?.powersUsed ?? 0) + 1,
            },
          };
          const switched = mapped.activation.switched;
          const openedAt = mapped.tile.openedAt ? Date.parse(mapped.tile.openedAt) : now;
          const activeTeamId = mapped.activation.activeTeamId ?? active.activeTeamId;
          const noiseUntil = mapped.activation.noiseUntil
            ? Date.parse(mapped.activation.noiseUntil)
            : switched
              ? null
              : active.noiseUntil;

          set({
            currentQuestion: {
              ...active,
              questionId: nextQuestion.id,
              sourceBackupId: mapped.backupUsed ?? active.sourceBackupId,
              usedBackupIds: mapped.backupUsed
                ? [...active.usedBackupIds, mapped.backupUsed]
                : active.usedBackupIds,
              activePowers: mapped.tile.activePowers ?? active.activePowers,
              activeTeamId,
              stolenByTeamId: powerId === 'steal' ? owner : active.stolenByTeamId,
              timer: switched ? startTimer(createTimer(), openedAt) : active.timer,
              noiseUntil,
              wrongGuesses: switched ? 0 : active.wrongGuesses,
            },
            currentTurnTeamId: powerId === 'steal' ? owner : current.currentTurnTeamId,
            content: {
              ...current.content,
              questions: { ...current.content.questions, [nextQuestion.id]: nextQuestion },
              tiles: current.content.tiles.map((tile) =>
                tile.id === question.tileId
                  ? {
                      ...tile,
                      questionId: nextQuestion.id,
                      openedAt: mapped.tile.openedAt,
                      activePowers: mapped.tile.activePowers,
                    }
                  : tile,
              ),
            },
            usedPowerIds: { ...current.usedPowerIds, [owner]: used },
            stats,
            server: {
              ...current.server,
              version: mapped.match.version,
              status: mapped.match.status,
              winner: mapped.match.winner ?? null,
              online: true,
              error: null,
              pending: false,
            },
            recoveryNotice: null,
          });
          return {
            ok: true,
            powerId,
            teamId: owner,
            stoleQuestion: powerId === 'steal',
            activeTeamId,
            backup: mapped.backupUsed
              ? { id: mapped.backupUsed, question: nextQuestion.question }
              : null,
          };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({
            server: { ...get().server, pending: false, online: false, error: message },
            recoveryNotice: message,
          });
          if (isVersionConflict(error)) await get().syncServerMatch();
          return { ok: false, reason: message };
        }
      },

      resolveTeamWin(teamId, now = Date.now()) {
        const state = get();
        const question = state.currentQuestion;
        if (!question) return { ok: false, reason: 'ما في سؤال مفتوح.' };
        if (!TEAM_IDS.includes(teamId)) return { ok: false, reason: 'الفريق غير معروف.' };
        if (teamId === question.activeTeamId) {
          return get().resolveQuestion(OUTCOMES.ACTIVE, now);
        }
        return get().resolveQuestion(OUTCOMES.DEFENDING, now);
      },

      resolveNobody(now = Date.now()) {
        return get().resolveQuestion(OUTCOMES.NOBODY, now);
      },

      abandonQuestion(now = Date.now()) {
        const state = get();
        if (state.currentStage !== STAGES.ARENA || !state.currentQuestion) {
          return { ok: false, reason: 'ما في سؤال نتركه.' };
        }
        // الخانة تبقى غير ملعوبة، والدور يرجع مثل ما كان قبل فتحها.
        set({
          currentQuestion: null,
          currentStage: STAGES.BOARD,
          // لو انسرق السؤال، يرجع الدور لصاحبه الأصلي عند الانسحاب بدون تسجيل.
          currentTurnTeamId: state.currentQuestion.originalActiveTeamId ?? state.currentTurnTeamId,
          recoveryNotice: null,
        });
        return { ok: true };
      },

      /** يغلق جلسة السؤال على الخادم ثم يرجع للوحة. */
      async abandonQuestionOnline(now = Date.now()) {
        const state = get();
        const question = state.currentQuestion;
        if (!state.server.matchCode) return get().abandonQuestion(now);
        if (state.currentStage !== STAGES.ARENA || !question) {
          return { ok: false, reason: 'ما في سؤال نتركه.' };
        }
        if (state.server.pending) return { ok: false, reason: 'السيرفر يحدّث السؤال…' };

        set({ server: { ...state.server, pending: true, error: null } });
        try {
          const raw = await api.abandonTile({
            matchCode: state.server.matchCode,
            tileKey: question.tileId,
            expectedVersion: state.server.version,
          });
          const mapped = toFrontendTileSessionResult(raw);
          const current = get();
          set({
            currentQuestion: null,
            currentStage: STAGES.BOARD,
            currentTurnTeamId:
              question.originalActiveTeamId ?? current.currentTurnTeamId,
            content: {
              ...current.content,
              tiles: current.content.tiles.map((tile) =>
                tile.id === question.tileId
                  ? { ...tile, questionId: mapped.question.id, openedAt: null }
                  : tile,
              ),
            },
            server: {
              ...current.server,
              version: mapped.match.version,
              status: mapped.match.status,
              winner: mapped.match.winner ?? null,
              online: true,
              error: null,
              pending: false,
            },
            recoveryNotice: null,
          });
          return { ok: true };
        } catch (error) {
          const message = apiErrorMessage(error);
          set({
            server: { ...get().server, pending: false, online: false, error: message },
            recoveryNotice: message,
          });
          if (isVersionConflict(error)) await get().syncServerMatch();
          return { ok: false, reason: message };
        }
      },
    }),
    {
      name: STORAGE_KEY,
      version: 1,
      storage: safeStorage,
      partialize: (state) => ({
        schemaVersion: state.schemaVersion,
        currentStage: state.currentStage,
        teams: state.teams,
        coinToss: state.coinToss,
        draft: state.draft,
        currentTurnTeamId: state.currentTurnTeamId,
        tileResults: state.tileResults,
        currentQuestion: state.currentQuestion,
        usedPowerIds: state.usedPowerIds,
        stats: state.stats,
        selectedCategorySlugs: state.selectedCategorySlugs,
        manualAdjustments: state.manualAdjustments,
        matchHistory: state.matchHistory,
        matchStartedAt: state.matchStartedAt,
        matchFinishedAt: state.matchFinishedAt,
        settings: state.settings,
        // نسخة استرداد فقط؛ السيرفر يبقى مرجع المحتوى والنقاط عند عودته.
        server: state.server,
        content: state.content,
      }),
      migrate: (persistedState, version) => {
        // إصدار 1 هو الحالي؛ نمرره كما هو حتى يلتقط merge أي تلف ويعرض إشعارًا.
        if (version >= 1) return persistedState;
        return sanitizePersistedState(persistedState).state;
      },
      merge: (persistedState, currentState) => {
        // أول زيارة: لا يوجد مفتاح محفوظ. لا نعرض إشعار تلف في هالحالة.
        if (persistedState === null || persistedState === undefined) {
          return currentState;
        }
        const result = sanitizePersistedState(persistedState);
        if (!result.valid) {
          return {
            ...currentState,
            recoveryNotice:
              result.notice || 'الملف المحفوظ كان غير صالح، بدأنا من جديد بأمان.',
          };
        }
        return {
          ...currentState,
          ...result.state,
          recoveryNotice: result.notice || null,
        };
      },
    },
  ),
);

export const selectAllTilesPlayed = (state) =>
  countPlayedTiles(state.tileResults) >= TOTAL_PRIMARY_TILES;

export const selectActiveTeam = (state) =>
  state.teams.find((team) => team.id === state.currentTurnTeamId) ?? null;

export const selectDefendingTeam = (state) =>
  state.teams.find((team) => team.id === otherTeamId(state.currentTurnTeamId)) ?? null;

export const selectQuestionPayload = (state) => {
  const questionId = state.currentQuestion?.questionId;
  if (!questionId) return null;
  return state.content?.questions?.[questionId] ?? getSessionQuestion(questionId);
};

export const selectQuestionElapsedMs = (state, now = Date.now()) =>
  state.currentQuestion ? getElapsedMs(state.currentQuestion.timer, now) : 0;

export { otherTeamId, getElapsedMs };
