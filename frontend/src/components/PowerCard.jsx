import { colorForTeam } from '../game/constants.js';
import Icon from './Icon.jsx';

const ACCENTS = {
  rose: { hex: '#fb7185', border: 'border-rose-400/22', text: 'text-red-700', bg: 'bg-rose-500/10', glow: 'shadow-[0_0_34px_rgba(244,63,94,0.14)]' },
  orange: { hex: '#b65720', border: 'border-orange-400/22', text: 'text-brand-700', bg: 'bg-orange-500/10', glow: 'shadow-[0_0_34px_rgba(251,146,60,0.13)]' },
  emerald: { hex: '#34d399', border: 'border-emerald-400/22', text: 'text-emerald-700', bg: 'bg-emerald-500/10', glow: 'shadow-[0_0_34px_rgba(52,211,153,0.13)]' },
  sky: { hex: '#38bdf8', border: 'border-sky-400/22', text: 'text-blue-700', bg: 'bg-sky-500/10', glow: 'shadow-[0_0_34px_rgba(56,189,248,0.13)]' },
  slate: { hex: '#94a3b8', border: 'border-stone-300', text: 'text-stone-600', bg: 'bg-slate-500/10', glow: 'shadow-[0_0_34px_rgba(148,163,184,0.1)]' },
  fuchsia: { hex: '#e879f9', border: 'border-fuchsia-400/22', text: 'text-violet-700', bg: 'bg-fuchsia-500/10', glow: 'shadow-[0_0_34px_rgba(232,121,249,0.13)]' },
  yellow: { hex: '#facc15', border: 'border-yellow-400/22', text: 'text-amber-800', bg: 'bg-yellow-500/10', glow: 'shadow-[0_0_34px_rgba(250,204,21,0.13)]' },
  indigo: { hex: '#818cf8', border: 'border-indigo-400/22', text: 'text-violet-700', bg: 'bg-indigo-500/10', glow: 'shadow-[0_0_34px_rgba(129,140,248,0.14)]' },
};

const TYPE_LABELS = {
  offensive: 'هجومية',
  defensive: 'دفاعية',
  tactical: 'تكتيكية',
};

