import { describe, expect, it } from 'vitest';
import { resolveFrontDoor } from './frontDoors';

describe('resolveFrontDoor', () => {
  it('returns the kiosk front door for mode=kiosk', () => {
    expect(resolveFrontDoor('kiosk')).toEqual({ homePath: '/kiosk' });
  });

  it('returns null for unknown values', () => {
    expect(resolveFrontDoor('something-else')).toBeNull();
  });

  it('returns null for null/undefined/empty', () => {
    expect(resolveFrontDoor(null)).toBeNull();
    expect(resolveFrontDoor(undefined)).toBeNull();
    expect(resolveFrontDoor('')).toBeNull();
  });
});
