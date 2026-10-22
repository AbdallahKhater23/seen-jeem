import { beforeEach, describe, expect, it } from 'vitest';
import { BACKUPS, TILES, POWERS } from '../data/mockData.js';
import {
  STAGES,
  STORAGE_KEY,
  TEAM_A_ID as A,
  TEAM_B_ID as B,
} from '../game/constants.js';
import { getPodiumResult } from '../game/podium.js';
import { createInitialGameState } from '../game/state.js';
import { useGameStore } from './gameStore.js';

const api = () => useGameStore.getState();
const STANDARD = ['pit', 'trap', 'steal', 'double', 'noise', 'switch'];

function setupMatch(sequence = STANDARD) {
  expect(api().finishCoinToss(A, 1000).ok).toBe(true);
  expect(api().startDraft(1000).ok).toBe(true);
  sequence.forEach((powerId, index) => {
    const result = api().draftPower(powerId, 1100 + index);
    expect(result.ok, `pick ${powerId}: ${result.reason ?? ''}`).toBe(true);
  });
  const board = api().enterBoard();
  expect(board.ok, board.reason ?? '').toBe(true);
}

function tileOf(points, categoryId = 'football') {
  return TILES.find((tile) => tile.points === points && tile.categoryId === categoryId);
}

beforeEach(() => {
  window.localStorage.clear();
  useGameStore.setState({ ...createInitialGameState() });
});

describe('lobby and draft store flow', () => {
  it('blocks draft start before the coin toss', () => {
    expect(api().startDraft(1000).ok).toBe(false);
  });

  it('finishes a toss once and builds the exact snake order', () => {
    expect(api().finishCoinToss(A).ok).toBe(true);
    expect(api().coinToss).toEqual({ result: A, completed: true });
    expect(api().draft.order).toEqual([A, B, B, A, A, B]);
    expect(api().finishCoinToss(B).ok).toBe(false);
  });

  it('gives each team exactly three unique powers and leaves the rest undrafted', () => {
    setupMatch();
    const picks = api().draft.picks;
    expect(picks).toHaveLength(6);
    expect(picks.filter((pick) => pick.teamId === A)).toHaveLength(3);
    expect(picks.filter((pick) => pick.teamId === B)).toHaveLength(3);
    expect(new Set(picks.map((pick) => pick.powerId)).size).toBe(6);
    const undrafted = POWERS.filter(
      (power) => !picks.some((pick) => pick.powerId === power.id),
    );
    expect(undrafted).toHaveLength(POWERS.length - 6);
    expect(api().currentStage).toBe(STAGES.BOARD);
    expect(api().currentTurnTeamId).toBe(A);
  });

  it('allows both teams to pick the same power but not twice within one team', () => {
    api().finishCoinToss(A);
    api().startDraft();
    expect(api().draftPower('pit').ok).toBe(true);
    expect(api().draftPower('pit').ok).toBe(true);
    expect(api().draftPower('pit').ok).toBe(false);
    expect(api().draftPower('trap').ok).toBe(true);
    expect(api().draft.picks.map((pick) => pick.teamId)).toEqual([A, B, B]);
    expect(api().draft.picks.filter((pick) => pick.powerId === 'pit')).toHaveLength(2);
  });

  it('rejects team color collisions but allows name edits', () => {
    expect(api().updateTeam(A, { color: 'pink' }).ok).toBe(false);
    expect(api().updateTeam(A, { name: 'فريقنا' }).ok).toBe(true);
    expect(api().teams[0].name).toBe('فريقنا');
  });
});

