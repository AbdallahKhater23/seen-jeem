import { describe, expect, it } from 'vitest';
import { isEditableTarget, shouldIgnoreShortcut } from './keyboard.js';

function event(overrides = {}) {
  return {
    key: '1',
    target: { tagName: 'BUTTON', closest: () => null },
    repeat: false,
    isComposing: false,
    keyCode: 49,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    ...overrides,
  };
}

describe('keyboard shortcut filtering', () => {
  it('detects text inputs, textareas, selects, and contenteditable', () => {
    expect(isEditableTarget({ tagName: 'INPUT' })).toBe(true);
    expect(isEditableTarget({ tagName: 'TEXTAREA' })).toBe(true);
    expect(isEditableTarget({ tagName: 'SELECT' })).toBe(true);
    expect(isEditableTarget({ isContentEditable: true, tagName: 'DIV' })).toBe(true);
    expect(isEditableTarget({ tagName: 'DIV', closest: () => ({}) })).toBe(true);
    expect(isEditableTarget({ tagName: 'BUTTON', closest: () => null })).toBe(false);
  });

  it('ignores shortcuts inside inputs', () => {
    expect(shouldIgnoreShortcut(event({ target: { tagName: 'INPUT' } }))).toBe(true);
    expect(
      shouldIgnoreShortcut(event({ target: { tagName: 'DIV', closest: () => ({}) } })),
    ).toBe(true);
  });

  it('ignores IME composition, repeated keydown, and modifier chords', () => {
    expect(shouldIgnoreShortcut(event({ isComposing: true }))).toBe(true);
    expect(shouldIgnoreShortcut(event({ keyCode: 229 }))).toBe(true);
    expect(shouldIgnoreShortcut(event({ repeat: true }))).toBe(true);
    expect(shouldIgnoreShortcut(event({ ctrlKey: true }))).toBe(true);
    expect(shouldIgnoreShortcut(event({ metaKey: true }))).toBe(true);
    expect(shouldIgnoreShortcut(event({ altKey: true }))).toBe(true);
  });

  it('allows normal game keys on buttons and the page', () => {
    expect(shouldIgnoreShortcut(event())).toBe(false);
    expect(shouldIgnoreShortcut(event({ target: { tagName: 'BODY' } }))).toBe(false);
  });

  it('ignores missing events safely', () => {
    expect(shouldIgnoreShortcut(null)).toBe(true);
  });
});
