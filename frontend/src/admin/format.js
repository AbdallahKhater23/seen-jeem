const NUMBER_FORMAT = new Intl.NumberFormat('en-US');
const DATE_FORMAT = new Intl.DateTimeFormat('ar-EG', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

const EVENT_LABELS = {
  match_created: 'إنشاء المباراة',
  match_completed: 'اكتمال المباراة',
  match_abandoned: 'ترك المباراة',
  tile_opened: 'فتح خانة',
  tile_revealed: 'إظهار إجابة',
  tile_abandoned: 'ترك سؤال',
  tile_rerolled: 'استبدال سؤال',
  tile_resolved: 'حسم خانة',
  power_drafted: 'سحب قوة',
  power_activated: 'تفعيل قوة',
  score_adjusted: 'تعديل نقاط',
};

const STATUS_LABELS = {
  active: 'نشطة',
  completed: 'مكتملة',
  abandoned: 'متروكة',
  tie: 'تعادل',
};

const OUTCOME_LABELS = {
  team1: 'الفريق الأول',
  team2: 'الفريق الثاني',
  none: 'لا أحد',
};

export function formatNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? NUMBER_FORMAT.format(number) : '—';
}

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : DATE_FORMAT.format(date);
}

export function percent(part, total) {
  const numerator = Number(part);
  const denominator = Number(total);
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator <= 0) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((numerator / denominator) * 100)));
}

export function teamLabel(team) {
  return team === 'team1' ? 'الفريق الأول' : team === 'team2' ? 'الفريق الثاني' : '—';
}

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? status ?? '—';
}

export function eventLabel(eventType) {
  return EVENT_LABELS[eventType] ?? eventType ?? 'حدث';
}

export function eventSummary(event) {
  const payload = event?.payload ?? {};
  switch (event?.event_type) {
    case 'tile_resolved':
      return [
        payload.tile_key,
        OUTCOME_LABELS[payload.outcome] ?? payload.outcome,
        `النتيجة ${formatNumber(payload.score_team1)} — ${formatNumber(payload.score_team2)}`,
      ]
        .filter(Boolean)
        .join(' • ');
    case 'power_drafted':
    case 'power_activated':
      return [payload.power_id, teamLabel(payload.team), payload.tile_key]
        .filter(Boolean)
        .join(' • ');
    case 'tile_opened':
    case 'tile_revealed':
    case 'tile_abandoned':
    case 'tile_rerolled':
      return String(payload.tile_key ?? '—');
    case 'score_adjusted':
      return `${teamLabel(payload.team)} • ${payload.delta > 0 ? '+' : ''}${formatNumber(payload.delta)}`;
    case 'match_completed':
      return `الفائز: ${payload.winner === 'tie' ? 'تعادل' : teamLabel(payload.winner)}`;
    default: {
      const keys = Object.keys(payload);
      if (keys.length === 0) return 'بدون تفاصيل';
      return keys
        .slice(0, 3)
        .map((key) => `${key}: ${String(payload[key])}`)
        .join(' • ');
    }
  }
}
