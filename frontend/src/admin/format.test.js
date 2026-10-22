import { describe, expect, it } from 'vitest';
import {
  eventLabel,
  eventSummary,
  formatDateTime,
  formatNumber,
  percent,
  statusLabel,
  teamLabel,
} from './format.js';

describe('admin formatting', () => {
  it('formats numbers and guards invalid values', () => {
    expect(formatNumber(1500)).toBe('1,500');
    expect(formatNumber(undefined)).toBe('—');
    expect(formatNumber('not-a-number')).toBe('—');
  });

  it('clamps percentages', () => {
    expect(percent(50, 200)).toBe(25);
    expect(percent(300, 200)).toBe(100);
    expect(percent(10, 0)).toBe(0);
  });

  it('labels server team/status keys in Arabic', () => {
    expect(teamLabel('team1')).toBe('الفريق الأول');
    expect(teamLabel('team2')).toBe('الفريق الثاني');
    expect(statusLabel('completed')).toBe('مكتملة');
    expect(eventLabel('power_activated')).toBe('تفعيل قوة');
  });

  it('formats invalid and missing dates without throwing', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('not-a-date')).toBe('not-a-date');
    expect(formatDateTime('2026-10-20T10:30:00Z')).not.toBe('—');
  });

  it('summarizes resolved, power, and fallback events', () => {
    expect(
      eventSummary({
        event_type: 'tile_resolved',
        payload: {
          tile_key: 'flags-200-1',
          outcome: 'team1',
          score_team1: 200,
          score_team2: 0,
        },
      }),
    ).toContain('flags-200-1');

    expect(
      eventSummary({
        event_type: 'power_activated',
        payload: { power_id: 'steal', team: 'team2', tile_key: 'flags-400-1' },
      }),
    ).toContain('steal');

    expect(eventSummary({ event_type: 'custom', payload: {} })).toBe('بدون تفاصيل');
  });
});