describe('board and resolution', () => {
  it('does not score before reveal, then resolves exactly once and alternates turn', () => {
    setupMatch();
    const tile = tileOf(400);
    expect(api().selectTile(tile.id, 5000).ok).toBe(true);
    expect(api().currentStage).toBe(STAGES.ARENA);
    expect(api().currentQuestion.timer.running).toBe(true);
    expect(api().currentQuestion.timer.elapsedMs).toBe(0);
    expect(api().resolveTeamWin(A, 6000).ok).toBe(false);
    expect(api().revealAnswer(6000).ok).toBe(true);
    const result = api().resolveTeamWin(A, 7000);
    expect(result.ok).toBe(true);
    expect(result.outcome).toBe('active_team');
    expect(api().teams.find((team) => team.id === A).score).toBe(400);
    expect(api().teams.find((team) => team.id === B).score).toBe(0);
    expect(api().tileResults[tile.id].played).toBe(true);
    expect(api().currentStage).toBe(STAGES.BOARD);
    expect(api().currentTurnTeamId).toBe(B);

    const after = api().teams.map((team) => team.score);
    expect(api().resolveTeamWin(A, 8000).ok).toBe(false);
    expect(api().teams.map((team) => team.score)).toEqual(after);
    expect(api().currentQuestion).toBeNull();
  });

  it('records the second team answer as a steal without any steal window', () => {
    setupMatch();
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    api().revealAnswer(7000);
    const result = api().resolveTeamWin(B, 8000);
    expect(result.ok).toBe(true);
    expect(result.outcome).toBe('defending_team');
    expect(api().teams.find((team) => team.id === B).score).toBe(400);
    expect(api().stats[B].successfulSteals).toBe(1);
    // الدور يرجع لصاحب السؤال الأصلي (B) بعد التسجيل.
    expect(api().currentTurnTeamId).toBe(B);
  });

  it('lets both teams be selected after reveal', () => {
    setupMatch();
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    api().revealAnswer(6000);
    expect(api().resolveTeamWin(A, 7000).ok).toBe(true);

    const tile2 = tileOf(400, 'worldcup') ?? TILES.find((item) => item.points === 400 && item.id !== tile.id);
    api().selectTile(tile2.id, 8000);
    api().revealAnswer(9000);
    expect(api().resolveTeamWin(B, 10000).ok).toBe(true);
  });

  it('resolves nobody, marks the tile played, and alternates turn', () => {
    setupMatch();
    const tile = tileOf(200);
    api().selectTile(tile.id, 5000);
    api().revealAnswer(6000);
    expect(api().resolveNobody(7000).ok).toBe(true);
    expect(api().teams.every((team) => team.score === 0)).toBe(true);
    expect(api().tileResults[tile.id].winningTeamId).toBeNull();
    expect(api().currentTurnTeamId).toBe(B);
  });

  it('abandons without marking the tile or switching the turn', () => {
    setupMatch();
    const tile = tileOf(600);
    const turn = api().currentTurnTeamId;
    api().selectTile(tile.id, 5000);
    expect(api().abandonQuestion(6000).ok).toBe(true);
    expect(api().currentStage).toBe(STAGES.BOARD);
    expect(api().currentTurnTeamId).toBe(turn);
    expect(api().tileResults[tile.id]).toBeUndefined();
    expect(api().currentQuestion).toBeNull();
  });

  it('logs manual ±100 adjustments and permits negative scores', () => {
    setupMatch();
    expect(api().adjustScore(A, -100, 5000).ok).toBe(true);
    expect(api().adjustScore(A, -100, 6000).ok).toBe(true);
    expect(api().teams.find((team) => team.id === A).score).toBe(-200);
    expect(api().manualAdjustments).toHaveLength(2);
    expect(api().adjustScore(A, 50).ok).toBe(false);
    expect(api().adjustScore(A, 100).ok).toBe(true);
    expect(api().teams.find((team) => team.id === A).score).toBe(-100);
  });
});

