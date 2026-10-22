export const OUTCOMES = Object.freeze({
  ACTIVE: 'active_team',
  DEFENDING: 'defending_team',
  NOBODY: 'nobody',
});

export const VALID_OUTCOMES = Object.freeze(Object.values(OUTCOMES));

export const SCORING_REASONS = Object.freeze({
  BASE_WIN: 'base_win',
  STEAL_WIN: 'steal_win',
  PIT_DEDUCTION: 'pit_deduction',
  TRAP_DEDUCTION: 'trap_deduction',
  DOUBLE_WIN: 'double_win',
  DOUBLE_LOSS: 'double_loss',
});

/**
 * دالة نقية قابلة للاختبار. ترتيب التطبيق ثابت:
 * 1) الجائزة الأساسية (أو ضعفها مع «دبل أو ابلع»).
 * 2) خصم «الحفرة» من الخصم عند فوز صاحب الدور.
 * 3) خصم «الفخ» من صاحب الدور عند عدم فوزه.
 *
 * تتوقع activePowerIds قائمة معرّفات القوى المفعّلة لهذا السؤال (بدون تكرار).
 */
export function computeScoreDeltas({
  basePoints,
  outcome,
  activeTeamId,
  defendingTeamId,
  activePowerIds = [],
}) {
  if (!Number.isFinite(basePoints) || basePoints <= 0) {
    throw new Error('قيمة الخانة لازم تكون رقمًا موجبًا.');
  }
  if (!VALID_OUTCOMES.includes(outcome)) {
    throw new Error(`نتيجة غير معروفة: ${outcome}`);
  }
  if (!activeTeamId || !defendingTeamId || activeTeamId === defendingTeamId) {
    throw new Error('يلزم فريقان مختلفان لحساب النقاط.');
  }

  const powers = new Set(activePowerIds);
  const hasDouble = powers.has('double');
  const hasPit = powers.has('pit');
  const hasTrap = powers.has('trap');
  const ledger = [];
  const deltas = { [activeTeamId]: 0, [defendingTeamId]: 0 };

  const add = (teamId, delta, reason) => {
    if (!delta) return;
    deltas[teamId] = (deltas[teamId] ?? 0) + delta;
    ledger.push({
      teamId,
      delta,
      reason,
      powerId:
        reason === SCORING_REASONS.PIT_DEDUCTION
          ? 'pit'
          : reason === SCORING_REASONS.TRAP_DEDUCTION
            ? 'trap'
            : reason === SCORING_REASONS.DOUBLE_WIN || reason === SCORING_REASONS.DOUBLE_LOSS
              ? 'double'
              : null,
    });
  };

  if (outcome === OUTCOMES.ACTIVE) {
    if (hasDouble) {
      add(activeTeamId, basePoints * 2, SCORING_REASONS.DOUBLE_WIN);
    } else {
      add(activeTeamId, basePoints, SCORING_REASONS.BASE_WIN);
    }
    if (hasPit) {
      // «الحفرة» تخصم قيمة أساسية واحدة فقط، حتى مع الدبل.
      add(defendingTeamId, -basePoints, SCORING_REASONS.PIT_DEDUCTION);
    }
  } else if (outcome === OUTCOMES.DEFENDING) {
    add(defendingTeamId, basePoints, SCORING_REASONS.STEAL_WIN);
    if (hasDouble) {
      add(activeTeamId, -basePoints, SCORING_REASONS.DOUBLE_LOSS);
    }
    if (hasTrap) {
      add(activeTeamId, -Math.floor(basePoints / 2), SCORING_REASONS.TRAP_DEDUCTION);
    }
  } else {
    if (hasDouble) {
      add(activeTeamId, -basePoints, SCORING_REASONS.DOUBLE_LOSS);
    }
    if (hasTrap) {
      add(activeTeamId, -Math.floor(basePoints / 2), SCORING_REASONS.TRAP_DEDUCTION);
    }
  }

  return {
    outcome,
    basePoints,
    activeTeamId,
    defendingTeamId,
    deltas,
    ledger,
  };
}

/** يعيد وصفًا عربيًا قصيرًا لسطر دفتر النقاط، للعرض في السجل. */
export function describeLedgerReason(reason) {
  const labels = {
    [SCORING_REASONS.BASE_WIN]: 'جائزة السؤال',
    [SCORING_REASONS.STEAL_WIN]: 'جائزة السرقة',
    [SCORING_REASONS.PIT_DEDUCTION]: 'خصم الحفرة',
    [SCORING_REASONS.TRAP_DEDUCTION]: 'خصم الفخ',
    [SCORING_REASONS.DOUBLE_WIN]: 'دبل أو ابلع — فوز',
    [SCORING_REASONS.DOUBLE_LOSS]: 'دبل أو ابلع — خسارة',
  };
  return labels[reason] ?? reason;
}
