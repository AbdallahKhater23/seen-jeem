export const STORAGE_KEY = 'ya-hala-trivia:match:v1';

export const STAGES = Object.freeze({
  LOBBY: 'lobby',
  DRAFT: 'draft',
  BOARD: 'board',
  ARENA: 'arena',
  PODIUM: 'podium',
});

export const ACTIVE_STAGES = Object.freeze([STAGES.DRAFT, STAGES.BOARD, STAGES.ARENA]);

export const TEAM_A_ID = 'team-falcons';
export const TEAM_B_ID = 'team-wolves';
export const TEAM_IDS = Object.freeze([TEAM_A_ID, TEAM_B_ID]);

export const TEAM_COLORS = Object.freeze([
  { id: 'cyan', name: 'سماوي', ring: 'ring-cyan-400', text: 'text-cyan-300', bar: 'bg-cyan-400', hex: '#187c79' },
  { id: 'pink', name: 'وردي', ring: 'ring-pink-400', text: 'text-pink-300', bar: 'bg-pink-400', hex: '#bb4768' },
  { id: 'lime', name: 'ليموني', ring: 'ring-lime-400', text: 'text-lime-300', bar: 'bg-lime-400', hex: '#587b25' },
  { id: 'amber', name: 'ذهبي', ring: 'ring-amber-400', text: 'text-amber-300', bar: 'bg-amber-400', hex: '#9d6b15' },
  { id: 'violet', name: 'بنفسجي', ring: 'ring-violet-400', text: 'text-violet-300', bar: 'bg-violet-400', hex: '#7954a5' },
  { id: 'orange', name: 'برتقالي', ring: 'ring-orange-400', text: 'text-orange-300', bar: 'bg-orange-400', hex: '#b85424' },
]);

export const AVATARS = Object.freeze([
  { id: 'falcon', label: 'صقر', emoji: '🦅' },
  { id: 'wolf', label: 'ذيب', emoji: '🐺' },
  { id: 'lion', label: 'أسد', emoji: '🦁' },
  { id: 'horse', label: 'حصان', emoji: '🐎' },
  { id: 'camel', label: 'جمل', emoji: '🐪' },
  { id: 'eagle', label: 'عقاب', emoji: '🦅' },
]);

export const TEAM_NAME_MAX_LENGTH = 28;

export function colorForTeam(team) {
  return TEAM_COLORS.find((color) => color.id === team?.color) ?? TEAM_COLORS[0];
}

export function avatarForTeam(team) {
  return AVATARS.find((avatar) => avatar.id === team?.avatar) ?? AVATARS[0];
}
