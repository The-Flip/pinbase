import { describe, expect, it, vi } from 'vitest';
import { isRedirect } from '@sveltejs/kit';
import { load } from './+page.server';

type LoadEvent = Parameters<typeof load>[0];

function makeEvent(modeCookie: string | undefined): LoadEvent {
  return {
    cookies: { get: vi.fn().mockReturnValue(modeCookie) },
  } as unknown as LoadEvent;
}

describe('homepage server load', () => {
  it('redirects to /kiosk when mode=kiosk cookie is set', () => {
    try {
      load(makeEvent('kiosk'));
      throw new Error('expected redirect');
    } catch (err) {
      if (!isRedirect(err)) throw err;
      expect(err.status).toBe(307);
      expect(err.location).toBe('/kiosk');
    }
  });

  it('returns empty object when no mode cookie', () => {
    expect(load(makeEvent(undefined))).toEqual({});
  });

  it('returns empty object when mode is unknown', () => {
    expect(load(makeEvent('something-else'))).toEqual({});
  });
});
