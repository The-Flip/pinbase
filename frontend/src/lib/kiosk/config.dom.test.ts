import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearConfig,
  clearKioskCookie,
  DEFAULT_IDLE_SECONDS,
  DEFAULT_TITLE,
  isKioskCookieSet,
  loadConfig,
  saveConfig,
  setKioskCookie,
} from './config';

beforeAll(() => {
  // Node 22+ ships an experimental webstorage that lacks a usable in-memory
  // backing in vitest; swap in a Map-backed Storage for tests.
  const store = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => store.set(k, String(v)),
    removeItem: (k: string) => store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  } satisfies Storage);
});

describe('kiosk config (localStorage)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns null when nothing is stored', () => {
    expect(loadConfig()).toBeNull();
  });

  it('round-trips a saved config', () => {
    const config = {
      title: 'Test Title',
      idleSeconds: 60,
      items: [{ modelSlug: 'gorgar', hook: 'Talks' }],
    };
    saveConfig(config);
    expect(loadConfig()).toEqual(config);
  });

  it('clearConfig empties storage', () => {
    saveConfig({ title: 'x', idleSeconds: 30, items: [] });
    clearConfig();
    expect(loadConfig()).toBeNull();
  });

  it('falls back to defaults for malformed fields', () => {
    localStorage.setItem(
      'kioskConfig',
      JSON.stringify({ title: 123, idleSeconds: -5, items: 'nope' }),
    );
    expect(loadConfig()).toEqual({
      title: DEFAULT_TITLE,
      idleSeconds: DEFAULT_IDLE_SECONDS,
      items: [],
    });
  });

  it('drops malformed items but keeps valid ones', () => {
    localStorage.setItem(
      'kioskConfig',
      JSON.stringify({
        title: 'T',
        idleSeconds: 30,
        items: [
          { modelSlug: 'a', hook: 'h' },
          null,
          { modelSlug: 'b' },
          { modelSlug: 'c', hook: 'k' },
        ],
      }),
    );
    expect(loadConfig()?.items).toEqual([
      { modelSlug: 'a', hook: 'h' },
      { modelSlug: 'c', hook: 'k' },
    ]);
  });

  it('returns null on parse error', () => {
    localStorage.setItem('kioskConfig', '{not json');
    expect(loadConfig()).toBeNull();
  });
});

describe('kiosk cookie', () => {
  beforeEach(() => {
    clearKioskCookie();
  });

  it('setKioskCookie sets mode=kiosk', () => {
    setKioskCookie();
    expect(document.cookie).toContain('mode=kiosk');
    expect(isKioskCookieSet()).toBe(true);
  });

  it('clearKioskCookie removes the cookie', () => {
    setKioskCookie();
    clearKioskCookie();
    expect(isKioskCookieSet()).toBe(false);
  });

  it('isKioskCookieSet returns false when not set', () => {
    expect(isKioskCookieSet()).toBe(false);
  });
});
