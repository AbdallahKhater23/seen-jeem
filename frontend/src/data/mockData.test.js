import { describe, expect, it } from 'vitest';
import {
  BACKUPS,
  CATEGORIES,
  POINT_VALUES,
  POWERS,
  QUESTIONS,
  TILES,
  TOTAL_PRIMARY_TILES,
  flagUrl,
  getCompatibleBackups,
  validateGameData,
} from './mockData.js';

describe('game dataset', () => {
  it('passes the strict development validator', () => {
    expect(() => validateGameData()).not.toThrow();
    expect(validateGameData()).toBe(true);
  });

  it('has six categories and 36 unique tiles with two of each value per category', () => {
    expect(CATEGORIES).toHaveLength(6);
    expect(TILES).toHaveLength(36);
    expect(TOTAL_PRIMARY_TILES).toBe(36);
    expect(new Set(TILES.map((tile) => tile.id)).size).toBe(36);
    for (const category of CATEGORIES) {
      const categoryTiles = TILES.filter((tile) => tile.categoryId === category.id);
      expect(categoryTiles).toHaveLength(6);
      for (const points of POINT_VALUES) {
        expect(categoryTiles.filter((tile) => tile.points === points)).toHaveLength(2);
      }
    }
  });

  it('keeps questions, tiles and categories referentially consistent', () => {
    const questionIds = new Set(QUESTIONS.map((question) => question.id));
    expect(questionIds.size).toBe(36);
    for (const tile of TILES) {
      const question = QUESTIONS.find((item) => item.id === tile.questionId);
      expect(question).toBeTruthy();
      expect(question.tileId).toBe(tile.id);
      expect(question.categoryId).toBe(tile.categoryId);
      expect(question.points).toBe(tile.points);
      expect(question.answer.length).toBeGreaterThan(0);
      expect(question.explanation.length).toBeGreaterThan(0);
      expect(question.tolerance.length).toBeGreaterThan(0);
    }
  });

  it('uses valid ISO alpha-2 codes for flag questions', () => {
    const flagQuestions = QUESTIONS.filter((question) => question.type === 'flag');
    expect(flagQuestions.length).toBeGreaterThan(0);
    for (const question of flagQuestions) {
      expect(question.iso2).toMatch(/^[a-z]{2}$/);
      expect(flagUrl(question.iso2)).toBe(`https://flagcdn.com/w640/${question.iso2}.png`);
    }
  });

  it('gives career questions chronological structured stops', () => {
    const careerQuestions = QUESTIONS.filter((question) => question.type === 'career');
    expect(careerQuestions).toHaveLength(6);
    for (const question of careerQuestions) {
      expect(question.career.length).toBeGreaterThanOrEqual(2);
      let previous = 0;
      for (const stop of question.career) {
        const startYear = Number(stop.years.match(/\d{4}/)?.[0]);
        expect(Number.isFinite(startYear)).toBe(true);
        expect(startYear).toBeGreaterThanOrEqual(previous);
        previous = startYear;
      }
    }
  });

  it('defines exactly three in-bounds difference targets for every spot scene', () => {
    const spotQuestions = QUESTIONS.filter((question) => question.type === 'spot_diff');
    expect(spotQuestions).toHaveLength(6);
    for (const question of spotQuestions) {
      expect(question.differences).toHaveLength(3);
      expect(new Set(question.differences.map((difference) => difference.id)).size).toBe(3);
      for (const difference of question.differences) {
        expect(difference.x - difference.r).toBeGreaterThanOrEqual(0);
        expect(difference.x + difference.r).toBeLessThanOrEqual(400);
        expect(difference.y - difference.r).toBeGreaterThanOrEqual(0);
        expect(difference.y + difference.r).toBeLessThanOrEqual(300);
      }
    }
  });

  it('has seven powers with valid activation metadata and unique IDs', () => {
    expect(POWERS).toHaveLength(7);
    expect(new Set(POWERS.map((power) => power.id)).size).toBe(7);
    for (const power of POWERS) {
      expect(['active', 'defending']).toContain(power.activation.side);
      expect(power.activation.phases.length).toBeGreaterThan(0);
      expect(power.activation.beforeReveal).toBe(true);
    }
  });

  it('has six backups compatible with every primary tile', () => {
    expect(BACKUPS).toHaveLength(6);
    for (const tile of TILES) {
      const compatible = getCompatibleBackups(tile.categoryId, tile.points);
      expect(compatible.length).toBe(6);
    }
    const used = BACKUPS.map((backup) => backup.id);
    expect(getCompatibleBackups('flags', 200, used)).toHaveLength(0);
    expect(getCompatibleBackups('flags', 200, used.slice(0, 5))).toHaveLength(1);
  });

  it('uses only the three permitted point values', () => {
    expect(POINT_VALUES).toEqual([200, 400, 600]);
    for (const question of QUESTIONS) {
      expect(POINT_VALUES).toContain(question.points);
    }
  });
});
