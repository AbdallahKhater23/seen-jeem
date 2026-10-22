import TeamAvatar from './TeamAvatar.jsx';
import { motion } from 'framer-motion';
import { POWER_BY_ID } from '../data/mockData.js';
import { avatarForTeam, colorForTeam } from '../game/constants.js';
import { useGameStore } from '../store/gameStore.js';
import Icon from './Icon.jsx';

function PowerPips({ team, used, picks }) {
  const drafted = picks.filter((pick) => pick.teamId === team.id);
  const ready = drafted.filter(({ powerId }) => !used.includes(powerId)).length;

  if (drafted.length === 0) {
    return (
      <span className="flex items-center gap-1 text-xs text-stone-600">
        <Icon name="Zap" size={11} />
        ما عندهم قوى بعد
      </span>
    );
  }

  return (
    <div className="flex items-center gap-1.5" aria-label={`قوى ${team.name}: ${ready} جاهزة`}>
      <span className="flex items-center gap-1">
        {drafted.map(({ powerId }) => {
          const spent = used.includes(powerId);
          return (
            <span
              key={powerId}
              title={`${POWER_BY_ID[powerId]?.name ?? powerId}${spent ? ' — استُخدمت' : ' — جاهزة'}`}
              className={`grid h-6 w-6 place-items-center rounded-md border ${
                spent
                  ? 'border-stone-300 bg-stone-100 text-stone-600'
                  : 'border-stone-200 bg-white/[0.08] text-stone-800'
              }`}
            >
              <Icon name={POWER_BY_ID[powerId]?.icon ?? 'Sparkles'} size={12} />
              <span className="sr-only">
                {POWER_BY_ID[powerId]?.name ?? powerId}
                {spent ? ' استُخدمت' : ' جاهزة'}
              </span>
            </span>
          );
        })}
      </span>
      <span className="text-xs font-bold text-stone-600">
        <span className="ltr tv-number">{ready}</span> جاهزة
      </span>
    </div>
  );
}