export default function PowerCard({
  power,
  ownerTeam = null,
  ownerTeams = null,
  status = 'available',
  onAction = null,
  actionLabel = 'اختار',
  disabled = false,
  disabledReason = '',
  compact = false,
  showTiming = true,
  activeLabel = '',
}) {
  const accent = ACCENTS[power.accent] ?? ACCENTS.slate;
  const owners = (ownerTeams ?? (ownerTeam ? [ownerTeam] : [])).filter(Boolean);
  const isUsed = status === 'used';
  const isPicked = status === 'drafted';
  const isActive = status === 'active';
  const cardDisabled = disabled || isUsed || isPicked;

  return (
    <article
      className={`power-card group relative flex h-full flex-col overflow-hidden rounded-2xl border bg-white transition duration-300 ${
        accent.border
      } ${isActive ? `${accent.glow} ring-1 ring-white/25` : ''} ${
        isUsed ? 'opacity-50 saturate-50' : ''
      } ${isPicked ? 'opacity-80' : ''} ${compact ? 'p-3' : 'p-4 xl:p-[1.15rem]'}`}
      aria-label={`${power.name}، ${TYPE_LABELS[power.type]}`}
      style={{ boxShadow: isActive ? `0 0 0 1px ${accent.hex}55, 0 18px 44px ${accent.hex}1f` : undefined }}
    >
      <span
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-px opacity-70"
        style={{ background: `linear-gradient(90deg, transparent, ${accent.hex}, transparent)` }}
      />
      <div
        aria-hidden="true"
        className={`pointer-events-none absolute -start-12 -top-16 h-40 w-40 rounded-full blur-3xl ${accent.bg}`}
      />

      <div className="relative flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2.5">
          <span
            className={`relative grid shrink-0 place-items-center rounded-xl border ${accent.bg} ${accent.text} ${
              compact ? 'h-9 w-9' : 'h-11 w-11 xl:h-12 xl:w-12'
            }`}
            style={{ borderColor: `${accent.hex}33` }}
          >
            <Icon name={power.icon} size={compact ? 18 : 22} strokeWidth={2} />
          </span>
          <div className="min-w-0">
            <h3
              className={`font-black leading-tight text-ink-900 ${
                compact ? 'text-sm' : 'text-lg xl:text-[1.3rem]'
              }`}
            >
              {power.name}
            </h3>
            <p className={`mt-1 flex flex-wrap items-center gap-x-1.5 text-xs font-bold ${accent.text}`}>
              <span>{TYPE_LABELS[power.type]}</span>
              <span className="h-1 w-1 rounded-full bg-current opacity-50" />
              <span>{power.activation.side === 'active' ? 'صاحب الدور' : 'الفريق المدافع'}</span>
            </p>
          </div>
        </div>
        {owners.length > 0 && (
          <span className="flex max-w-[48%] shrink-0 flex-wrap justify-end gap-1">
            {owners.map((team) => {
              const color = colorForTeam(team);
              return (
                <span
                  key={team.id}
                  className="max-w-[7.5rem] truncate rounded-full border px-2 py-0.5 text-xs font-bold"
                  style={{
                    color: color.hex,
                    borderColor: `${color.hex}55`,
                    backgroundColor: `${color.hex}14`,
                  }}
                  title={team.name}
                >
                  {team.name}
                </span>
              );
            })}
          </span>
        )}
      </div>

      {!compact && (
        <p className="relative mt-3 text-[12px] leading-6 text-stone-600 xl:text-[13px] xl:leading-7">
          {power.description}
        </p>
      )}

      {showTiming && (
        <p
          className={`relative mt-2 flex items-start gap-1.5 rounded-lg border border-stone-200 bg-stone-100/70 px-2 py-1 text-xs leading-4 text-stone-600 ${
            compact ? 'line-clamp-2' : ''
          }`}
        >
          <Icon name="Clock" size={11} className="mt-0.5 shrink-0 text-stone-600" />
          <span>{power.timingLabel}</span>
        </p>
      )}

      <div className="relative mt-auto pt-3">
        {isActive && (
          <p className="flex items-center justify-center gap-1 rounded-lg border border-stone-200 bg-white/10 px-2 py-1.5 text-center text-[13px] font-black text-ink-900">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-300" />
            {activeLabel || 'مفعّلة الآن'}
          </p>
        )}
        {isUsed && (
          <p className="rounded-lg border border-stone-300 bg-stone-100 px-2 py-1.5 text-center text-xs font-bold text-stone-600">
            استُخدمت في هالمباراة
          </p>
        )}
        {isPicked && !isUsed && (
          <p className="rounded-lg border border-stone-200 bg-stone-100/70 px-2 py-1.5 text-center text-xs font-bold text-stone-600">
            {owners.length > 1
              ? 'محجوزة للفريقين'
              : `محجوزة لـ${owners[0]?.name ?? ownerTeam?.name ?? 'الفريق'}`}
          </p>
        )}
        {!isPicked && !isUsed && onAction && (
          <>
            <button
              type="button"
              onClick={onAction}
              disabled={cardDisabled}
              className={`flex min-h-[2.6rem] w-full items-center justify-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-black transition ${
                cardDisabled
                  ? 'cursor-not-allowed border-stone-300 bg-stone-100 text-stone-600'
                  : `border-stone-200 bg-white/[0.08] text-ink-900 hover:border-stone-200 hover:bg-white/[0.14] active:scale-[0.98] ${accent.text}`
              }`}
            >
              {!cardDisabled && <Icon name="Zap" size={13} />}
              {actionLabel}
            </button>
            {disabled && disabledReason && (
              <p className="mt-1.5 text-center text-xs leading-4 text-amber-800">{disabledReason}</p>
            )}
          </>
        )}
      </div>
    </article>
  );
}
