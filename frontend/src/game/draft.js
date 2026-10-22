export const DRAFT_PICK_COUNT = 6;

/** ترتيب السحب الثعباني: A → B → B → A → A → B (ثلاث قوى لكل فريق). */
export function buildDraftOrder(firstTeamId, secondTeamId) {
  if (!firstTeamId || !secondTeamId || firstTeamId === secondTeamId) {
    throw new Error('ترتيب السحب يحتاج فريقين مختلفين.');
  }
  return [firstTeamId, secondTeamId, secondTeamId, firstTeamId, firstTeamId, secondTeamId];
}

export function getDraftTeamAt(order, pickIndex) {
  if (!Array.isArray(order) || pickIndex < 0 || pickIndex >= order.length) return null;
  return order[pickIndex] ?? null;
}

export function getCurrentDraftTeam(order, picks) {
  return getDraftTeamAt(order, picks?.length ?? 0);
}

export function isDraftComplete(picks) {
  return Array.isArray(picks) && picks.length === DRAFT_PICK_COUNT;
}

export function getPickedPowerIds(picks) {
  return new Set((picks ?? []).map((pick) => pick.powerId));
}

export function getDraftedPowersForTeam(picks, teamId) {
  return (picks ?? [])
    .filter((pick) => pick.teamId === teamId)
    .map((pick) => pick.powerId);
}

export function countTeamPicks(picks, teamId) {
  return (picks ?? []).filter((pick) => pick.teamId === teamId).length;
}

/**
 * تحقق كامل من اكتمال السحب: ست اختيارات، ثلاث لكل فريق، وقوى فريدة داخل
 * كل فريق. الفريقان يقدرون يختارون نفس القوة، فما في حجز عالمي للقوى.
 * يُستخدم قبل الانتقال للوحة.
 */
export function validateDraft(picks, allPowerIds, teamIds) {
  const errors = [];
  if (!Array.isArray(picks)) return { ok: false, errors: ['اختيارات السحب غير صالحة.'] };
  if (picks.length !== DRAFT_PICK_COUNT) errors.push('لازم تكملون ست اختيارات.');
  const powerSet = new Set(allPowerIds);
  const perTeam = Object.fromEntries(teamIds.map((id) => [id, 0]));
  const seenByTeam = Object.fromEntries(teamIds.map((id) => [id, new Set()]));

  for (const pick of picks) {
    if (!pick || !pick.teamId || !pick.powerId) {
      errors.push('اختيار سحب ناقص البيانات.');
      continue;
    }
    if (!teamIds.includes(pick.teamId)) errors.push(`اختيار لفريق غير معروف: ${pick.teamId}`);
    if (!powerSet.has(pick.powerId)) errors.push(`قوة غير معروفة: ${pick.powerId}`);
    const teamSeen = seenByTeam[pick.teamId];
    if (teamSeen?.has(pick.powerId)) {
      errors.push(`القوة ${pick.powerId} اختيرت مرتين من نفس الفريق.`);
    }
    teamSeen?.add(pick.powerId);
    if (perTeam[pick.teamId] !== undefined) perTeam[pick.teamId] += 1;
  }

  for (const teamId of teamIds) {
    if (perTeam[teamId] !== 3) errors.push(`الفريق ${teamId} لازم ياخذ ثلاث قوى بالضبط.`);
  }

  return { ok: errors.length === 0, errors };
}

/** فحص مبسّط قابل للاستخدام في الاختبارات والقواعد. */
export function draftProducesThreePowersPerTeam(firstTeamId, secondTeamId, picks) {
  if (picks.length !== DRAFT_PICK_COUNT) return false;
  for (const teamId of [firstTeamId, secondTeamId]) {
    const teamPowers = picks
      .filter((pick) => pick.teamId === teamId)
      .map((pick) => pick.powerId);
    if (teamPowers.length !== 3) return false;
    if (new Set(teamPowers).size !== teamPowers.length) return false;
  }
  return true;
}
