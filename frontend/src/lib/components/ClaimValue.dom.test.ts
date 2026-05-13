import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import ClaimValueFixture from './ClaimValue.fixture.svelte';

describe('ClaimValue', () => {
  describe('with backend-supplied display', () => {
    it('renders the display string for a positive relationship claim', () => {
      const { container } = render(ClaimValueFixture, {
        value: { person: 13, role: 9, exists: true },
        display: 'Pat Lawlor — Art',
      });
      expect(container.textContent).toBe('Pat Lawlor — Art');
      expect(container.querySelector('s')).toBeNull();
    });

    it('strikes through the display when the underlying claim asserts exists:false', () => {
      // Negative claim with payload: "I assert that Pat Lawlor is NOT the
      // artist." display is still the human label; the <s> distinguishes
      // it from a positive assertion of the same label.
      const { container } = render(ClaimValueFixture, {
        value: { person: 13, role: 9, exists: false },
        display: 'Pat Lawlor — Art',
      });
      const struck = container.querySelector('s');
      expect(struck).not.toBeNull();
      expect(struck!.textContent).toBe('Pat Lawlor — Art');
    });

    it('prefers display over the simplify fallback', () => {
      // value would simplify to "DW" on its own, but display takes priority.
      const { container } = render(ClaimValueFixture, {
        value: { value: 'DW', exists: true },
        display: 'Doctor Who (abbrev.)',
      });
      expect(container.textContent).toBe('Doctor Who (abbrev.)');
    });
  });

  describe('without display (simplify fallback)', () => {
    it('renders a single-string-key claim as the bare scalar', () => {
      const { container } = render(ClaimValueFixture, {
        value: { value: 'DW', exists: true },
      });
      expect(container.textContent).toBe('DW');
      expect(container.querySelector('s')).toBeNull();
    });

    it('strikes through a negative single-string-key claim', () => {
      const { container } = render(ClaimValueFixture, {
        value: { value: 'DW', exists: false },
      });
      const struck = container.querySelector('s');
      expect(struck).not.toBeNull();
      expect(struck!.textContent).toBe('DW');
    });
  });

  describe('without display or simplify (formatValue fallback)', () => {
    it('renders bare scalars verbatim', () => {
      const { container } = render(ClaimValueFixture, { value: 'solid-state' });
      expect(container.textContent).toBe('solid-state');
    });

    it('renders null / undefined / empty string as em-dash', () => {
      const cases: unknown[] = [null, undefined, ''];
      for (const value of cases) {
        const { container } = render(ClaimValueFixture, { value });
        expect(container.textContent).toBe('—');
      }
    });

    it('JSON-stringifies unrecognised dict shapes', () => {
      // Multi-key relationship claims the backend declined fall through.
      const { container } = render(ClaimValueFixture, {
        value: { person: 13, role: 9, exists: true },
      });
      expect(container.textContent).toBe('{"person":13,"role":9,"exists":true}');
    });
  });
});
