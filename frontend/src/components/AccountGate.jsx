import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { accounts } from '../api/accounts.js';
import { useGameStore } from '../store/gameStore.js';
import BrandMark from './BrandMark.jsx';
import CategoryVisual from './CategoryVisual.jsx';
import Icon from './Icon.jsx';

const OWNER_KEY = 'seenjeem:account-owner:v1';
const buttonClass = 'brand-button brand-button--subtle';
const inputClass = 'brand-input';

function bindLocalGame(userId) {
  // Only this browser's recovery copy is reset; the server retains accounts/history.
  let previous = null;
  try { previous = localStorage.getItem(OWNER_KEY); } catch { /* Storage may be disabled. */ }
  if (previous !== String(userId)) {
    const store = useGameStore.getState();
    store.resetSavedMatch();
    store.clearRecoveryNotice();
  }
  try { localStorage.setItem(OWNER_KEY, String(userId)); } catch { /* Session cookie still works. */ }
}

export default function AccountGate({ children }) {
  const [account, setAccount] = useState(null);
  const [checking, setChecking] = useState(true);
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const mounted = useRef(true);
  const generation = useRef(0);
  const boundUser = useRef(null);

  const accept = useCallback((value) => {
    if (boundUser.current !== value.user.id) {
      bindLocalGame(value.user.id);
      boundUser.current = value.user.id;
    }
    setAccount(value);
    setPassword('');
    setHistory(null);
    setHistoryOpen(false);
  }, []);

  const checkSession = useCallback(async () => {
    const current = ++generation.current;
    try {
      const value = await accounts.me();
      if (mounted.current && current === generation.current) { accept(value); setError(''); }
    } catch (err) {
      if (mounted.current && current === generation.current) {
        setAccount(null);
        setHistory(null);
        setHistoryOpen(false);
        setError(err.status === 401 ? '' : 'تعذّر التحقق من الحساب. تحقق من الاتصال وأعد المحاولة.');
      }
    } finally {
      if (mounted.current && current === generation.current) setChecking(false);
    }
  }, [accept]);

  useEffect(() => {
    mounted.current = true;
    void checkSession();
    const expired = () => { generation.current += 1; setAccount(null); setError('انتهت الجلسة. سجّل دخولك مجددًا؛ سجل أسئلتك محفوظ.'); };
    const refreshCount = async () => {
      const current = generation.current;
      try {
        const value = await accounts.me();
        if (mounted.current && current === generation.current) {
          setAccount((previous) => previous?.user.id === value.user.id ? value : previous);
        }
      } catch { /* Keep the active game; the history button can retry the count. */ }
    };
    window.addEventListener('focus', checkSession);
    window.addEventListener('seenjeem:session-expired', expired);
    window.addEventListener('seenjeem:history-updated', refreshCount);
    return () => {
      mounted.current = false;
      window.removeEventListener('focus', checkSession);
      window.removeEventListener('seenjeem:session-expired', expired);
      window.removeEventListener('seenjeem:history-updated', refreshCount);
    };
  }, [checkSession]);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    generation.current += 1;
    setBusy(true);
    setError('');
    try { accept(await accounts[mode](username.trim(), password)); }
    catch (err) { setError(err.message || 'تعذّر تسجيل الدخول. حاول مجددًا.'); }
    finally { if (mounted.current) setBusy(false); }
  }

  async function logout() {
    if (busy) return;
    generation.current += 1;
    setBusy(true);
    setError('');
    try {
      await accounts.logout();
      setAccount(null);
      setHistory(null);
      setHistoryOpen(false);
      setPassword('');
    } catch (err) { setError(err.message || 'تعذّر تسجيل الخروج.'); }
    finally { if (mounted.current) setBusy(false); }
  }

  async function loadHistory(offset = 0) {
    if (historyBusy) return;
    setHistoryOpen(true);
    setHistoryBusy(true);
    setError('');
    const current = generation.current;
    try {
      const result = await accounts.history(offset);
      if (!mounted.current || current !== generation.current) return;
      setHistory((previous) => ({ ...result, items: offset ? [...(previous?.items ?? []), ...result.items] : result.items }));
      setAccount((previous) => previous ? { ...previous, questions_seen: result.total } : previous);
    } catch (err) {
      if (!mounted.current || current !== generation.current) return;
      if (err.status === 401) { setAccount(null); setHistory(null); setHistoryOpen(false); }
      setError(err.message || 'تعذّر تحميل سجل الأسئلة.');
    } finally { if (mounted.current) setHistoryBusy(false); }
  }

  if (checking) return <main dir="rtl" className="grid min-h-screen place-items-center bg-white p-6 text-ink-900" role="status">جاري التحقق من حسابك…</main>;

  if (!account) return (
    <main dir="rtl" className="auth-page">
      <div className="auth-page__top"><BrandMark /><span className="auth-page__note"><Icon name="Shield" size={16} /> كل سؤال جديد… لمّة أحلى</span></div>
      <div className="auth-layout">
        <aside className="auth-story">
          <span className="brand-pill">اللّعبة اللي تجمعكم</span>
          <h2>جهّزوا اللّمّة، <br />وخلّوا <span>التحدّي علينا.</span></h2>
          <p>فريقين، ست فئات، وحماس ما يوقف.<br />منو فيكم يعرف أكثر؟</p>
          <div className="auth-deck" aria-hidden="true">
            <div className="auth-deck__card"><CategoryVisual id="football" /><strong>كورة وبس!</strong><span>٢٠٠ · ٤٠٠ · ٦٠٠</span></div>
            <div className="auth-deck__card"><CategoryVisual id="worldcup" /><strong>قدّها وقدود</strong><span>خلّ الفوز لفريقك</span></div>
            <div className="auth-deck__card"><CategoryVisual id="riddles" /><strong>شغّل مخّك</strong><span>كل سؤال له سالفة</span></div>
          </div>
          <div className="auth-story__facts"><span><strong>٦</strong> فئات تختارونها</span><span><strong>٣٦</strong> فرصة للتحدّي</span><span><strong>٢</strong> فريق يتنافسون</span></div>
        </aside>
      <section className="auth-form panel" aria-labelledby="account-title">
        <span className="auth-form__icon"><Icon name="UserCheck" size={25} /></span>
        <h1 id="account-title" className="mt-4 text-3xl font-black">{mode === 'register' ? 'أول لمّة؟ حيّاك!' : 'يا هلا بعودتك!'}</h1>
        <p className="mt-3 text-sm leading-7 text-stone-600">كل سؤال تفتحه يُحفظ في حسابك، وما يرجع لك في المباريات القادمة. سجلك معك حتى لو غيّرت الجهاز.</p>
        <div className="auth-tabs" aria-label="خيارات الحساب">
          {[['login', 'تسجيل الدخول'], ['register', 'إنشاء حساب']].map(([value, label]) => (
            <button key={value} type="button" aria-pressed={mode === value} disabled={busy}
              className={mode === value ? 'is-active' : ''}
              onClick={() => { setMode(value); setError(''); setPassword(''); }}>{label}</button>
          ))}
        </div>
        <form className="mt-6 space-y-5" onSubmit={submit} aria-busy={busy}>
          <label className="block text-sm font-bold" htmlFor="account-username">اسم المستخدم
            <input id="account-username" name="username" autoComplete="username" required maxLength={32}
              value={username} onChange={(event) => setUsername(event.target.value)} className={inputClass} disabled={busy} />
          </label>
          <label className="block text-sm font-bold" htmlFor="account-password">كلمة المرور
            <input id="account-password" name="password" type="password" dir="ltr" required
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'} minLength={mode === 'register' ? 10 : 1} maxLength={128}
              value={password} onChange={(event) => setPassword(event.target.value)} className={inputClass} disabled={busy}
              aria-describedby={mode === 'register' ? 'password-hint' : undefined} />
          </label>
          {mode === 'register' && <p id="password-hint" className="text-sm text-stone-600">استخدم ١٠ أحرف على الأقل. احفظ كلمة المرور؛ استعادة الحساب غير متاحة حاليًا.</p>}
          {error && <p role="alert" className="rounded-xl border border-rose-300/40 bg-white p-3 text-sm leading-6 text-red-700">{error}</p>}
          <button type="submit" disabled={busy} className="brand-button brand-button--primary w-full">
            {busy ? 'لحظة…' : mode === 'register' ? 'إنشاء حساب والبدء' : 'دخول إلى اللعبة'}
          </button>
        </form>
        <p className="auth-form__promise"><Icon name="Shield" size={16} /> أسئلتك محفوظة. كل مباراة تجربة جديدة.</p>
      </section>
      </div>
      <footer className="auth-footer">مصنوعة للّمة، ولحظات «إي والله أعرفها!»</footer>
    </main>
  );

  return (
    <>
      <header dir="rtl" className="account-nav">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3">
          <BrandMark compact />
          <div className="account-nav__identity"><p className="font-bold">أهلًا، {account.user.username}</p><p className="mt-1 text-xs text-stone-600"><span dir="ltr">{account.questions_seen}</span> سؤال محفوظ في حسابك · يُستبعد من المباريات الجديدة</p></div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={buttonClass} disabled={historyBusy} onClick={() => void loadHistory()}>سجل أسئلتي</button>
            <button type="button" className={buttonClass} disabled={busy} onClick={logout}>تسجيل الخروج</button>
          </div>
        </div>
        {error && <p role="alert" className="mx-auto mt-3 max-w-[1600px] text-sm text-red-700">{error}</p>}
        {historyOpen && (
          <section aria-label="سجل أسئلتي" className="mx-auto mt-4 max-w-4xl rounded-2xl border border-stone-200 bg-stone-100/70 p-4">
            <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-black">الأسئلة اللي شفتها</h2><button type="button" className={buttonClass} onClick={() => setHistoryOpen(false)}>إغلاق السجل</button></div>
            {history && history.total === 0 && <p className="mt-4 text-sm text-stone-600">سجلك فاضي. افتح أول سؤال في مباراة وراح ينحفظ تلقائيًا.</p>}
            <ol className="mt-4 max-h-80 space-y-3 overflow-auto" tabIndex={0} aria-label="الأسئلة السابقة">
              {(history?.items ?? []).map((item) => <li key={item.question_id} className="rounded-xl border border-stone-200 p-3"><p className="text-sm leading-6">{item.question_text}</p><p className="mt-2 text-xs text-stone-600">{item.category_name} · {item.difficulty} نقطة · {new Date(item.played_at).toLocaleDateString('ar')}</p></li>)}
            </ol>
            {historyBusy && <p role="status" className="mt-3 text-sm">جاري تحميل السجل…</p>}
            {history && history.items.length < history.total && <button type="button" disabled={historyBusy} className={`${buttonClass} mt-3`} onClick={() => void loadHistory(history.items.length)}>عرض المزيد</button>}
          </section>
        )}
      </header>
      <Fragment key={account.user.id}>{children}</Fragment>
    </>
  );
}