describe('powers in the store', () => {
  it('combines pit and double exactly as specified and consumes both once', () => {
    setupMatch();
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    expect(api().activatePower('pit', A, 6000).ok).toBe(true);
    expect(api().activatePower('pit', A, 6000).ok).toBe(false);
    expect(api().activatePower('double', A, 6100).ok).toBe(true);
    expect(api().revealAnswer(6200).ok).toBe(true);
    const result = api().resolveTeamWin(A, 7000);
    expect(result.ok).toBe(true);
    expect(api().teams.find((team) => team.id === A).score).toBe(800);
    expect(api().teams.find((team) => team.id === B).score).toBe(-400);
    expect(api().usedPowerIds[A]).toEqual(['pit', 'double']);
    expect(api().stats[A].powersUsed).toBe(2);
  });

  it('lets both teams use the same drafted power on different turns', () => {
    setupMatch(['pit', 'pit', 'trap', 'double', 'noise', 'switch']);
    const first = tileOf(200);
    api().selectTile(first.id, 5000);
    expect(api().activatePower('pit', A, 6000).ok).toBe(true);
    api().revealAnswer(7000);
    expect(api().resolveTeamWin(A, 8000).ok).toBe(true);

    const second = TILES.find((tile) => tile.points === 200 && tile.id !== first.id);
    api().selectTile(second.id, 9000);
    expect(api().currentQuestion.activeTeamId).toBe(B);
    expect(api().activatePower('pit', B, 10000).ok).toBe(true);
    expect(api().usedPowerIds[A]).toEqual(['pit']);
    expect(api().usedPowerIds[B]).toEqual(['pit']);
  });

  it('applies trap to a steal and records the ledger', () => {
    setupMatch();
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    expect(api().activatePower('trap', B, 6000).ok).toBe(true);
    api().revealAnswer(7000);
    expect(api().resolveTeamWin(B, 8000).ok).toBe(true);
    expect(api().teams.find((team) => team.id === B).score).toBe(400);
    expect(api().teams.find((team) => team.id === A).score).toBe(-200);
    const result = api().tileResults[tile.id];
    expect(result.ledger.map((entry) => entry.reason)).toContain('trap_deduction');
    expect(api().stats[B].successfulSteals).toBe(1);
  });

  it('steal gives the question to the second team instead of the first', () => {
    setupMatch(['pit', 'steal', 'trap', 'double', 'noise', 'switch']);
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    expect(api().currentQuestion.activeTeamId).toBe(A);
    const result = api().activatePower('steal', B, 6000);
    expect(result.ok).toBe(true);
    expect(result.stoleQuestion).toBe(true);
    expect(api().currentQuestion.activeTeamId).toBe(B);
    expect(api().currentQuestion.stolenByTeamId).toBe(B);
    expect(api().currentQuestion.originalActiveTeamId).toBe(A);
    api().revealAnswer(7000);
    expect(api().resolveTeamWin(B, 8000).ok).toBe(true);
    expect(api().teams.find((team) => team.id === B).score).toBe(400);
    expect(api().stats[B].successfulSteals).toBe(1);
    // صاحب السؤال الأصلي هو من يحدد الدور التالي.
    expect(api().currentTurnTeamId).toBe(B);
  });

  it('keeps the stopwatch open past one minute and never auto-closes', () => {
    setupMatch();
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    expect(api().tickQuestionTimer(68000)).toEqual([]);
    expect(api().currentQuestion.timer.running).toBe(true);
    expect(api().currentQuestion.timer.phase).toBe('primary');
    api().revealAnswer(69000);
    expect(api().resolveTeamWin(B, 70000).ok).toBe(true);
  });

  it('two-answer guesses no longer add time', () => {
    setupMatch(['two_answers', 'trap', 'steal', 'pit', 'noise', 'switch']);
    const tile = tileOf(200);
    api().selectTile(tile.id, 5000);
    expect(api().activatePower('two_answers', A, 6000).ok).toBe(true);
    const first = api().registerWrongGuess(7000);
    expect(first.ok).toBe(true);
    expect(api().currentQuestion.wrongGuesses).toBe(1);
    expect(api().currentQuestion.timer.elapsedMs).toBe(0);
    const second = api().registerWrongGuess(8000);
    expect(second.ok).toBe(true);
    expect(api().currentQuestion.wrongGuesses).toBe(2);
    expect(api().registerWrongGuess(9000).ok).toBe(false);
    expect(api().currentQuestion.revealed).toBe(false);
  });

  it('lets the defending team activate multiple distinct defensive powers', () => {
    setupMatch(['pit', 'trap', 'noise', 'double', 'steal', 'switch']);
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    expect(api().activatePower('trap', B, 6000).ok).toBe(true);
    expect(api().activatePower('noise', B, 6100).ok).toBe(true);
    expect(api().currentQuestion.noiseUntil).toBe(18100);
    expect(api().usedPowerIds[B]).toEqual(['trap', 'noise']);
  });

  it('switches to an unused backup, preserves tile value, and resets the timer', () => {
    setupMatch(['switch', 'trap', 'steal', 'double', 'noise', 'pit']);
    const tile = tileOf(200);
    api().selectTile(tile.id, 5000);
    const originalQuestionId = api().currentQuestion.questionId;
    const result = api().activatePower('switch', A, 6000);
    expect(result.ok).toBe(true);
    expect(result.backup).toBeTruthy();
    expect(api().currentQuestion.questionId).not.toBe(originalQuestionId);
    expect(api().currentQuestion.usedBackupIds).toHaveLength(1);
    expect(api().currentQuestion.points).toBe(tile.points);
    expect(api().currentQuestion.categoryId).toBe(tile.categoryId);
    expect(api().currentQuestion.timer.elapsedMs).toBe(0);
    expect(api().currentQuestion.timer.running).toBe(true);
    expect(api().currentQuestion.timer.startedAt).toBe(6000);
    expect(api().activatePower('switch', A, 7000).ok).toBe(false);
  });

  it('rejects switch field after 15 seconds and when backups are exhausted', () => {
    setupMatch(['switch', 'trap', 'steal', 'double', 'noise', 'pit']);
    const tile = tileOf(200);
    api().selectTile(tile.id, 5000);
    const late = api().activatePower('switch', A, 21000);
    expect(late.ok).toBe(false);
    expect(late.reason).toContain('15');
    expect(api().usedPowerIds[A]).toEqual([]);

    useGameStore.setState({
      currentQuestion: {
        ...api().currentQuestion,
        usedBackupIds: BACKUPS.map((backup) => backup.id),
      },
    });
    const exhausted = api().activatePower('switch', A, 6000);
    expect(exhausted.ok).toBe(false);
    expect(api().usedPowerIds[A]).toEqual([]);
  });

  it('rejects powers after reveal and from the wrong team', () => {
    setupMatch();
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    expect(api().activatePower('trap', A, 6000).ok).toBe(false);
    api().revealAnswer(6500);
    expect(api().activatePower('pit', A, 7000).ok).toBe(false);
  });
});

