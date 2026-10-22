import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  BarChart3,
  Database,
  KeyRound,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Trophy,
  X,
} from 'lucide-react';
import Icon from '../components/Icon.jsx';
import {
  AdminApiError,
  fetchMatchEvents,
  fetchMatches,
  fetchQuestionBank,
  fetchSeedHistory,
} from './api.js';
import {
  eventLabel,
  eventSummary,
  formatDateTime,
  formatNumber,
  percent,
  statusLabel,
  teamLabel,
} from './format.js';

const TOKEN_KEY = 'seenjeem:admin-token';
const DIFFICULTIES = [200, 400, 600];

const STATUS_STYLES = {
  active: 'border-orange-400/30 bg-orange-400/10 text-brand-700',
  completed: 'border-lime-400/30 bg-lime-400/10 text-emerald-700',
  abandoned: 'border-rose-400/30 bg-rose-400/10 text-red-700',
};

function readStoredToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? '';
  } catch {
    return '';
  }
}

function storeToken(value) {
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // التخزين قد يكون معطلًا؛ التوكن يبقى في الذاكرة فقط.
  }
}

function statusClass(status) {
  return STATUS_STYLES[status] ?? 'border-stone-300 bg-white/5 text-stone-600';
}

function TokenGate({ value, onChange, onSubmit, error, loading }) {
  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <form
        onSubmit={onSubmit}
        className="panel w-full max-w-md rounded-2xl p-6 sm:p-8"
        aria-busy={loading}
      >
        <div className="mb-6 flex items-start gap-3">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl border border-orange-300/25 bg-orange-400/10 text-brand-700">
            <KeyRound size={22} />
          </span>
          <div>
            <p className="eyebrow">Seen Jeem · Admin</p>
            <h1 className="mt-1 text-2xl font-black text-stone-800">لوحة الإدارة</h1>
            <p className="mt-1 text-xs leading-6 text-stone-600">
              توازن بنك الأسئلة، تاريخ الزرع، وأحداث المباريات في مكان واحد.
            </p>
          </div>
        </div>

        <label htmlFor="admin-token" className="mb-2 block text-xs font-bold text-stone-600">
          توكن الإدارة
        </label>
        <input
          id="admin-token"
          name="admin-token"
          type="password"
          autoComplete="current-password"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="X-Admin-Token"
          className="ltr w-full rounded-xl border border-stone-200 bg-stone-100/70 px-3 py-3 text-sm text-stone-800 placeholder:text-stone-600 focus:border-orange-300/50 focus:outline-none"
          disabled={loading}
        />
        <p className="mt-2 text-xs leading-5 text-stone-600">
          يُحفظ في جلسة المتصفح فقط، ولا يُرسل إلا إلى مسارات الإدارة المحمية.
        </p>

        {error ? (
          <p className="mt-4 rounded-xl border border-rose-400/25 bg-rose-500/10 px-3 py-2 text-xs leading-5 text-red-700">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl border border-orange-300/30 bg-orange-400/15 px-4 py-3 text-sm font-black text-brand-700 transition hover:bg-orange-400/25 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <ShieldCheck size={16} />
          {loading ? 'جارٍ التحقق…' : 'دخول اللوحة'}
        </button>
      </form>
    </div>
  );
}

function SummaryCard({ label, value, hint, icon: CardIcon, tone = 'cyan' }) {
  const tones = {
    cyan: 'text-brand-700 border-orange-300/20 bg-orange-400/10',
    lime: 'text-emerald-700 border-lime-300/20 bg-lime-400/10',
    amber: 'text-amber-800 border-amber-300/20 bg-amber-400/10',
    violet: 'text-violet-700 border-violet-300/20 bg-violet-400/10',
  };
  return (
    <div className="panel rounded-xl p-3 sm:p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-bold text-stone-600">{label}</p>
          <p className="mt-1 text-2xl font-black tabular-nums text-stone-800">
            {formatNumber(value)}
          </p>
        </div>
        <span className={`grid h-9 w-9 place-items-center rounded-lg border ${tones[tone]}`}>
          <CardIcon size={17} />
        </span>
      </div>
      <p className="mt-2 text-xs leading-4 text-stone-600">{hint}</p>
    </div>
  );
}

function BankSection({ bank }) {
  if (!bank) return null;
  const standards = bank.standards ?? {};
  return (
    <section className="panel min-w-0 rounded-2xl p-3 sm:p-5" aria-labelledby="bank-title">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="eyebrow">Question bank</p>
          <h2 id="bank-title" className="text-lg font-black text-stone-800">
            توازن البنك حسب الفئة والصعوبة
          </h2>
          <p className="mt-1 text-xs leading-5 text-stone-600">
            المؤهل = نشط، غير مستخدم في الدورة الحالية، وغير محجوز لمباراة نشطة.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-stone-600">
          <span className="rounded-full border border-stone-200 px-2 py-1">
            الحد التشغيلي {formatNumber(standards.operational_min_per_bucket)}
          </span>
          <span className="rounded-full border border-stone-200 px-2 py-1">
            هدف المحتوى {formatNumber(standards.content_floor_per_bucket)}
          </span>
          <span className="rounded-full border border-stone-200 px-2 py-1">
            سعة 100 مباراة {formatNumber(standards.capacity_per_bucket)}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] border-separate border-spacing-y-1 text-right text-xs">
          <thead className="text-xs text-stone-600">
            <tr>
              <th className="px-3 py-2 font-bold">الفئة</th>
              {DIFFICULTIES.map((difficulty) => (
                <th key={difficulty} className="min-w-[180px] px-3 py-2 font-bold">
                  {difficulty}
                </th>
              ))}
              <th className="px-3 py-2 font-bold">إجمالي المؤهل</th>
              <th className="px-3 py-2 font-bold">مرات اللعب</th>
            </tr>
          </thead>
          <tbody>
            {(bank.categories ?? []).map((category) => (
              <tr key={category.slug} className="bg-white/[0.025]">
                <td className="rounded-r-lg border-r border-y border-stone-200 px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="grid h-8 w-8 place-items-center rounded-lg border border-stone-200 bg-stone-100/70 text-brand-700">
                      <Icon name={category.icon} size={15} />
                    </span>
                    <div>
                      <p className="font-bold text-stone-800">{category.name_ar}</p>
                      <p className="text-xs text-stone-600">{category.slug}</p>
                    </div>
                  </div>
                </td>
                {DIFFICULTIES.map((difficulty) => {
                  const bucket = category.buckets?.[String(difficulty)];
                  if (!bucket) {
                    return (
                      <td
                        key={difficulty}
                        className="border-y border-stone-200 px-3 py-2.5 text-stone-600"
                      >
                        —
                      </td>
                    );
                  }
                  const fill = percent(bucket.eligible, bucket.total);
                  return (
                    <td key={difficulty} className="border-y border-stone-200 px-3 py-2.5">
                      <div
                        title={`مؤهل ${bucket.eligible} من ${bucket.total} • مستخدم ${bucket.used_current_cycle} • محجوز ${bucket.reserved_active} • دورة ${bucket.cycle}`}
                      >
                        <div className="flex items-baseline gap-1">
                          <span className="text-lg font-black tabular-nums text-stone-800">
                            {formatNumber(bucket.eligible)}
                          </span>
                          <span className="text-xs text-stone-600">
                            / {formatNumber(bucket.total)}
                          </span>
                          <span
                            className={`mr-auto rounded-full border px-1.5 py-0.5 text-xs ${
                              bucket.meets_capacity
                                ? 'border-lime-300/25 text-emerald-700'
                                : bucket.meets_content_floor
                                  ? 'border-amber-300/25 text-amber-800'
                                  : 'border-rose-300/25 text-red-700'
                            }`}
                          >
                            {bucket.meets_capacity
                              ? 'سعة كاملة'
                              : bucket.meets_content_floor
                                ? 'هدف محتوى'
                                : 'تحت الهدف'}
                          </span>
                        </div>
                        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                          <div
                            className={`h-full rounded-full ${
                              bucket.meets_content_floor ? 'bg-orange-400/80' : 'bg-amber-400/80'
                            }`}
                            style={{ width: `${Math.max(fill, 2)}%` }}
                          />
                        </div>
                        <div className="mt-1 flex justify-between text-xs text-stone-600">
                          <span>مستخدم {formatNumber(bucket.used_current_cycle)}</span>
                          <span>محجوز {formatNumber(bucket.reserved_active)}</span>
                          <span>دورة {formatNumber(bucket.cycle)}</span>
                        </div>
                      </div>
                    </td>
                  );
                })}
                <td className="border-y border-stone-200 px-3 py-2.5 text-base font-black tabular-nums text-brand-700">
                  {formatNumber(category.eligible)}
                </td>
                <td className="rounded-l-lg border-l border-y border-stone-200 px-3 py-2.5 tabular-nums text-stone-600">
                  {formatNumber(category.total_plays)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SeedSection({ seeds }) {
  return (
    <section className="panel min-w-0 rounded-2xl p-3 sm:p-5" aria-labelledby="seed-title">
      <div className="mb-3">
        <p className="eyebrow">Seed history</p>
        <h2 id="seed-title" className="text-lg font-black text-stone-800">
          تاريخ الزرع
        </h2>
      </div>
      <div className="max-h-[22rem] overflow-auto">
        <table className="w-full min-w-[560px] text-right text-[13px]">
          <thead className="sticky top-0 bg-cream text-xs text-stone-600">
            <tr>
              <th className="px-2 py-2 font-bold">#</th>
              <th className="px-2 py-2 font-bold">النسخة / البذرة</th>
              <th className="px-2 py-2 font-bold">أُضيف</th>
              <th className="px-2 py-2 font-bold">تخطّى / خاطئ</th>
              <th className="px-2 py-2 font-bold">النشط</th>
              <th className="px-2 py-2 font-bold">التاريخ</th>
            </tr>
          </thead>
          <tbody>
            {(seeds?.runs ?? []).map((run) => (
              <tr key={run.id} className="border-t border-stone-200">
                <td className="px-2 py-2 tabular-nums text-stone-600">{run.id}</td>
                <td className="px-2 py-2">
                  <p className="font-bold text-stone-800">{run.seed_version}</p>
                  <p className="text-xs tabular-nums text-stone-600">
                    seed {run.deterministic_seed}
                  </p>
                </td>
                <td className="px-2 py-2 tabular-nums text-emerald-700">
                  {formatNumber(run.inserted)}
                </td>
                <td className="px-2 py-2 tabular-nums text-stone-600">
                  {formatNumber(run.skipped)} /{' '}
                  <span className={run.invalid > 0 ? 'text-red-700' : ''}>
                    {formatNumber(run.invalid)}
                  </span>
                </td>
                <td className="px-2 py-2 tabular-nums text-stone-800">
                  {formatNumber(run.total_active)}
                </td>
                <td className="px-2 py-2 text-xs text-stone-600">
                  {formatDateTime(run.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {seeds?.runs?.length === 0 ? (
          <p className="py-6 text-center text-xs text-stone-600">ما في عمليات زرع مسجلة.</p>
        ) : null}
      </div>
    </section>
  );
}

function MatchesSection({
  matches,
  statusFilter,
  onStatusFilter,
  selectedCode,
  onSelect,
  eventsLoading,
}) {
  const visible = useMemo(() => {
    const rows = matches?.matches ?? [];
    return statusFilter === 'all'
      ? rows
      : rows.filter((match) => match.status === statusFilter);
  }, [matches, statusFilter]);

  const counts = matches?.status_counts ?? {};
  const filters = [
    { id: 'all', label: 'الكل', count: matches?.total ?? 0 },
    { id: 'active', label: 'نشطة', count: counts.active ?? 0 },
    { id: 'completed', label: 'مكتملة', count: counts.completed ?? 0 },
    { id: 'abandoned', label: 'متروكة', count: counts.abandoned ?? 0 },
  ];

  return (
    <section className="panel min-w-0 rounded-2xl p-3 sm:p-5" aria-labelledby="matches-title">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="eyebrow">Matches & events</p>
          <h2 id="matches-title" className="text-lg font-black text-stone-800">
            المباريات وأحداثها
          </h2>
        </div>
        <div className="flex flex-wrap gap-1">
          {filters.map((filter) => (
            <button
              key={filter.id}
              type="button"
              onClick={() => onStatusFilter(filter.id)}
              className={`rounded-full border px-2.5 py-1 text-xs font-bold transition ${
                statusFilter === filter.id
                  ? 'border-orange-300/40 bg-orange-400/15 text-brand-700'
                  : 'border-stone-200 text-stone-600 hover:bg-white/5'
              }`}
            >
              {filter.label} {formatNumber(filter.count)}
            </button>
          ))}
        </div>
      </div>

      <div className="max-h-[22rem] overflow-auto">
        <table className="w-full min-w-[620px] text-right text-[13px]">
          <thead className="sticky top-0 bg-cream text-xs text-stone-600">
            <tr>
              <th className="px-2 py-2 font-bold">المواجهة</th>
              <th className="px-2 py-2 font-bold">النتيجة</th>
              <th className="px-2 py-2 font-bold">الحالة</th>
              <th className="px-2 py-2 font-bold">أحداث</th>
              <th className="px-2 py-2 font-bold">آخر تحديث</th>
              <th className="px-2 py-2 font-bold" />
            </tr>
          </thead>
          <tbody>
            {visible.map((match) => (
              <tr
                key={match.match_code}
                className={`border-t border-stone-200 ${
                  selectedCode === match.match_code ? 'bg-orange-400/[0.06]' : ''
                }`}
              >
                <td className="px-2 py-2">
                  <p className="font-bold text-stone-800">
                    {match.team1_name} × {match.team2_name}
                  </p>
                  <p className="ltr text-left text-xs text-stone-600">{match.match_code}</p>
                </td>
                <td className="px-2 py-2 tabular-nums text-stone-800">
                  {formatNumber(match.score_team1)} — {formatNumber(match.score_team2)}
                </td>
                <td className="px-2 py-2">
                  <span className={`rounded-full border px-2 py-1 text-xs ${statusClass(match.status)}`}>
                    {statusLabel(match.status)}
                  </span>
                </td>
                <td className="px-2 py-2 tabular-nums text-stone-600">
                  {formatNumber(match.event_count)}
                </td>
                <td className="px-2 py-2 text-xs text-stone-600">
                  {formatDateTime(match.updated_at)}
                </td>
                <td className="px-2 py-2">
                  <button
                    type="button"
                    onClick={() => onSelect(match.match_code)}
                    disabled={eventsLoading && selectedCode === match.match_code}
                    className="rounded-lg border border-stone-200 px-2 py-1 text-xs font-bold text-brand-700 transition hover:bg-orange-400/10 disabled:opacity-50"
                  >
                    {selectedCode === match.match_code ? 'إخفاء' : 'الأحداث'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visible.length === 0 ? (
          <p className="py-6 text-center text-xs text-stone-600">ما في مباريات بهذه الحالة.</p>
        ) : null}
      </div>
    </section>
  );
}

function EventsPanel({ data, loading, error, onClose }) {
  return (
    <section className="panel min-w-0 rounded-2xl p-3 sm:p-5" aria-labelledby="events-title">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Event ledger</p>
          <h2 id="events-title" className="text-lg font-black text-stone-800">
            أحداث المباراة
          </h2>
          {data?.match ? (
            <p className="mt-1 text-xs text-stone-600">
              {data.match.team1_name} × {data.match.team2_name} •{' '}
              <span className="ltr inline-block">{data.match.match_code}</span> •{' '}
              {statusLabel(data.match.status)}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="إغلاق الأحداث"
          className="rounded-lg border border-stone-200 p-2 text-stone-600 transition hover:bg-white/10"
        >
          <X size={15} />
        </button>
      </div>

      {loading ? <p className="py-6 text-center text-xs text-stone-600">جارٍ تحميل الأحداث…</p> : null}
      {error ? (
        <p className="rounded-xl border border-rose-400/25 bg-rose-500/10 px-3 py-2 text-xs text-red-700">
          {error}
        </p>
      ) : null}

      {!loading && !error ? (
        <ol className="max-h-[30rem] space-y-2 overflow-auto border-r border-stone-200 pr-4">
          {(data?.events ?? []).map((event) => (
            <li key={event.id} className="relative rounded-lg border border-stone-200 bg-white/[0.02] p-2.5">
              <span className="absolute -right-[1.32rem] top-4 h-2 w-2 rounded-full bg-orange-300/80 ring-4 ring-[#0a1020]" />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-bold text-stone-800">{eventLabel(event.event_type)}</p>
                <p className="text-xs text-stone-600">{formatDateTime(event.created_at)}</p>
              </div>
              <p className="mt-1 text-xs leading-5 text-stone-600">{eventSummary(event)}</p>
              <details className="mt-1">
                <summary className="cursor-pointer text-xs text-stone-600 hover:text-stone-600">
                  التفاصيل
                </summary>
                <pre className="ltr mt-1 max-h-40 overflow-auto rounded-lg bg-stone-100/70 p-2 text-left text-xs leading-4 text-stone-600">
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              </details>
            </li>
          ))}
          {(data?.events ?? []).length === 0 ? (
            <li className="py-4 text-center text-xs text-stone-600">ما في أحداث لهذه المباراة.</li>
          ) : null}
        </ol>
      ) : null}
    </section>
  );
}

export default function AdminApp() {
  const [token, setToken] = useState(readStoredToken);
  const [tokenInput, setTokenInput] = useState('');
  const [bank, setBank] = useState(null);
  const [seeds, setSeeds] = useState(null);
  const [matches, setMatches] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedCode, setSelectedCode] = useState(null);
  const [eventsData, setEventsData] = useState(null);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState('');
  const bootstrapped = useRef(false);

  const loadAll = useCallback(async (candidate) => {
    setLoading(true);
    setError('');
    try {
      const [bankData, seedData, matchData] = await Promise.all([
        fetchQuestionBank(candidate),
        fetchSeedHistory(candidate),
        fetchMatches(candidate),
      ]);
      setBank(bankData);
      setSeeds(seedData);
      setMatches(matchData);
      storeToken(candidate);
      return true;
    } catch (caught) {
      const message =
        caught instanceof AdminApiError
          ? caught.message
          : 'ما وصلنا لخادم الإدارة. تأكد أن الخادم شغّال وجرّب مرة ثانية.';
      if (caught instanceof AdminApiError && caught.status === 403) {
        storeToken('');
        setToken('');
        setBank(null);
        setSeeds(null);
        setMatches(null);
      }
      setError(message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    if (token) void loadAll(token);
  }, [loadAll, token]);

  async function submit(event) {
    event.preventDefault();
    const candidate = tokenInput.trim();
    if (!candidate) return;
    const ok = await loadAll(candidate);
    if (ok) {
      setToken(candidate);
      setTokenInput('');
    }
  }

  async function openEvents(code) {
    if (selectedCode === code) {
      setSelectedCode(null);
      setEventsData(null);
      setEventsError('');
      return;
    }
    setSelectedCode(code);
    setEventsData(null);
    setEventsError('');
    setEventsLoading(true);
    try {
      setEventsData(await fetchMatchEvents(token, code));
    } catch (caught) {
      setEventsError(
        caught instanceof AdminApiError
          ? caught.message
          : 'تعذّر تحميل أحداث المباراة.',
      );
    } finally {
      setEventsLoading(false);
    }
  }

  function logout() {
    storeToken('');
    setToken('');
    setTokenInput('');
    setBank(null);
    setSeeds(null);
    setMatches(null);
    setSelectedCode(null);
    setEventsData(null);
    setError('');
  }

  if (!token) {
    return (
      <div className="stage-bg grid-noise min-h-screen">
        <TokenGate
          value={tokenInput}
          onChange={setTokenInput}
          onSubmit={submit}
          error={error}
          loading={loading}
        />
      </div>
    );
  }

  const totals = bank?.totals ?? {};
  const statusCounts = matches?.status_counts ?? {};
  const lastSeed = seeds?.runs?.[0];

  return (
    <div className="stage-bg grid-noise min-h-screen px-3 py-5 sm:px-6">
      <div className="mx-auto max-w-7xl space-y-4">
        <header className="panel flex flex-wrap items-center justify-between gap-3 rounded-2xl p-4 sm:p-5">
          <div className="flex items-center gap-3">
            <span className="grid h-12 w-12 place-items-center rounded-xl border border-orange-300/25 bg-orange-400/10 text-brand-700">
              <Database size={22} />
            </span>
            <div>
              <p className="eyebrow">Seen Jeem · Operator console</p>
              <h1 className="text-xl font-black text-stone-800 sm:text-2xl">لوحة الإدارة</h1>
              <p className="mt-0.5 text-xs text-stone-600">
                نظرة مباشرة على البنك والزرع والمباريات. البيانات للقراءة فقط.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void loadAll(token)}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl border border-stone-200 px-3 py-2 text-xs font-bold text-stone-600 transition hover:bg-white/5 disabled:opacity-50"
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              تحديث
            </button>
            <button
              type="button"
              onClick={logout}
              className="flex items-center gap-2 rounded-xl border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs font-bold text-red-700 transition hover:bg-rose-500/20"
            >
              <LogOut size={13} />
              خروج
            </button>
          </div>
        </header>

        {error ? (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-rose-400/25 bg-rose-500/10 px-4 py-3 text-xs text-red-700"
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => void loadAll(token)}
              className="rounded-lg border border-rose-300/30 px-2 py-1 text-xs font-bold hover:bg-rose-500/20"
            >
              إعادة المحاولة
            </button>
          </div>
        ) : null}

        {loading && !bank ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="panel h-28 animate-pulse rounded-xl bg-white/[0.03]" />
            ))}
          </div>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <SummaryCard
                label="أسئلة نشطة"
                value={totals.questions}
                hint={`${formatNumber(totals.playable)} قابلة للعب • ${formatNumber(totals.buckets)} دلو`}
                icon={Database}
              />
              <SummaryCard
                label="مؤهلة الآن"
                value={totals.eligible}
                hint={`مستخدم ${formatNumber(totals.used_current_cycle)} • محجوز ${formatNumber(totals.reserved_active)}`}
                icon={Activity}
              />
              <SummaryCard
                label="مجموعات واقعية"
                value={totals.fact_groups}
                hint={`${formatNumber(totals.played_questions)} سؤال لُعب`}
                icon={ShieldCheck}
                tone="lime"
              />
              <SummaryCard
                label="مرات اللعب"
                value={totals.total_plays}
                hint={`أقصى دورة ${formatNumber(totals.max_cycle)} • ${formatNumber(totals.total_cycles)} مجموع الدورات`}
                icon={BarChart3}
                tone="violet"
              />
              <SummaryCard
                label="المباريات"
                value={matches?.total}
                hint={`${formatNumber(statusCounts.active)} نشطة • ${formatNumber(statusCounts.completed)} مكتملة`}
                icon={Trophy}
                tone="amber"
              />
              <SummaryCard
                label="عمليات الزرع"
                value={seeds?.total}
                hint={lastSeed ? `آخر نسخة ${lastSeed.seed_version}` : 'ما في زرع مسجل'}
                icon={RefreshCw}
                tone="cyan"
              />
            </div>

            <BankSection bank={bank} />

            <div className="grid gap-4 xl:grid-cols-2">
              <SeedSection seeds={seeds} />
              <MatchesSection
                matches={matches}
                statusFilter={statusFilter}
                onStatusFilter={setStatusFilter}
                selectedCode={selectedCode}
                onSelect={openEvents}
                eventsLoading={eventsLoading}
              />
            </div>

            {selectedCode ? (
              <EventsPanel
                data={eventsData}
                loading={eventsLoading}
                error={eventsError}
                onClose={() => {
                  setSelectedCode(null);
                  setEventsData(null);
                  setEventsError('');
                }}
              />
            ) : null}

            <footer className="flex flex-wrap items-center justify-between gap-2 py-2 text-xs text-stone-600">
              <span>
                آخر تحديث {formatDateTime(bank?.generated_at)} •{' '}
                {formatNumber(totals.questions)} سؤال نشط
              </span>
              <span>
                {teamLabel('team1')} / {teamLabel('team2')} هي مفاتيح الخادم الداخلية.
              </span>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
