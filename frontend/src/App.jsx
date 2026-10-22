import { useEffect, useRef, useState } from 'react';
import { MotionConfig } from 'framer-motion';
import {
  CategoryZoomOverlay,
  CinematicStage,
  TurnCueOverlay,
} from './components/StageTransition.jsx';
import { isActiveMatchStage } from './game/state.js';
import { useGameStore } from './store/gameStore.js';
import { api } from './api/server.js';
import soundEngine from './utils/soundEngine.js';
import ArenaView from './views/ArenaView.jsx';
import BoardView from './views/BoardView.jsx';
import DraftView from './views/DraftView.jsx';
import LobbyView from './views/LobbyView.jsx';
import PodiumView from './views/PodiumView.jsx';
import Icon from './components/Icon.jsx';

function RecoveryBanner() {
  const notice = useGameStore((state) => state.recoveryNotice);
  const clear = useGameStore((state) => state.clearRecoveryNotice);
  if (!notice) return null;
  return (
    <div
      className="fixed bottom-3 left-1/2 z-50 flex w-[calc(100%-1.5rem)] max-w-xl -translate-x-1/2 items-start gap-2 rounded-xl border border-amber-400/35 bg-amber-950/95 px-3 py-2 text-amber-800 shadow-panel backdrop-blur"
      role="status"
    >
      <Icon name="CircleHelp" size={16} className="mt-0.5 shrink-0 text-amber-800" />
      <p className="flex-1 text-xs leading-5">{notice}</p>
      <button
        type="button"
        onClick={clear}
        aria-label="إغلاق التنبيه"
        className="rounded-md border border-stone-200 p-1 text-stone-600 transition hover:bg-white/10"
      >
        <Icon name="X" size={12} />
      </button>
    </div>
  );
}

export default function App() {
  const stage = useGameStore((state) => state.currentStage);
  const muted = useGameStore((state) => state.settings.muted);
  const matchCode = useGameStore((state) => state.server.matchCode);
  const syncServerMatch = useGameStore((state) => state.syncServerMatch);
  const [resumePending, setResumePending] = useState(() =>
    isActiveMatchStage(useGameStore.getState().currentStage),
  );

  // توكن المضيف يغذّي عميل API من المخزن (بما فيه نسخة الاسترداد بعد التحديث).
  useEffect(() => {
    const syncToken = () => {
      api.setHostToken(useGameStore.getState().server?.hostToken ?? null);
    };
    syncToken();
    return useGameStore.subscribe(syncToken);
  }, []);

  // عند فتح التطبيق: الخادم يصحّح المباراة المحفوظة، والكاش المحلي يبقى احتياطًا.
  useEffect(() => {
    if (matchCode) void syncServerMatch();
  }, [matchCode, syncServerMatch]);

  useEffect(() => {
    soundEngine.setMuted(muted);
  }, [muted]);

  useEffect(() => {
    const unlock = () => {
      soundEngine.unlock();
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
    window.addEventListener('pointerdown', unlock, { passive: true });
    window.addEventListener('keydown', unlock);
    return () => {
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
  }, []);

  // في حال تأخرت هيدرشن التخزين، نلتقط المباراة النشطة بعد أول دورة.
  useEffect(() => {
    if (isActiveMatchStage(useGameStore.getState().currentStage)) {
      setResumePending(true);
    }
  }, []);

  const prevStage = useRef(stage);
  const activeKey = resumePending && isActiveMatchStage(stage) ? 'lobby-resume' : stage;
  useEffect(() => {
    prevStage.current = stage;
  }, [stage]);

  let view = null;
  if (resumePending && isActiveMatchStage(stage)) {
    view = (
      <LobbyView
        resumePending
        onResume={() => setResumePending(false)}
        onReset={() => setResumePending(false)}
      />
    );
  } else if (stage === 'draft') view = <DraftView />;
  else if (stage === 'board') view = <BoardView />;
  else if (stage === 'arena') view = <ArenaView />;
  else if (stage === 'podium') view = <PodiumView />;
  else {
    view = (
      <LobbyView
        onResume={() => setResumePending(false)}
        onReset={() => setResumePending(false)}
      />
    );
  }

  return (
    <MotionConfig reducedMotion="user">
        <CinematicStage
          key={activeKey}
          stageKey={activeKey === 'lobby-resume' ? 'lobby' : stage}
          prevStage={prevStage.current}
        >
          {view}
        </CinematicStage>
      <CategoryZoomOverlay />
      <TurnCueOverlay />
      <RecoveryBanner />
    </MotionConfig>
  );
}
