import TeamAvatar from '../components/TeamAvatar.jsx';
import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { POWERS, POWER_BY_ID } from '../data/mockData.js';
import { avatarForTeam, colorForTeam } from '../game/constants.js';
import { getCurrentDraftTeam, getDraftedPowersForTeam, validateDraft } from '../game/draft.js';
import { useGameStore } from '../store/gameStore.js';
import soundEngine from '../utils/soundEngine.js';
import HeaderScoreboard from '../components/HeaderScoreboard.jsx';
import Icon from '../components/Icon.jsx';
import PowerCard from '../components/PowerCard.jsx';
import StageBackdrop from '../components/StageBackdrop.jsx';
import { HERO_ART } from '../ui/categoryArt.js';

function OrderRail({ order, picks }) {
  const teams = useGameStore((state) => state.teams);
  return (
    <div className="flex flex-wrap items-center justify-center gap-1.5" aria-label="ترتيب السحب">
      {order.map((teamId, index) => {
        const team = teams.find((item) => item.id === teamId);
        const done = Boolean(picks[index]);
        const current = picks.length === index;
        const color = colorForTeam(team);
        return (
          <div key={`${teamId}-${index}`} className="flex items-center gap-1.5">
            <span
              className={`flex min-h-[2.4rem] items-center gap-1.5 rounded-xl border px-2 py-1.5 text-xs font-bold transition ${
                current ? 'bg-white/[0.08] text-ink-900' : 'bg-white text-stone-600'
              } ${done ? 'opacity-65' : ''}`}
              style={{
                borderColor: current ? `${color.hex}88` : done ? `${color.hex}30` : 'rgba(148,163,184,0.11)',
                boxShadow: current ? `0 0 20px ${color.hex}20` : 'none',
              }}
              aria-current={current ? 'step' : undefined}
            >
              <span
                className="grid h-5 w-5 place-items-center rounded-md text-xs font-black"
                style={{
                  backgroundColor: current || done ? `${color.hex}22` : 'rgba(255,255,255,0.04)',
                  color: current || done ? color.hex : '#64748b',
                }}
              >
                {done ? <Icon name="Check" size={10} /> : index + 1}
              </span>
              <span className="max-w-[5.5rem] truncate">{team?.name}</span>
            </span>
            {index < order.length - 1 && (
              <span aria-hidden="true" className="h-px w-2 bg-stone-100" />
            )}
          </div>
        );
      })}
    </div>
  );
}