describe('last tile and podium', () => {
  it('routes to podium after 36 tiles and preserves a tie without a winner', () => {
    setupMatch();
    const lastTile = TILES[TILES.length - 1];
    const results = {};
    for (const tile of TILES.slice(0, 35)) {
      results[tile.id] = {
        played: true,
        tileId: tile.id,
        outcome: 'nobody',
        winningTeamId: null,
        basePoints: tile.points,
        deltas: {},
        ledger: [],
        activePowers: [],
      };
    }
    useGameStore.setState({
      tileResults: results,
      teams: api().teams.map((team) => ({ ...team, score: 500 })),
      currentTurnTeamId: A,
      currentStage: STAGES.BOARD,
    });
    expect(api().selectTile(lastTile.id, 5000).ok).toBe(true);
    api().revealAnswer(6000);
    expect(api().resolveNobody(7000).ok).toBe(true);
    expect(api().currentStage).toBe(STAGES.PODIUM);
    expect(api().matchFinishedAt).not.toBeNull();
    expect(Object.keys(api().tileResults)).toHaveLength(36);
    const podium = getPodiumResult(api().teams);
    expect(podium.tie).toBe(true);
    expect(podium.winner).toBeNull();
  });
});

describe('persistence and reset', () => {
  it('persists the open stopwatch and restores it', async () => {
    setupMatch();
    const tile = tileOf(400);
    api().selectTile(tile.id, 5000);
    api().toggleQuestionTimer(6000);
    const raw = window.localStorage.getItem(STORAGE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw);
    expect(parsed.state.currentStage).toBe(STAGES.ARENA);
    expect(parsed.state.currentQuestion.timer.elapsedMs).toBe(1000);
    expect(parsed.state.currentQuestion.timer.running).toBe(false);
    expect(parsed.state.currentQuestion.timer).not.toHaveProperty('intervalId');

    useGameStore.setState({ ...createInitialGameState() });
    window.localStorage.setItem(STORAGE_KEY, raw);
    await useGameStore.persist.rehydrate();

    expect(api().currentStage).toBe(STAGES.ARENA);
    expect(api().currentQuestion.tileId).toBe(tile.id);
    expect(api().currentQuestion.timer.elapsedMs).toBe(1000);
    expect(api().currentQuestion.timer.running).toBe(false);
  });

  it('recovers from corrupt storage to a lobby with a non-blocking notice', async () => {
    useGameStore.setState({ ...createInitialGameState() });
    window.localStorage.setItem(STORAGE_KEY, '{this is not json');
    await useGameStore.persist.rehydrate();
    expect(api().currentStage).toBe(STAGES.LOBBY);
    expect(api().recoveryNotice).toBeTruthy();
  });

  it('resets a saved match to a clean lobby and clears match data', () => {
    setupMatch();
    expect(api().matchStartedAt).not.toBeNull();
    const result = api().resetSavedMatch();
    expect(result.ok).toBe(true);
    expect(api().currentStage).toBe(STAGES.LOBBY);
    expect(api().matchStartedAt).toBeNull();
    expect(api().draft.picks).toEqual([]);
    expect(api().tileResults).toEqual({});
    expect(api().teams.every((team) => team.score === 0)).toBe(true);
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
    expect(stored.state.currentStage).toBe(STAGES.LOBBY);
    expect(stored.state.matchStartedAt).toBeNull();
  });

  it('creates a fresh match while preserving team names and settings', () => {
    expect(api().updateTeam(A, { name: 'النجوم' }).ok).toBe(true);
    api().setMuted(true);
    setupMatch();
    api().newMatch();
    expect(api().currentStage).toBe(STAGES.LOBBY);
    expect(api().teams.find((team) => team.id === A).name).toBe('النجوم');
    expect(api().settings.muted).toBe(true);
    expect(api().matchStartedAt).toBeNull();
    expect(api().coinToss.completed).toBe(false);
  });
});
