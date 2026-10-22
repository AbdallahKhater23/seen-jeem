import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import { useGameStore } from '../store/gameStore.js';
import { colorForTeam } from '../game/constants.js';
import TeamAvatar from './TeamAvatar.jsx';
import soundEngine from '../utils/soundEngine.js';

export const STAGE_ORDER = ['lobby', 'draft', 'board', 'arena', 'podium'];

export function StageShell({ stageKey, children }) {
  const reduce = useReducedMotion();
  return <motion.div key={stageKey} initial={reduce ? false : { opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .18 }} className="relative">{children}</motion.div>;
}

export function isTurnChange(previous, next) { return Boolean(next) && previous !== next; }

/** A compact turn notification leaves the board and its controls visible. */
export function TurnCueOverlay({ durationMs = 1400 }) {
  const stage = useGameStore((state) => state.currentStage);
  const turnId = useGameStore((state) => state.currentTurnTeamId);
  const teams = useGameStore((state) => state.teams);
  const lastTurn = useRef(null);
  const [cue, setCue] = useState(null);
  const reduce = useReducedMotion();
  useEffect(() => { if (stage === 'lobby') lastTurn.current = null; }, [stage]);
  useEffect(() => {
    if (stage !== 'board' || !isTurnChange(lastTurn.current, turnId)) return undefined;
    lastTurn.current = turnId;
    const team = teams.find((item) => item.id === turnId);
    if (!team) return undefined;
    setCue(team);
    void soundEngine.turn();
    const timer = setTimeout(() => setCue(null), durationMs);
    return () => clearTimeout(timer);
  }, [stage, turnId, teams, durationMs]);
  if (stage !== 'board') return null;
  return <AnimatePresence>{cue && <motion.div role="status" aria-live="polite"
    className="turn-toast" initial={reduce ? false : { opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
    style={{ borderColor: colorForTeam(cue).hex }}><span style={{ color: colorForTeam(cue).hex }}><TeamAvatar team={cue} /></span><span>الدور عليكم، <strong>{cue.name}</strong>!</span></motion.div>}</AnimatePresence>;
}

export function CategoryZoomOverlay() { return null; }
export function StageNameFlash() { return null; }
export function CinematicStage({ stageKey, children }) { return <StageShell stageKey={stageKey}>{children}</StageShell>; }
