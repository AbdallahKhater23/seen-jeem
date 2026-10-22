import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createInitialGameState } from '../game/state.js';
import { STAGES } from '../game/constants.js';

const categories = Array.from({ length: 12 }, (_, index) => ({
  id: `cat-${index}`,
  backendSlug: `cat-${index}`,
  name: `فئة ${index}`,
  icon: 'Hash',
  eligibleCount: 50,
  factGroups: 50,
  capacity100Matches: false,
}));

vi.mock('../api/client.js', () => ({
  fetchCategories: vi.fn(async () => categories),
}));

vi.mock('../api/server.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    api: {
      ...actual.api,
      createMatch: vi.fn(async () => {
        throw new Error('not used in this test');
      }),
    },
  };
});

const { useGameStore } = await import('./gameStore.js');
const store = () => useGameStore.getState();

beforeEach(() => {
  useGameStore.setState({
    ...createInitialGameState(),
    categories: { status: 'ready', items: categories, error: null },
  });
});

describe('lobby category selection', () => {
  it('loads the twelve live categories', async () => {
    useGameStore.setState({ categories: { status: 'idle', items: [], error: null } });
    const result = await store().loadCategories();
    expect(result.ok).toBe(true);
    expect(store().categories.items).toHaveLength(12);
  });

  it('selects exactly six distinct categories and refuses a seventh', () => {
    for (let index = 0; index < 6; index += 1) {
      expect(store().toggleCategory(`cat-${index}`).ok).toBe(true);
    }
    expect(store().selectedCategorySlugs).toHaveLength(6);
    const seventh = store().toggleCategory('cat-6');
    expect(seventh.ok).toBe(false);
    expect(seventh.reason).toContain('ست');
    expect(store().selectedCategorySlugs).toHaveLength(6);
    expect(new Set(store().selectedCategorySlugs).size).toBe(6);
  });

  it('toggles a selected category off', () => {
    expect(store().toggleCategory('cat-0').ok).toBe(true);
    expect(store().toggleCategory('cat-0').selected).toBe(false);
    expect(store().selectedCategorySlugs).toEqual([]);
  });

  it('random quick-pick returns six distinct selectable categories', () => {
    const result = store().pickRandomCategories();
    expect(result.ok).toBe(true);
    const selected = store().selectedCategorySlugs;
    expect(selected).toHaveLength(6);
    expect(new Set(selected).size).toBe(6);
    for (const slug of selected) {
      expect(store().categories.items.some((item) => item.id === slug)).toBe(true);
    }
  });

  it('blocks match creation until six categories are selected', async () => {
    expect(store().currentStage).toBe(STAGES.LOBBY);
    useGameStore.setState({
      teams: store().teams.map((team, index) => ({ ...team, name: index === 0 ? 'أ' : 'ب' })),
      coinToss: { result: 'team-falcons', completed: true },
      selectedCategorySlugs: ['cat-0', 'cat-1'],
    });
    const result = await store().beginMatch();
    expect(result.ok).toBe(false);
    expect(result.reason).toContain('ست فئات');
  });

  it('keeps the live catalog after leaving the lobby for the power draft', () => {
    useGameStore.setState({
      teams: store().teams.map((team, index) => ({ ...team, name: index === 0 ? 'أ' : 'ب' })),
      coinToss: { result: 'team-falcons', completed: true },
      selectedCategorySlugs: ['cat-0', 'cat-1', 'cat-2', 'cat-3', 'cat-4', 'cat-5'],
    });
    const loaded = store().categories;

    expect(store().startDraft().ok).toBe(true);
    expect(store().currentStage).toBe(STAGES.DRAFT);
    expect(store().categories).toBe(loaded);
    expect(store().categories.items).toHaveLength(12);
  });

  it('refuses categories with too few eligible questions', () => {
    useGameStore.setState({
      categories: {
        status: 'ready',
        items: [{ ...categories[0], eligibleCount: 2 }],
        error: null,
      },
    });
    const result = store().toggleCategory(categories[0].id);
    expect(result.ok).toBe(false);
  });
});
