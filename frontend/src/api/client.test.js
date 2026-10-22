import { describe, expect, it, vi, afterEach } from 'vitest';
import { normalizeCategories, startPoolSync } from './client.js';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('normalizeCategories', () => {
  it('maps the twelve backend slugs into stable UI categories', () => {
    const rows = [
      {
        id: 1,
        slug: 'spotdiff',
        name_ar: 'طلع الفرق',
        icon: 'Eye',
        sort_order: 12,
        eligible_count: 800,
        fact_groups: 800,
        capacity_100_matches: true,
      },
      {
        id: 2,
        slug: 'capitals',
        name_ar: 'عواصم وجغرافيا',
        icon: 'MapPin',
        sort_order: 2,
        eligible_count: 90,
        fact_groups: 100,
        capacity_100_matches: false,
      },
    ];
    const result = normalizeCategories(rows);
    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({
      id: 'spot',
      backendSlug: 'spotdiff',
      name: 'طلع الفرق',
      icon: 'Eye',
      eligibleCount: 800,
      capacity100Matches: true,
    });
    expect(result[1]).toMatchObject({ id: 'capitals', eligibleCount: 90 });
    expect(normalizeCategories(null)).toEqual([]);
  });

  it('accepts a missing count without inventing availability', () => {
    const [row] = normalizeCategories([{ slug: 'general', name_ar: 'عام', icon: 'Lightbulb' }]);
    expect(row.eligibleCount).toBe(0);
    expect(row.factGroups).toBe(0);
    expect(row.capacity100Matches).toBe(false);
  });
});

describe('pool sync client', () => {
  it('reports the real accepted/queued state from the backend', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      text: async () =>
        JSON.stringify({ accepted: true, status: 'queued', job_id: 3, message: 'queued' }),
    }));
    vi.stubGlobal('fetch', fetchMock);
    const result = await startPoolSync('restcountries');
    expect(result.accepted).toBe(true);
    expect(result.status).toBe('queued');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/pool/sync?source=restcountries'),
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
