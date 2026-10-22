import TeamAvatar from '../components/TeamAvatar.jsx';
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { CATEGORY_BY_ID, POWER_BY_ID, flagUrl } from '../data/mockData.js';
import { avatarForTeam, colorForTeam } from '../game/constants.js';
import { getOutcomeAvailability } from '../game/outcomes.js';
import { ARENA_SHORTCUTS, shouldIgnoreShortcut } from '../game/keyboard.js';
import { getPowerEligibility } from '../game/powerEligibility.js';
import { OUTCOMES } from '../game/scoring.js';
import { formatClock, getElapsedMs } from '../game/timer.js';
import { selectQuestionPayload, useGameStore } from '../store/gameStore.js';
import soundEngine from '../utils/soundEngine.js';
import CareerPathRenderer from '../components/CareerPathRenderer.jsx';
import FootballVisualRenderer from '../components/FootballVisualRenderer.jsx';
import HeaderScoreboard from '../components/HeaderScoreboard.jsx';
import Icon from '../components/Icon.jsx';
import MatchstickRenderer from '../components/MatchstickRenderer.jsx';
import PowerCard from '../components/PowerCard.jsx';
import RadialTimer from '../components/RadialTimer.jsx';
import ReverseRenderer from '../components/ReverseRenderer.jsx';
import SpotDifferenceRenderer from '../components/SpotDifferenceRenderer.jsx';
import StageBackdrop from '../components/StageBackdrop.jsx';
import { HERO_ART, categoryArt } from '../ui/categoryArt.js';

function useNow(intervalMs = 200) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function Shortcut({ keys, children }) {
  return (
    <span className="flex items-center gap-1.5">
      <kbd className="ltr rounded border border-stone-200 bg-white/5 px-1.5 py-0.5 text-xs font-bold text-stone-600">
        {keys}
      </kbd>
      <span>{children}</span>
    </span>
  );
}

function FlagQuestion({ payload }) {
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [payload.id]);
  return (
    <div className="mx-auto flex w-full max-w-md flex-col items-center">
      <div className="flex min-h-52 w-full items-center justify-center rounded-2xl border border-orange-200 bg-white p-3">
        {!broken ? (
          <img
            src={flagUrl(payload.iso2)}
            alt="صورة علم مطلوب التعرف على الدولة"
            className="h-40 w-auto max-w-full rounded-lg border border-stone-200 object-contain shadow-panel"
            onError={() => setBroken(true)}
            loading="eager"
            draggable="false"
          />
        ) : (
          <div className="flex min-h-32 w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-amber-400/30 bg-amber-400/5 px-4 py-6 text-center">
            <Icon name="Flag" size={26} className="text-amber-800" />
            <p className="text-xs font-bold text-amber-800">صورة العلم ما تحمّلت</p>
            <p className="text-xs leading-5 text-stone-600">
              السؤال يظل قابلًا للإجابة من الوصف المكتوب فوق. كمّلوا عادي.
            </p>
          </div>
        )}
      </div>
      <p className="mt-1.5 text-xs text-stone-600">مصدر الصورة: FlagCDN</p>
    </div>
  );
}

function QuestionRenderer({ payload, revealed }) {
  if (!payload) return null;
  if (payload.visual) return <FootballVisualRenderer visual={payload.visual} revealed={revealed} />;
  if (payload.type === 'flag') return <FlagQuestion payload={payload} />;
  if (payload.type === 'career') return <CareerPathRenderer career={payload.career} />;
  if (payload.type === 'spot_diff') {
    return <SpotDifferenceRenderer question={payload} revealed={revealed} />;
  }
  if (payload.type === 'matchstick') {
    return <MatchstickRenderer question={payload} revealed={revealed} />;
  }
  if (payload.type === 'reverse') {
    return <ReverseRenderer question={payload} revealed={revealed} />;
  }
  return (
    <div className="mx-auto grid h-32 w-full max-w-xl place-items-center rounded-2xl border border-stone-200 bg-white/[0.03]">
      <Icon name="CircleHelp" size={44} className="text-slate-700" strokeWidth={1.4} />
    </div>
  );
}

