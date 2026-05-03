import { render } from '@testing-library/svelte';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import KioskMode from './KioskMode.svelte';

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));

beforeAll(() => {
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

describe('KioskMode', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    goto.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('navigates to /kiosk after the configured idle timeout', () => {
    localStorage.setItem('kioskConfig', JSON.stringify({ title: 't', idleSeconds: 5, items: [] }));

    render(KioskMode);

    vi.advanceTimersByTime(5000);
    expect(goto).toHaveBeenCalledWith('/kiosk', { invalidateAll: true, replaceState: true });
  });

  it('resets the timer when the user interacts', () => {
    localStorage.setItem('kioskConfig', JSON.stringify({ title: 't', idleSeconds: 5, items: [] }));

    render(KioskMode);

    vi.advanceTimersByTime(4000);
    window.dispatchEvent(new Event('pointerdown'));
    vi.advanceTimersByTime(4000);
    expect(goto).not.toHaveBeenCalled();

    vi.advanceTimersByTime(2000);
    expect(goto).toHaveBeenCalledTimes(1);
  });

  it('uses default idle timeout when no config is stored', () => {
    render(KioskMode);

    vi.advanceTimersByTime(180 * 1000 - 1);
    expect(goto).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(goto).toHaveBeenCalledTimes(1);
  });

  it('cleans up timer and listeners on unmount', () => {
    localStorage.setItem('kioskConfig', JSON.stringify({ title: 't', idleSeconds: 5, items: [] }));

    const { unmount } = render(KioskMode);
    unmount();

    vi.advanceTimersByTime(10_000);
    expect(goto).not.toHaveBeenCalled();
  });
});