function Bench({ team }) {
  const picks = useGameStore((state) => state.draft.picks);
  const color = colorForTeam(team);
  const drafted = getDraftedPowersForTeam(picks, team.id);
  return (
    <div
      className="relative overflow-hidden rounded-2xl border bg-white p-3"
      style={{ borderColor: `${color.hex}2c` }}
    >
      <span
        aria-hidden="true"
        className="absolute inset-y-0 start-0 w-[3px]"
        style={{ background: `linear-gradient(180deg, ${color.hex}, ${color.hex}22)` }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -end-10 -top-12 h-32 w-32 rounded-full blur-2xl"
        style={{ backgroundColor: `${color.hex}0f` }}
      />
      <div className="relative flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-lg" aria-hidden="true"><TeamAvatar team={team} /></span>
          <div className="min-w-0">
            <p className="text-xs font-bold tracking-wider text-stone-600">حقيبة القوى</p>
            <h3 className="truncate text-xs font-black text-ink-900">{team.name}</h3>
          </div>
        </div>
        <span className="rounded-full border border-stone-200 bg-stone-100/70 px-2 py-0.5 text-xs font-bold text-stone-600">
          <span className="ltr text-ink-900">{drafted.length}</span> / <span className="ltr">3</span>
        </span>
      </div>
      <div className="relative mt-2 grid grid-cols-3 gap-1.5">
        {[0, 1, 2].map((index) => {
          const powerId = drafted[index];
          const power = powerId ? POWER_BY_ID[powerId] : null;
          return (
            <div
              key={index}
              className={`flex min-h-[3.6rem] flex-col items-center justify-center rounded-xl border px-1 py-1.5 text-center ${
                power
                  ? 'border-stone-200 bg-white/[0.05]'
                  : 'border-dashed border-stone-200 bg-stone-100/70'
              }`}
            >
              {power ? (
                <>
                  <span
                    className="grid h-7 w-7 place-items-center rounded-lg"
                    style={{ backgroundColor: `${color.hex}18`, color: color.hex }}
                  >
                    <Icon name={power.icon} size={15} />
                  </span>
                  <span className="mt-1 line-clamp-2 text-xs font-bold leading-3 text-stone-600">
                    {power.name}
                  </span>
                </>
              ) : (
                <>
                  <span className="grid h-6 w-6 place-items-center rounded-full border border-dashed border-stone-300 text-stone-600">
                    <Icon name="Plus" size={10} />
                  </span>
                  <span className="mt-1 text-xs font-bold text-stone-600">فاضي</span>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DraftView() {
  const teams = useGameStore((state) => state.teams);
  const draft = useGameStore((state) => state.draft);
  const draftPowerOnline = useGameStore((state) => state.draftPowerOnline);
  const enterBoard = useGameStore((state) => state.enterBoard);
  const serverPending = useGameStore((state) => state.server.pending);
  const [feedback, setFeedback] = useState('');

  const currentTeamId = getCurrentDraftTeam(draft.order, draft.picks);
  const currentTeam = teams.find((team) => team.id === currentTeamId) ?? null;
  const currentColor = currentTeam ? colorForTeam(currentTeam) : null;
  const currentAvatar = currentTeam ? avatarForTeam(currentTeam) : null;
  const picksComplete = draft.picks.length >= 6;
  const validation = useMemo(
    () => validateDraft(draft.picks, POWERS.map((power) => power.id), teams.map((team) => team.id)),
    [draft.picks, teams],
  );
  const unpicked = POWERS.filter(
    (power) => !draft.picks.some((pick) => pick.powerId === power.id),
  );

  const pick = async (powerId) => {
    const result = await draftPowerOnline(powerId);
    if (result.ok) {
      const team = teams.find((item) => item.id === result.teamId);
      setFeedback(`اختار ${team?.name ?? 'الفريق'} «${POWER_BY_ID[powerId].name}».`);
      soundEngine.power();
    } else {
      setFeedback(result.reason ?? 'ما صار الاختيار.');
    }
  };

  return (
    <div className="stage-bg-photo relative min-h-[100svh] pb-5">
      <StageBackdrop image={HERO_ART.crowd.src} position="center 45%" variant="spotlight" />
      <div className="relative z-10">
        <HeaderScoreboard compact />

        <main className="mx-auto w-full max-w-[1760px] px-3 pt-3 xl:px-6">
          <div className="draft-intro photo-card relative overflow-hidden rounded-2xl border border-stone-200">
            <img
              src={HERO_ART.crowd.src}
              alt=""
              aria-hidden="true"
              className="absolute inset-0 h-full w-full object-cover opacity-45"
              style={{ objectPosition: HERO_ART.crowd.position }}
              decoding="async"
            />
            <div className="absolute inset-0 bg-transparent" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_18%_0%,rgba(167,139,250,0.16),transparent_55%)]" />

            <div className="relative flex flex-col items-center justify-between gap-3 px-4 py-4 text-center sm:px-5 lg:flex-row lg:text-right">
              <div className="min-w-0">
                <p className="eyebrow text-violet-700">المرحلة الثانية</p>
                <h1 className="tv-title mt-1 font-black text-ink-900">سحب القوى</h1>
                <p className="mx-auto mt-1 max-w-2xl text-balance text-xs leading-5 text-stone-600 sm:text-xs sm:leading-6 lg:mx-0">
                  سحب ثعباني <span className="ltr font-bold text-stone-600">A → B → B → A → A → B</span>. كل فريق
                  ياخذ ثلاث قوى، ويقدر الفريقان يختارون نفس القوة.
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2 rounded-xl border border-stone-200 bg-stone-100/70 px-3 py-2">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-violet-400/10 text-violet-700">
                  <Icon name="Zap" size={15} />
                </span>
                <div className="text-right">
                  <p className="text-xs font-bold text-stone-600">البطاقات المتاحة</p>
                  <p className="ltr tv-number text-lg font-black leading-none text-ink-900">07</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-3">
            <OrderRail order={draft.order} picks={draft.picks} />
          </div>

          <section
            className="mx-auto mt-3 flex w-full max-w-4xl flex-wrap items-center justify-between gap-3 rounded-2xl border px-3 py-2.5"
            style={{
              borderColor: currentTeam ? `${currentColor.hex}40` : 'rgba(148,163,184,0.14)',
              backgroundColor: currentTeam ? `${currentColor.hex}0b` : 'rgba(7,11,24,0.7)',
              boxShadow: currentTeam ? `0 0 30px ${currentColor.hex}0c` : 'none',
            }}
            aria-live="polite"
          >
            {picksComplete ? (
              <>
                <div className="flex items-center gap-2.5">
                  <span className="grid h-10 w-10 place-items-center rounded-xl border border-emerald-400/25 bg-emerald-400/10 text-emerald-700">
                    <Icon name="Check" size={19} />
                  </span>
                  <div>
                    <p className="text-xs font-bold text-emerald-700">السحب مكتمل</p>
                    <p className="text-xs font-black text-ink-900">
                      {unpicked.length > 0
                        ? 'القوى اللي ما انسحبت ما راح تنزل هالمباراة.'
                        : 'كل القوى نزلت — وبعضها عند الفريقين.'}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {unpicked.map((power) => (
                    <span
                      key={power.id}
                      className="rounded-lg border border-stone-300 bg-stone-100 px-2 py-1 text-xs font-bold text-stone-600 line-through"
                    >
                      {power.name}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div className="flex min-w-0 items-center gap-2.5">
                  <span
                    className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border text-lg"
                    style={{ borderColor: `${currentColor?.hex}55`, backgroundColor: `${currentColor?.hex}18` }}
                    aria-hidden="true"
                  >
                    <TeamAvatar avatar={currentAvatar} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-bold tracking-wider text-stone-600">الاختيار الآن على</p>
                    <p className="truncate text-sm font-black" style={{ color: currentColor?.hex }}>
                      {currentTeam?.name}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="hidden h-1.5 w-28 overflow-hidden rounded-full bg-white/10 sm:block">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${(draft.picks.length / 6) * 100}%`,
                        backgroundColor: currentColor?.hex,
                      }}
                    />
                  </div>
                  <div className="text-left">
                    <p className="ltr tv-number text-lg font-black leading-none text-ink-900">
                      {draft.picks.length + 1}
                      <span className="text-stone-600">/6</span>
                    </p>
                    <p className="mt-0.5 text-xs font-bold text-stone-600">اختيار</p>
                  </div>
                </div>
              </>
            )}
          </section>

          {feedback && (
            <p
              className="mt-2 text-center text-xs font-bold text-brand-700"
              role="status"
            >
              {feedback}
            </p>
          )}

          <div className="mt-4 flex items-end justify-between gap-2">
            <div>
              <p className="text-xs font-black tracking-[0.2em] text-stone-600">طاولة القوى</p>
              <h2 className="mt-0.5 text-sm font-black text-ink-900">اختاروا بحكمة… القوى تُستخدم مرة واحدة</h2>
            </div>
            <p className="hidden text-xs font-bold text-stone-600 sm:block">
              <span className="ltr">3</span> قوى لكل فريق
            </p>
          </div>

          <section className="mt-2 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4" aria-label="بطاقات القوى">
            {POWERS.map((power) => {
              const pickByCurrent = draft.picks.find(
                (item) => item.powerId === power.id && item.teamId === currentTeamId,
              );
              const pickByOther = draft.picks.find(
                (item) => item.powerId === power.id && item.teamId !== currentTeamId,
              );
              const owners = draft.picks
                .filter((item) => item.powerId === power.id)
                .map((item) => teams.find((team) => team.id === item.teamId))
                .filter(Boolean);
              const ownerTeam = owners[0] ?? null;
              const disabled = Boolean(pickByCurrent) || picksComplete || !currentTeam || serverPending;
              return (
                <motion.div
                  key={power.id}
                  initial={{ opacity: 1, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.22 }}
                >
                  <PowerCard
                    power={power}
                    ownerTeam={ownerTeam}
                    ownerTeams={owners}
                    status={pickByCurrent || (picksComplete && owners.length > 0) ? 'drafted' : 'available'}
                    onAction={picksComplete ? null : () => pick(power.id)}
                    actionLabel={
                      pickByOther
                        ? `خذها أيضًا لـ${currentTeam?.name ?? 'الفريق'}`
                        : `اختار لـ${currentTeam?.name ?? 'الفريق'}`
                    }
                    disabled={disabled}
                    showTiming
                  />
                </motion.div>
              );
            })}
          </section>

          <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
            {teams.map((team) => (
              <Bench key={team.id} team={team} />
            ))}
          </div>

          <div className="mx-auto mt-4 flex w-full max-w-xl flex-col items-center gap-1.5">
            <button
              type="button"
              disabled={!picksComplete || !validation.ok}
              onClick={() => {
                const result = enterBoard();
                if (result.ok) soundEngine.power();
                else setFeedback(result.reason ?? 'ما نقدر ندخل اللوحة.');
              }}
              className={`flex min-h-[3rem] w-full items-center justify-center gap-2 rounded-2xl border px-5 py-3 text-sm font-black transition ${
                picksComplete && validation.ok
                  ? 'border-amber-100/35 brand-button--primary text-ink-950 shadow-[0_16px_40px_rgba(232,182,77,0.18)] hover:brightness-105 active:scale-[0.99]'
                  : 'cursor-not-allowed border-stone-300 bg-stone-100 text-stone-600'
              }`}
            >
              <Icon name="Swords" size={18} />
              ادخل اللوحة
              <Icon name="ChevronLeft" size={17} />
            </button>
            {!picksComplete && (
              <p className="text-xs font-bold text-amber-800">
                لازم تكملون ست اختيارات قبل اللوحة — باقي{' '}
                <span className="ltr">{6 - draft.picks.length}</span>.
              </p>
            )}
            {picksComplete && !validation.ok && (
              <p className="text-xs font-bold text-red-700">{validation.errors[0]}</p>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
