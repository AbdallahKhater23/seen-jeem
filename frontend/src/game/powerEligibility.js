import { POWER_BY_ID, selectCompatibleBackup } from '../data/mockData.js';

/**
 * تحقق موحّد من أهلية القوة. لا يعتمد على الواجهة ولا على نصوص مكررة:
 * الجانب (صاحب الدور/المدافع) يأتي من سجل القوى، والتفاصيل الخاصة بكل قوة
 * (مثل الحاجة لسؤال احتياطي) هنا. لا يوجد سقف زمني للسؤال.
 *
 * @returns {{eligible: boolean, reason: string}}
 */
export function getPowerEligibility({
  powerId,
  teamId,
  question,
  timer,
  draftedPowerIds = [],
  usedPowerIds = [],
  now = Date.now(),
}) {
  const fail = (reason) => ({ eligible: false, reason });
  const power = POWER_BY_ID[powerId];
  if (!power) return fail('قوة غير معروفة.');
  if (!question) return fail('ما في سؤال مفتوح.');
  if (!teamId) return fail('الفريق غير محدد.');
  if (!draftedPowerIds.includes(powerId)) return fail('هالقوة مو من اختيار هالفريق.');
  if (usedPowerIds.includes(powerId)) return fail('هالقوة استُخدمت من قبل بهالمباراة.');
  if (question.revealed) return fail('ما تنفع بعد إظهار الإجابة.');

  const isActiveTeam = teamId === question.activeTeamId;
  const sideOk =
    (power.activation.side === 'active' && isActiveTeam) ||
    (power.activation.side === 'defending' && !isActiveTeam);
  if (!sideOk) {
    return fail(
      power.activation.side === 'active'
        ? 'هالقوة للفريق صاحب الدور فقط.'
        : 'هالقوة للفريق الثاني فقط.',
    );
  }

  if (power.activation.maxElapsedMs) {
    const elapsed = now - (question.sessionStartedAt ?? now);
    if (elapsed > power.activation.maxElapsedMs) {
      return fail(
        powerId === 'switch'
          ? 'مرّت أول 15 ثانية من السؤال، ما تقدر تبدّل الميدان.'
          : 'انتهت نافذة التفعيل.',
      );
    }
  }

  if (powerId === 'noise' && (question.noiseUntil ?? 0) > now) {
    return fail('التشويش شغّال بالفعل.');
  }

  if (powerId === 'switch') {
    const backup = selectCompatibleBackup(
      question.categoryId,
      question.points,
      question.usedBackupIds ?? [],
    );
    if (!backup) return fail('ما بقى سؤال احتياطي متوافق مع هالخانة.');
  }

  if (powerId === 'two_answers' && (question.wrongGuesses ?? 0) >= 2) {
    return fail('المحاولتان انتهتا.');
  }

  return { eligible: true, reason: '' };
}

export function eligiblePowersForTeam({
  teamId,
  question,
  timer,
  picks,
  usedPowerIdsByTeam,
  now = Date.now(),
}) {
  const drafted = picks.filter((pick) => pick.teamId === teamId).map((pick) => pick.powerId);
  return drafted.map((powerId) => ({
    powerId,
    ...getPowerEligibility({
      powerId,
      teamId,
      question,
      timer,
      draftedPowerIds: drafted,
      usedPowerIds: usedPowerIdsByTeam?.[teamId] ?? [],
      now,
    }),
  }));
}
