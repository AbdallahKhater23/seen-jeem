import { OUTCOMES } from './scoring.js';

/**
 * بعد إظهار الإجابة، المقدم يختار أي فريق جاوب صح — مو شرط صاحب الدور.
 * فوز الفريق الثاني يُسجّل كـ«سرقة» بدون نافذة وقت منفصلة.
 */
export function getOutcomeAvailability({ question }) {
  const revealed = Boolean(question?.revealed);
  const reason = revealed ? '' : 'أظهروا الإجابة أولًا.';

  return {
    [OUTCOMES.ACTIVE]: { available: revealed, reason },
    [OUTCOMES.DEFENDING]: { available: revealed, reason },
    [OUTCOMES.NOBODY]: { available: revealed, reason },
  };
}

export function outcomeForTeam(teamId, activeTeamId) {
  return teamId === activeTeamId ? OUTCOMES.ACTIVE : OUTCOMES.DEFENDING;
}