function TeamCard({ team, isActive, showAdjustments, compact }) {
  const picks = useGameStore((state) => state.draft.picks);
  const usedPowerIds = useGameStore((state) => state.usedPowerIds[team.id] ?? []);
  const adjustScore = useGameStore((state) => state.adjustScoreOnline);
  const scorePending = useGameStore((state) => state.server.pending);
  const participants = useGameStore(
    (state) => state.matchParticipants.filter((member) => member.teamId === team.id),
  );
  const color = colorForTeam(team);
  const avatar = avatarForTeam(team);

  return (
    <motion.div
      layout
      className={`team-score-card relative min-w-0 overflow-hidden rounded-2xl border transition-colors ${
        isActive ? 'bg-white/[0.055]' : 'bg-white'
      } ${compact ? 'py-2' : 'py-2.5'}`}
      style={{
        borderColor: isActive ? `${color.hex}77` : 'rgba(148,163,184,0.13)',
        boxShadow: isActive ? `0 0 0 1px ${color.hex}20, 0 14px 38px ${color.hex}18` : 'none',
      }}
    >
      <span
        aria-hidden="true"
        className="absolute inset-y-0 start-0 w-[3px]"
        style={{ background: `linear-gradient(180deg, ${color.hex}, ${color.hex}22)` }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -start-10 -top-16 h-36 w-36 rounded-full blur-3xl"
        style={{ backgroundColor: `${color.hex}${isActive ? '22' : '0f'}` }}
      />

      <div className={`relative flex items-center gap-3 ${compact ? 'px-3' : 'px-3 xl:px-4'}`}>
        <span
          className={`relative grid shrink-0 place-items-center rounded-xl border ${
            compact ? 'h-10 w-10 text-xl' : 'h-11 w-11 text-2xl xl:h-12 xl:w-12'
          }`}
          style={{ borderColor: `${color.hex}66`, backgroundColor: `${color.hex}18` }}
          aria-hidden="true"
        >
          <TeamAvatar avatar={avatar} />
          {isActive && (
            <span
              className="absolute -top-1 -end-1 h-2.5 w-2.5 rounded-full ring-2 ring-ink-950"
              style={{ backgroundColor: color.hex }}
            />
          )}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <h2 className={`truncate font-black text-ink-900 ${compact ? 'text-sm' : 'text-base xl:text-lg'}`}>
              {team.name || 'بدون اسم'}
            </h2>
            {isActive && (
              <span
                className="badge-inverse shrink-0 rounded-full px-2 py-0.5 text-xs font-black"
                style={{ backgroundColor: color.hex }}
              >
                الدور
              </span>
            )}
          </div>
          <div className="mt-0.5 min-w-0">
            <PowerPips team={team} used={usedPowerIds} picks={picks} />
          </div>
          {participants.length > 0 && (
            <p
              className="mt-1 truncate text-xs font-bold text-stone-600"
              title={participants.map((member) => member.displayName || member.username).join('، ')}
            >
              {participants
                .map((member) => member.displayName || member.username)
                .join('، ')}
            </p>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end">
          <span
            className={`ltr tv-number font-black leading-none ${
              compact ? 'text-2xl' : 'text-3xl xl:text-[2.6rem]'
            }`}
            style={{ color: color.hex }}
          >
            {team.score}
          </span>
          {showAdjustments && (
            <div className="mt-1 flex items-center gap-1">
              <button
                type="button"
                onClick={() => adjustScore(team.id, -100)}
                disabled={scorePending}
                aria-label={`خصم 100 من ${team.name}`}
                className="grid h-8 w-8 place-items-center rounded-lg border border-stone-300 bg-stone-100 text-stone-600 transition hover:border-rose-400/60 hover:bg-rose-500/10 hover:text-red-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Icon name="Minus" size={13} />
              </button>
              <span className="text-xs font-bold text-stone-600">تعديل</span>
              <button
                type="button"
                onClick={() => adjustScore(team.id, 100)}
                disabled={scorePending}
                aria-label={`أضف 100 إلى ${team.name}`}
                className="grid h-8 w-8 place-items-center rounded-lg border border-stone-300 bg-stone-100 text-stone-600 transition hover:border-emerald-400/60 hover:bg-emerald-500/10 hover:text-emerald-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Icon name="Plus" size={13} />
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default function HeaderScoreboard({ showAdjustments = false, compact = false, center = null }) {
  const teams = useGameStore((state) => state.teams);
  const currentTurnTeamId = useGameStore((state) => state.currentTurnTeamId);
  const muted = useGameStore((state) => state.settings.muted);
  const setMuted = useGameStore((state) => state.setMuted);

  return (
    <header className="relative z-30 w-full">
      <div className="mx-auto grid w-full max-w-[1900px] grid-cols-1 gap-2 px-3 pt-3 md:grid-cols-[1fr_auto_1fr] md:items-center xl:px-6">
        <TeamCard
          team={teams[0]}
          isActive={currentTurnTeamId === teams[0].id}
          showAdjustments={showAdjustments}
          compact={compact}
        />

        <div className="order-first flex items-center justify-between gap-3 px-1 md:order-none md:flex-col md:justify-center md:gap-1.5 md:px-3">
          <div className="flex items-center gap-2 md:flex-col md:gap-1">
            <span className="relative grid h-9 w-9 place-items-center rounded-xl border border-orange-300/25 bg-orange-400/10 text-brand-700 md:h-10 md:w-10">
              <Icon name="Sparkles" size={17} />
              <span className="absolute inset-0 rounded-xl shadow-[inset_0_0_14px_rgba(34,211,238,0.14)]" />
            </span>
            <span className="flex flex-col text-right md:items-center md:text-center">
              <span className="text-xs font-black tracking-wide text-stone-800 md:text-xs">
                سين جيم
              </span>
              <span className="hidden text-xs font-bold tracking-[0.18em] text-stone-600 md:block">
                اللّمّة تحلى بالتحدّي
              </span>
            </span>
          </div>
          {center}
          <button
            type="button"
            onClick={() => setMuted(!muted)}
            aria-label={muted ? 'تشغيل الصوت' : 'كتم الصوت'}
            aria-pressed={muted}
            className="grid h-9 w-9 place-items-center rounded-lg border border-stone-300 bg-white text-stone-600 transition hover:border-orange-400/50 hover:text-brand-700 active:scale-95"
          >
            <Icon name={muted ? 'VolumeX' : 'Volume2'} size={15} />
          </button>
        </div>

        <TeamCard
          team={teams[1]}
          isActive={currentTurnTeamId === teams[1].id}
          showAdjustments={showAdjustments}
          compact={compact}
        />
      </div>
    </header>
  );
}