function AnswerPanel({ payload, question, teams, onResolve, onNobody }) {
  const activeTeam = teams.find((team) => team.id === question.activeTeamId);
  const availability = getOutcomeAvailability({ question, timer: question.timer });
  const activePowers = question.activePowers.map((powerId) => POWER_BY_ID[powerId]).filter(Boolean);

  return (
    <motion.div
      initial={{ opacity: 1, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-3 rounded-2xl border border-emerald-400/25 bg-white p-3 xl:p-4"
      aria-live="polite"
    >
      <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
        <div className="min-w-0">
          <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] px-3 py-2.5">
            <p className="flex items-center gap-1.5 text-xs font-black tracking-widest text-emerald-700">
              <Icon name="Check" size={11} />
              الإجابة الرسمية
            </p>
            <p className="mt-1 text-2xl font-black leading-9 text-emerald-700 xl:text-3xl">{payload.answer}</p>
            {payload.tolerance && (
              <p className="mt-1 text-[13px] leading-5 text-stone-600">
                <span className="font-bold text-stone-600">مقبول أيضًا:</span> {payload.tolerance}
              </p>
            )}
          </div>
          <p className="mt-2 text-[13px] leading-6 text-stone-600">{payload.explanation}</p>
          {activePowers.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {activePowers.map((power) => (
                <span key={power.id} className="rounded-md border border-stone-200 bg-white/5 px-1.5 py-0.5 text-xs font-bold text-stone-600">
                  {power.name}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="min-w-0 lg:w-[26rem]">
          <p className="text-center text-sm font-black text-ink-900">منو جاوب صح؟</p>
          <p className="mt-0.5 text-center text-xs text-stone-600">
            اختار صاحب الدور أو الفريق الثاني — الاثنان مسموحان.
          </p>
          <div className="mt-1.5 grid grid-cols-3 gap-1.5">
            {teams.map((team, index) => {
              const outcome = team.id === activeTeam?.id ? OUTCOMES.ACTIVE : OUTCOMES.DEFENDING;
              const state = availability[outcome];
              const color = colorForTeam(team);
              const isOriginalTeam = team.id === question.originalActiveTeamId;
              const answerLabel = question.stolenByTeamId
                ? isOriginalTeam
                  ? 'صاحب الدور الأصلي'
                  : 'سرق السؤال'
                : outcome === OUTCOMES.DEFENDING
                  ? 'جاوب بدال الأول'
                  : 'فوز';
              return (
                <button
                  key={team.id}
                  type="button"
                  disabled={!state.available}
                  onClick={() => onResolve(team.id)}
                  title={state.reason}
                  className={`flex min-h-[5rem] flex-col items-center justify-center rounded-xl border px-1.5 py-1.5 text-center transition ${
                    state.available
                      ? 'border-stone-200 bg-white/[0.07] hover:bg-white/15 active:scale-[0.98]'
                      : 'cursor-not-allowed border-stone-300 bg-stone-100 opacity-55'
                  }`}
                  style={state.available ? { borderColor: `${color.hex}66` } : undefined}
                >
                  <span className="text-lg" aria-hidden="true"><TeamAvatar team={team} /></span>
                  <span className="text-xs font-bold text-stone-600">
                    {answerLabel}
                  </span>
                  <span className="line-clamp-2 text-[13px] font-extrabold leading-4 text-ink-900">{team.name}</span>
                  <span className="ltr mt-0.5 rounded bg-stone-100/70 px-1 text-xs font-bold text-stone-600">[{index + 1}]</span>
                  {!state.available && (
                    <span className="mt-0.5 line-clamp-2 text-[7px] leading-2 text-amber-800">{state.reason}</span>
                  )}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            disabled={!availability[OUTCOMES.NOBODY].available}
            onClick={onNobody}
            title={availability[OUTCOMES.NOBODY].reason}
            className={`mt-1.5 flex w-full items-center justify-center gap-2 rounded-xl border px-2 py-2 text-[13px] font-bold transition ${
              availability[OUTCOMES.NOBODY].available
                ? 'border-stone-300 bg-stone-100 text-stone-800 hover:bg-stone-100'
                : 'cursor-not-allowed border-stone-300 bg-stone-100 text-stone-600'
            }`}
          >
            <span className="ltr rounded bg-stone-100/70 px-1 text-xs">[0]</span>
            ولا أحد جاوب
          </button>
        </div>
      </div>

      <p className="mt-2 text-center text-xs leading-4 text-stone-600">
        الفريقان متاحان بعد الإظهار. اختيار الفريق الثاني يُسجّل سرقة، والتسجيل يتم مرة وحدة.
      </p>
    </motion.div>
  );
}

function PowerRail({ teams, question, timer, now, onActivate }) {
  const picks = useGameStore((state) => state.draft.picks);
  const usedPowerIds = useGameStore((state) => state.usedPowerIds);
  return (
    <div className="panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl">
      <div className="flex items-center justify-between border-b border-stone-200 px-3 py-2">
        <h2 className="flex items-center gap-1.5 text-[13px] font-black text-ink-900">
          <Icon name="Zap" size={14} className="text-amber-800" />
          قوى المباراة
        </h2>
        <span className="text-xs text-stone-600">نافذة التفعيل ظاهرة بكل بطاقة</span>
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-2" tabIndex={0} role="region" aria-label="قوى الفريقين">
        {teams.map((team) => {
          const drafted = picks.filter((pick) => pick.teamId === team.id);
          const color = colorForTeam(team);
          return (
            <section key={team.id} aria-label={`قوى ${team.name}`}>
              <div className="mb-1.5 flex items-center gap-1.5 px-0.5">
                <span className="text-sm" aria-hidden="true"><TeamAvatar team={team} /></span>
                <h3 className="text-xs font-extrabold" style={{ color: color.hex }}>{team.name}</h3>
                <span className="text-xs text-stone-600">
                  {drafted.length - (usedPowerIds[team.id]?.length ?? 0)} جاهزة
                </span>
              </div>
              <div className="space-y-1.5">
                {drafted.map(({ powerId }) => {
                  const power = POWER_BY_ID[powerId];
                  if (!power) return null;
                  const eligibility = getPowerEligibility({
                    powerId,
                    teamId: team.id,
                    question,
                    timer,
                    draftedPowerIds: drafted.map((pick) => pick.powerId),
                    usedPowerIds: usedPowerIds[team.id] ?? [],
                    now,
                  });
                  const used = (usedPowerIds[team.id] ?? []).includes(powerId);
                  const active = question.activePowers.includes(powerId);
                  return (
                    <PowerCard
                      key={powerId}
                      power={power}
                      ownerTeam={team}
                      compact
                      showTiming
                      status={used ? 'used' : active ? 'active' : 'available'}
                      onAction={() => onActivate(powerId, team.id)}
                      actionLabel="تفعيل"
                      disabled={!eligibility.eligible}
                      disabledReason={eligibility.reason}
                    />
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

export default function ArenaView() {
  const question = useGameStore((state) => state.currentQuestion);
  const teams = useGameStore((state) => state.teams);
  const payload = useGameStore((state) => selectQuestionPayload(state));
  const server = useGameStore((state) => state.server);
  const now = useNow(200);
  const [feedback, setFeedback] = useState('');
  const [abandonConfirm, setAbandonConfirm] = useState(false);
  const feedbackTimeout = useRef(null);

  useEffect(() => () => clearTimeout(feedbackTimeout.current), []);
  useEffect(() => {
    setFeedback('');
    setAbandonConfirm(false);
  }, [question?.tileId]);

  useEffect(() => {
    if (!feedback) return undefined;
    clearTimeout(feedbackTimeout.current);
    feedbackTimeout.current = setTimeout(() => setFeedback(''), 5200);
    return () => clearTimeout(feedbackTimeout.current);
  }, [feedback]);

  const timer = question?.timer;
  const elapsedMs = timer ? getElapsedMs(timer, now) : 0;

  useEffect(() => {
    const handler = (event) => {
      if (shouldIgnoreShortcut(event)) return;
      const store = useGameStore.getState();
      if (!store.currentQuestion || store.currentStage !== 'arena') return;
      const q = store.currentQuestion;

      if (event.key === ' ') {
        event.preventDefault();
        const result = store.toggleQuestionTimer();
        if (!result.ok && result.reason) setFeedback(result.reason);
        return;
      }
      if (event.key === 'r' || event.key === 'R') {
        event.preventDefault();
        store.revealAnswerOnline().then((result) => {
          if (result.ok) soundEngine.power();
          else setFeedback(result.reason ?? 'ما نقدر نظهر الإجابة.');
        });
        return;
      }
      if (event.key === '1' || event.key === '2') {
        if (!q.revealed) {
          setFeedback('أظهروا الإجابة أولًا، بعدها سجّلوا منو جاوب صح.');
          return;
        }
        const team = store.teams[Number(event.key) - 1];
        if (!team) return;
        store.resolveTeamWinOnline(team.id).then((result) => {
          if (result.ok) {
            soundEngine.score();
            setFeedback('');
          } else {
            setFeedback(result.reason ?? 'ما نقدر نسجل هالنتيجة.');
          }
        });
        return;
      }
      if (event.key === '0') {
        if (!q.revealed) {
          setFeedback('أظهروا الإجابة أولًا، بعدها سجّلوا النتيجة.');
          return;
        }
        store.resolveNobodyOnline().then((result) => {
          if (result.ok) soundEngine.buzzer();
          else setFeedback(result.reason ?? 'ما نقدر نسجل هالنتيجة.');
        });
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        store.abandonQuestionOnline().then((result) => {
          if (!result.ok) setFeedback(result.reason ?? 'ما نقدر نترك السؤال.');
        });
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  if (!question || !payload) return null;

  const category =
    CATEGORY_BY_ID[question.categoryId] ??
    useGameStore.getState().categories.items.find((item) => item.id === question.categoryId) ?? {
      id: question.categoryId,
      name: question.categoryName ?? question.categoryId,
      icon: 'Sparkles',
    };
  const activeTeam = teams.find((team) => team.id === question.activeTeamId);
  const activeColor = activeTeam ? colorForTeam(activeTeam) : null;
  const activeAvatar = activeTeam ? avatarForTeam(activeTeam) : null;
  const noiseRemaining = Math.max(0, (question.noiseUntil ?? 0) - now);
  const noiseActive = noiseRemaining > 0;
  const stoleTeam = question.stolenByTeamId
    ? teams.find((team) => team.id === question.stolenByTeamId)
    : null;
  const canToggle = !question.revealed;

  const handleActivate = async (powerId, teamId) => {
    const result = await useGameStore.getState().activatePowerOnline(powerId, teamId);
    if (result.ok) {
      soundEngine.power();
      const power = POWER_BY_ID[powerId];
      if (result.stoleQuestion) {
        const stealer = teams.find((team) => team.id === teamId)?.name;
        setFeedback(`«${power.name}»: ${stealer} صار صاحب السؤال، وصاحب الدور الأصلي صار مدافعًا.`);
      } else if (result.backup) {
        setFeedback(`تم تفعيل «${power.name}» وتبدّل السؤال: ${result.backup.question}`);
      } else {
        setFeedback(`تم تفعيل «${power.name}» لـ${teams.find((team) => team.id === teamId)?.name}.`);
      }
    } else {
      setFeedback(result.reason ?? 'ما صار التفعيل.');
    }
  };

  const handleResolve = async (teamId) => {
    const result = await useGameStore.getState().resolveTeamWinOnline(teamId);
    if (result.ok) {
      if (result.outcome === OUTCOMES.NOBODY) soundEngine.buzzer();
      else soundEngine.score();
      setFeedback('');
    } else {
      setFeedback(result.reason ?? 'ما صار التسجيل.');
    }
  };

  const handleNobody = async () => {
    const result = await useGameStore.getState().resolveNobodyOnline();
    if (result.ok) soundEngine.buzzer();
    else setFeedback(result.reason ?? 'ما صار التسجيل.');
  };

  const handleWrongGuess = () => {
    const result = useGameStore.getState().registerWrongGuess();
    if (result.ok) {
      soundEngine.buzzer();
      setFeedback('محاولة خاطئة مسجلة. الساعة ما توقفت.');
    } else {
      setFeedback(result.reason ?? 'ما نقدر نسجل المحاولة.');
    }
  };

  const handleAbandon = async () => {
    const result = await useGameStore.getState().abandonQuestionOnline();
    if (result.ok) soundEngine.tick();
    else setFeedback(result.reason ?? 'ما نقدر نترك السؤال.');
  };

  const art = categoryArt(question.categoryId);

  return (
    <div className="stage-bg-photo question-stage relative flex min-h-[100svh] flex-col">
      <StageBackdrop image={HERO_ART.crowd.src} position="center 40%" variant="stage" />
      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
      <HeaderScoreboard compact />

      <main className="mx-auto flex min-h-0 w-full max-w-[1900px] flex-1 flex-col gap-2 overflow-hidden px-3 pb-2 pt-2 xl:px-6">
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 xl:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_400px]">
          <section
            className={`panel relative flex min-h-0 flex-col overflow-hidden rounded-2xl border ${
              stoleTeam ? 'border-emerald-500/50' : 'border-stone-200'
            }`}
            aria-label="ساحة السؤال"
          >
            {stoleTeam && (
              <div className="flex items-center justify-center gap-2 border-b border-emerald-500/40 bg-white px-3 py-1.5 text-xs font-black text-emerald-700">
                <Icon name="Swords" size={13} />
                {stoleTeam.name} سرق السؤال — الفريق الثاني يجاوب بدال صاحب الدور
              </div>
            )}

            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-200 px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                <span className="relative h-10 w-10 shrink-0 overflow-hidden rounded-xl border border-orange-300/25 bg-orange-400/10">
                  <img
                    src={art.src}
                    alt=""
                    aria-hidden="true"
                    className="h-full w-full object-cover opacity-70"
                    style={{ objectPosition: art.position }}
                    decoding="async"
                  />
                  <span className="absolute inset-0 bg-white" />
                  <span className="absolute inset-0 grid place-items-center text-brand-700">
                    <Icon name={category?.icon ?? 'Sparkles'} size={18} />
                  </span>
                </span>
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-stone-600">{category?.name}</p>
                  <p className="text-xs font-black text-ink-900">
                    قيمة الخانة <span className="text-brand-700">{question.points}</span> نقطة
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                <span className="flex items-center gap-1 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.07] px-2 py-1 text-xs font-bold text-emerald-700">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  وقت مفتوح
                </span>
                {server.matchCode && (
                  <span
                    className={`flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-bold ${
                      server.pending
                        ? 'border-orange-400/30 bg-orange-400/10 text-brand-700'
                        : server.online
                          ? 'border-stone-300 bg-stone-100 text-stone-600'
                          : 'border-amber-400/30 bg-amber-400/10 text-amber-800'
                    }`}
                    title={`نسخة المباراة على السيرفر: ${server.version}`}
                  >
                    <Icon name={server.pending ? 'RotateCcw' : 'Radar'} size={10} className={server.pending ? 'animate-spin' : ''} />
                    {server.pending ? 'يُحفظ' : server.online ? 'متزامن' : 'نسخة محلية'}
                  </span>
                )}
                {noiseActive && (
                  <span className="rounded-lg border border-fuchsia-400/30 bg-fuchsia-400/10 px-2 py-1 text-xs font-bold text-violet-700">
                    تشويش <span className="ltr">{Math.ceil(noiseRemaining / 1000)}</span>ث
                  </span>
                )}
                {activeTeam && (
                  <span
                    className="flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs font-bold text-ink-900"
                    style={{ borderColor: `${activeColor.hex}44`, backgroundColor: `${activeColor.hex}12` }}
                  >
                    <span aria-hidden="true"><TeamAvatar avatar={activeAvatar} /></span>
                    دور {activeTeam.name}
                  </span>
                )}
              </div>
            </header>

            <div
              className="relative min-h-0 flex-1 overflow-y-auto px-3 py-3 xl:px-5 xl:py-4"
              style={{
                backgroundImage: 'linear-gradient(180deg, #fffdf9, #fff7ee)',
                backgroundSize: 'cover',
                backgroundPosition: art.position,
              }}
            >
              <div className={noiseActive ? 'noise-blur select-none' : ''} aria-hidden={noiseActive || undefined}>
                <p className="tv-question mx-auto max-w-5xl text-center font-black text-ink-900">
                  {payload.question}
                </p>
                <div className="mt-3 xl:mt-4">
                  <QuestionRenderer payload={payload} revealed={question.revealed} />
                </div>
              </div>

              {noiseActive && (
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-white">
                  <div className="rounded-2xl border border-fuchsia-400/40 bg-white px-4 py-3 text-center shadow-panel">
                    <Icon name="CloudFog" size={24} className="mx-auto text-violet-700" />
                    <p className="mt-1 text-xs font-black text-violet-700">تشويش شغّال</p>
                    <p className="ltr mt-1 text-2xl font-black text-ink-900">{formatClock(noiseRemaining)}</p>
                    <p className="mt-0.5 text-xs text-stone-600">الوقت ما يوقف.</p>
                  </div>
                </div>
              )}
            </div>

            <div className="shrink-0 border-t border-stone-200 px-3 py-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  disabled={!canToggle}
                  onClick={() => {
                    const result = useGameStore.getState().toggleQuestionTimer();
                    if (!result.ok) setFeedback(result.reason ?? 'المؤقت ما يتحرك.');
                  }}
                  className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[13px] font-black transition ${
                    canToggle
                      ? 'border-orange-400/40 bg-orange-400/10 text-brand-700 hover:bg-orange-400/20'
                      : 'cursor-not-allowed border-stone-300 bg-stone-100 text-stone-600'
                  }`}
                >
                  <Icon name={timer.running ? 'Pause' : 'Play'} size={14} />
                  {timer.running ? 'إيقاف مؤقت' : 'تشغيل المؤقت'}
                  <kbd className="ltr rounded border border-stone-200 bg-stone-100/70 px-1 text-xs">Space</kbd>
                </button>

                <button
                  type="button"
                  disabled={question.revealed}
                  onClick={() => {
                    useGameStore.getState().revealAnswerOnline().then((result) => {
                      if (result.ok) soundEngine.power();
                      else setFeedback(result.reason ?? 'ما نقدر نظهر الإجابة.');
                    });
                  }}
                  className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[13px] font-black transition ${
                    !question.revealed
                      ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-700 hover:bg-emerald-400/20'
                      : 'cursor-not-allowed border-stone-300 bg-stone-100 text-stone-600'
                  }`}
                >
                  <Icon name="Eye" size={14} />
                  إظهار الإجابة
                  <kbd className="ltr rounded border border-stone-200 bg-stone-100/70 px-1 text-xs">R</kbd>
                </button>

                {!abandonConfirm ? (
                  <button
                    type="button"
                    onClick={() => setAbandonConfirm(true)}
                    className="ms-auto flex items-center gap-1.5 rounded-xl border border-stone-300 bg-stone-100 px-2.5 py-2 text-xs font-bold text-stone-600 transition hover:border-rose-400/40 hover:text-red-700"
                  >
                    <Icon name="LogOut" size={13} />
                    انسحاب
                    <kbd className="ltr rounded border border-stone-200 bg-stone-100/70 px-1 text-xs">Esc</kbd>
                  </button>
                ) : (
                  <div className="ms-auto flex items-center gap-1.5 rounded-xl border border-rose-400/40 bg-white px-2 py-1">
                    <span className="text-xs font-bold text-red-700">تترك بدون تسجيل؟</span>
                    <button
                      type="button"
                      onClick={handleAbandon}
                      className="rounded-lg bg-rose-500 px-2 py-1 text-xs font-black text-ink-900"
                    >
                      نعم
                    </button>
                    <button
                      type="button"
                      onClick={() => setAbandonConfirm(false)}
                      className="rounded-lg border border-stone-200 px-2 py-1 text-xs font-bold text-stone-600"
                    >
                      لا
                    </button>
                  </div>
                )}
              </div>

              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-1 text-xs text-stone-600">
                <span>
                  {question.revealed
                    ? 'الإجابة ظاهرة — اختاروا أي فريق جاوب صح أو «ولا أحد».'
                    : timer.running
                      ? 'الساعة تعدّ للأمام من لحظة فتح السؤال. المسافة توقف/تشغّل.'
                      : 'الساعة متوقفة مؤقتًا — المسافة تكمّل من نفس اللحظة.'}
                </span>
                <span className="flex items-center gap-2">
                  <span>المحاولات: <span className="ltr">{question.wrongGuesses}</span></span>
                  <span>القوى المفعّلة: <span className="ltr">{question.activePowers.length}</span></span>
                </span>
              </div>

              {feedback && (
                <p className="mt-1.5 rounded-lg border border-orange-400/20 bg-orange-400/5 px-2.5 py-1.5 text-xs font-bold text-brand-700" role="status">
                  {feedback}
                </p>
              )}

              {!question.revealed && question.activePowers.includes('two_answers') && (
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-sky-400/25 bg-sky-400/5 px-2.5 py-1.5">
                  <p className="text-xs font-bold text-blue-700">
                    جاوب جوابين — المحاولات المتبقية:{' '}
                    <span className="ltr">{Math.max(0, 2 - question.wrongGuesses)}</span>
                  </p>
                  <button
                    type="button"
                    disabled={question.wrongGuesses >= 2}
                    onClick={handleWrongGuess}
                    className={`rounded-lg border px-2.5 py-1 text-xs font-bold transition ${
                      question.wrongGuesses < 2
                        ? 'border-sky-400/40 bg-sky-400/10 text-blue-700 hover:bg-sky-400/20'
                        : 'cursor-not-allowed border-stone-300 text-stone-600'
                    }`}
                  >
                    محاولة خاطئة
                  </button>
                </div>
              )}

              {question.revealed && (
                <AnswerPanel
                  payload={payload}
                  question={question}
                  teams={teams}
                  onResolve={handleResolve}
                  onNobody={handleNobody}
                />
              )}
            </div>
          </section>

          <aside className="flex min-h-0 flex-col gap-2">
            <section className="panel rounded-2xl p-3" aria-label="المؤقت">
              <div className="flex items-center gap-3">
                <RadialTimer
                  elapsedMs={elapsedMs}
                  running={timer.running}
                />
                <div className="min-w-0">
                  <p className="text-xs font-black tracking-widest text-stone-600">المؤقت</p>
                  <p className="mt-0.5 text-xs font-black text-ink-900">ساعة مفتوحة</p>
                  <p className="mt-1 text-xs leading-4 text-stone-600">
                    {timer.running
                      ? 'الوقت يعدّ للأمام من لحظة فتح السؤال، بلا سقف ولا انتقال تلقائي.'
                      : 'موقّف مؤقتًا. المسافة تكمّل من نفس المكان.'}
                  </p>
                  <p className="mt-1.5 text-xs text-stone-600">
                    المنقضي <span className="ltr">{formatClock(elapsedMs)}</span>
                  </p>
                </div>
              </div>
              {question.activePowers.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1" aria-label="القوى المفعّلة">
                  {question.activePowers.map((powerId) => {
                    const power = POWER_BY_ID[powerId];
                    if (!power) return null;
                    return (
                      <span
                        key={powerId}
                        className="rounded-md border border-amber-400/25 bg-amber-400/10 px-1.5 py-0.5 text-xs font-bold text-amber-800"
                      >
                        {power.name}
                      </span>
                    );
                  })}
                </div>
              )}
              {!question.revealed && (
                <div className="mt-2 rounded-xl border border-emerald-400/20 bg-emerald-400/5 px-2 py-1.5 text-xs leading-4 text-emerald-700">
                  الساعة تبدأ لحظة فتح السؤال. الإظهار يوقفها، وبعدها تختار أي فريق جاوب.
                </div>
              )}
            </section>

            <PowerRail
              teams={teams}
              question={question}
              timer={timer}
              now={now}
              onActivate={handleActivate}
            />

            <section className="panel hidden rounded-2xl px-3 py-2 2xl:block" aria-label="اختصارات">
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-600">
                {ARENA_SHORTCUTS.map((shortcut) => (
                  <Shortcut key={shortcut.key} keys={shortcut.label}>
                    {shortcut.action}
                  </Shortcut>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </main>
      </div>
    </div>
  );
}
