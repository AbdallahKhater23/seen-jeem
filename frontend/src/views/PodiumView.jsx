import TeamAvatar from '../components/TeamAvatar.jsx';
import { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import confetti from 'canvas-confetti';
import { CATEGORY_BY_ID, POWER_BY_ID, TILE_BY_ID } from '../data/mockData.js';
import { avatarForTeam, colorForTeam } from '../game/constants.js';
import { getPodiumResult } from '../game/podium.js';
import { useGameStore } from '../store/gameStore.js';
import soundEngine from '../utils/soundEngine.js';
import Icon from '../components/Icon.jsx';
import StageBackdrop from '../components/StageBackdrop.jsx';
import { HERO_ART } from '../ui/categoryArt.js';

function Confetti({ disabled }) {
  useEffect(() => {
    if (disabled) return undefined;
    let cancelled = false;
    const colors = ['#f5c96a', '#22d3ee', '#a78bfa', '#f472b6', '#34d399'];
    const bursts = [
      { delay: 0, x: 0.2 },
      { delay: 420, x: 0.5 },
      { delay: 840, x: 0.8 },
    ];
    const timers = bursts.map((burst) =>
      setTimeout(() => {
        if (cancelled) return;
        confetti({
          particleCount: 64,
          spread: 70,
          startVelocity: 40,
          gravity: 0.9,
          scalar: 0.7,
          ticks: 200,
          origin: { x: burst.x, y: 0.72 },
          colors,
          disableForReducedMotion: true,
        });
      }, burst.delay),
    );
    return () => {
      cancelled = true;
      timers.forEach((timer) => clearTimeout(timer));
      confetti.reset();
    };
  }, [disabled]);
  return null;
}

function TeamStatCard({ team, stats, isWinner, isTie }) {
  const color = colorForTeam(team);
  return (
    <motion.section
      initial={{ opacity: 1, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative overflow-hidden rounded-3xl border bg-white ${
        isWinner ? 'panel-gold' : ''
      }`}
      style={{
        borderColor: isWinner ? `${color.hex}77` : 'rgba(148,163,184,0.14)',
        boxShadow: isWinner ? `0 18px 45px ${color.hex}16` : '0 8px 30px rgba(94,46,24,0.06)',
      }}
      aria-label={`نتيجة ${team.name}`}
    >
      <div className="results-banner photo-card relative h-24 overflow-hidden border-b border-stone-200">
        <img
          src={HERO_ART.crowd.src}
          alt=""
          aria-hidden="true"
          className="h-full w-full object-cover opacity-45"
          style={{ objectPosition: 'center 35%' }}
          loading="lazy"
          decoding="async"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0"
          style={{
            background: `linear-gradient(180deg, ${color.hex}16, #fff8ef)`,
          }}
        />
        {isWinner && (
          <span
            className="absolute start-3 top-3 flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-black text-ink-950 shadow-[0_4px_18px_rgba(0,0,0,0.3)]"
            style={{ backgroundColor: color.hex }}
          >
            <Icon name="Crown" size={11} /> الفائز
          </span>
        )}
        {isTie && (
          <span className="absolute start-3 top-3 rounded-full border border-stone-200 bg-white/10 px-2.5 py-1 text-xs font-black text-ink-900 backdrop-blur">
            مناصفة
          </span>
        )}
        <span className="absolute end-3 top-3 text-xs font-black tracking-[0.2em] text-ink-900">
          النتيجة النهائية
        </span>
      </div>

      <div className="relative p-4 xl:p-5">
        <div className="flex items-center gap-3">
          <span
            className="grid h-14 w-14 place-items-center rounded-2xl border text-3xl"
            style={{
              borderColor: `${color.hex}55`,
              backgroundColor: `${color.hex}14`,
              boxShadow: `inset 0 0 24px ${color.hex}10`,
            }}
            aria-hidden="true"
          >
            <TeamAvatar team={team} />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-black text-ink-900 xl:text-2xl">{team.name}</h2>
            <p className="mt-0.5 text-xs font-bold text-stone-600">
              {isWinner ? 'على قمة المنصة' : isTie ? 'شريك في اللقب' : 'وصيف المباراة'}
            </p>
          </div>
          <p className="ltr tv-number text-4xl font-black leading-none xl:text-5xl" style={{ color: color.hex }}>
            {team.score}
          </p>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-2">
          {[
            { label: 'خانات فازوا فيها', value: stats.tilesWon, icon: 'Target' },
            { label: 'سرقات ناجحة', value: stats.successfulSteals, icon: 'Swords' },
            { label: 'قوى استخدموها', value: stats.powersUsed, icon: 'Zap' },
            { label: 'أكبر تحول بالنقاط', value: stats.biggestSwing, icon: 'Flame' },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-xl border border-stone-200 bg-stone-100/70 px-2.5 py-2"
            >
              <dt className="flex items-center gap-1.5 text-xs font-bold text-stone-600">
                <Icon name={item.icon} size={10} style={{ color: color.hex }} />
                {item.label}
              </dt>
              <dd className="ltr tv-number mt-1 text-lg font-black leading-none text-ink-900">{item.value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </motion.section>
  );
}

function ResultsLog({ history }) {
  const teams = useGameStore((state) => state.teams);
  const recent = [...history].slice(-6).reverse();
  if (recent.length === 0) return null;
  return (
    <section className="panel rounded-2xl p-3 xl:p-4" aria-label="آخر نتائج الخانات">
      <h2 className="flex items-center gap-1.5 text-[13px] font-black text-ink-900">
        <Icon name="Flame" size={13} className="text-amber-800" />
        آخر الخانات
      </h2>
      <div className="mt-2 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {recent.map((entry) => {
          const team = teams.find((item) => item.id === entry.winningTeamId);
          const tile = TILE_BY_ID[entry.tileId];
          const color = team ? colorForTeam(team) : null;
          return (
            <div
              key={`${entry.tileId}-${entry.resolvedAt}`}
              className="flex items-center justify-between gap-2 rounded-xl border border-stone-200 bg-stone-100/70 px-2.5 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-xs font-bold text-stone-600">
                  {CATEGORY_BY_ID[entry.categoryId]?.name ?? entry.categoryId} ·{' '}
                  <span className="ltr">{entry.points}</span>
                </p>
                <p className="truncate text-xs text-stone-600">
                  {entry.activePowers.length > 0
                    ? entry.activePowers.map((id) => POWER_BY_ID[id]?.name).filter(Boolean).join('، ')
                    : 'بدون قوى'}
                </p>
              </div>
              <span
                className="shrink-0 rounded-full px-1.5 py-0.5 text-xs font-bold"
                style={
                  team
                    ? { color: color.hex, backgroundColor: `${color.hex}16` }
                    : { color: '#94a3b8', backgroundColor: '#1e293b' }
                }
              >
                {team ? team.name : 'ولا أحد'}
              </span>
              <span className="sr-only">{tile ? `خانة ${tile.points}` : ''}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function PodiumView() {
  const teams = useGameStore((state) => state.teams);
  const stats = useGameStore((state) => state.stats);
  const history = useGameStore((state) => state.matchHistory);
  const manualAdjustments = useGameStore((state) => state.manualAdjustments);
  const newMatch = useGameStore((state) => state.newMatch);
  const matchCode = useGameStore((state) => state.server.matchCode);
  const syncServerMatch = useGameStore((state) => state.syncServerMatch);
  const reducedMotion = useReducedMotion();
  const [confirming, setConfirming] = useState(false);
  const victoryPlayed = useRef(false);

  const { tie, winner } = getPodiumResult(teams);

  useEffect(() => {
    if (victoryPlayed.current) return;
    victoryPlayed.current = true;
    soundEngine.victory();
  }, []);

  // النتيجة النهائية تأتي من الخادم؛ المزامنة تصحّح أي فرق في النسخة المحلية.
  useEffect(() => {
    if (matchCode) void syncServerMatch();
  }, [matchCode, syncServerMatch]);

  return (
    <div className="stage-bg-photo relative min-h-[100svh] overflow-x-hidden">
      <StageBackdrop image={HERO_ART.crowd.src} position="center 40%" variant="hero" />
      <Confetti disabled={reducedMotion} />

      <div className="relative z-10 mx-auto flex min-h-[100svh] w-full max-w-[1500px] flex-col justify-center px-3 py-5 sm:px-5 xl:px-8">
        <header className="text-center">
          <motion.div
            initial={{ opacity: 1, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-amber-200/40 bg-amber-300/10 text-amber-800"
          >
            <span aria-hidden="true" className="absolute inset-[-8px] rounded-full border border-amber-200/15" />
            <span aria-hidden="true" className="absolute inset-[-16px] rounded-full border border-amber-200/[0.07]" />
            <Icon name="Trophy" size={26} />
          </motion.div>
          <p className="mt-4 text-xs font-black tracking-[0.3em] text-amber-800">نهاية المباراة</p>

          {tie ? (
            <>
              <h1 className="mt-2 text-balance text-[clamp(2.4rem,5vw,4.5rem)] font-black leading-tight text-ink-900">
                اللقب <span className="gold-text">مناصفة</span>
              </h1>
              <p className="mx-auto mt-2 max-w-lg text-balance text-xs leading-6 text-stone-600">
                النقاط متساوية — ما نعلن فائز. يبقى الفخر للفريقين، والقرار للمقدم.
              </p>
            </>
          ) : (
            <>
              <h1 className="mt-2 text-balance text-[clamp(2.4rem,5vw,4.5rem)] font-black leading-tight text-ink-900">
                الفائز{' '}
                <span
                  className="whitespace-nowrap"
                  style={{ color: colorForTeam(winner).hex, textShadow: `0 0 38px ${colorForTeam(winner).hex}45` }}
                >
                  {winner.name}
                </span>
              </h1>
              <p className="mt-2 flex items-center justify-center gap-2 text-xs font-bold text-stone-600">
                <span className="text-2xl" aria-hidden="true"><TeamAvatar team={winner} /></span>
                <span>
                  بفارق{' '}
                  <span className="ltr tv-number font-black text-ink-900">
                    {Math.abs(teams[0].score - teams[1].score)}
                  </span>{' '}
                  نقطة
                </span>
              </p>
            </>
          )}

          <div className="mx-auto mt-4 h-px w-40 rule-gold" />
        </header>

        <motion.div
          initial={{ opacity: 1, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mt-5 grid gap-3 md:grid-cols-2"
        >
          {teams.map((team) => (
            <TeamStatCard
              key={team.id}
              team={team}
              stats={stats[team.id]}
              isWinner={winner?.id === team.id}
              isTie={tie}
            />
          ))}
        </motion.div>

        <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_0.8fr]">
          <ResultsLog history={history} />

          <section className="panel rounded-2xl p-3 xl:p-4" aria-label="ملخص المباراة">
            <h2 className="flex items-center gap-1.5 text-[13px] font-black text-ink-900">
              <Icon name="Award" size={13} className="text-amber-800" />
              ملخص سريع
            </h2>
            <ul className="mt-2 space-y-2 text-xs text-stone-600">
              <li className="flex items-center justify-between gap-2 border-b border-stone-200 pb-2">
                <span>الخانات المكتملة</span>
                <span className="ltr tv-number font-bold text-ink-900">36 / 36</span>
              </li>
              <li className="flex items-center justify-between gap-2 border-b border-stone-200 pb-2">
                <span>القوى المستخدمة</span>
                <span className="ltr tv-number font-bold text-ink-900">
                  {stats[teams[0].id].powersUsed + stats[teams[1].id].powersUsed} / 6
                </span>
              </li>
              <li className="flex items-center justify-between gap-2 border-b border-stone-200 pb-2">
                <span>تعديلات المقدم اليدوية</span>
                <span className="ltr tv-number font-bold text-ink-900">{manualAdjustments.length}</span>
              </li>
              <li className="flex items-center justify-between gap-2">
                <span>حالة اللقب</span>
                <span className="font-bold text-amber-800">{tie ? 'تعادل' : 'فوز واضح'}</span>
              </li>
            </ul>
          </section>
        </div>

        <div className="mt-5 flex flex-col items-center gap-2 pb-2">
          {!confirming ? (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              className="flex min-h-[3rem] items-center gap-2 rounded-2xl border border-amber-100/35 brand-button--primary px-6 py-3 text-sm font-black text-ink-950 shadow-[0_16px_40px_rgba(232,182,77,0.18)] transition hover:brightness-105 active:scale-[0.99]"
            >
              <Icon name="RotateCcw" size={17} />
              مباراة جديدة
            </button>
          ) : (
            <div className="flex flex-col items-center gap-2 rounded-2xl border border-amber-400/35 bg-amber-950/25 px-4 py-3 text-center">
              <p className="text-[13px] font-bold leading-5 text-amber-800">
                المباراة السابقة ما راح تكون قابلة للاستئناف بعد البدء من جديد.
                <br />
                تبدأون بنقاط جديدة، وأسماء الفرق تبقى. سجل أسئلة حسابك محفوظ.
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => newMatch()}
                  className="rounded-xl bg-amber-400 px-4 py-2 text-xs font-black text-ink-950"
                >
                  نعم، ابدأ من جديد
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="rounded-xl border border-stone-200 px-3 py-2 text-xs font-bold text-stone-600"
                >
                  رجوع
                </button>
              </div>
            </div>
          )}
          <p className="text-xs text-stone-600">المنصة تظهر فقط بعد لعب كل الخانات الـ36.</p>
        </div>
      </div>
    </div>
  );
}
