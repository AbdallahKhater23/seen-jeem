import { Bird, Crown, Flame, Shield, Sparkles, Zap } from 'lucide-react';
import { avatarForTeam } from '../game/constants.js';

const SYMBOLS = { falcon: Bird, wolf: Shield, lion: Crown, horse: Zap, camel: Flame, eagle: Sparkles };
export default function TeamAvatar({ team, avatar }) {
  const Symbol = SYMBOLS[(avatar ?? avatarForTeam(team)).id] ?? Bird;
  return <Symbol aria-hidden="true" width="1em" height="1em" strokeWidth={1.8} />;
}
