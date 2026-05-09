import { describe, expect, it } from 'vitest';

import { rateLimitErrorBody, validationErrorBody } from './error-fixtures';
import { parseApiError } from './parse-api-error';

describe('parseApiError', () => {
  it('handles structured validation error with field errors only', () => {
    const result = parseApiError({
      detail: validationErrorBody({
        message: 'This field cannot be cleared.',
        field_errors: { name: 'This field cannot be cleared.' },
      }),
    });
    expect(result.message).toBe('name: This field cannot be cleared.');
    expect(result.fieldErrors).toEqual({ name: 'This field cannot be cleared.' });
  });

  it('handles structured validation error with form errors only', () => {
    const result = parseApiError({
      detail: validationErrorBody({
        message: 'No changes provided.',
        form_errors: ['No changes provided.'],
      }),
    });
    expect(result.message).toBe('No changes provided.');
    expect(result.fieldErrors).toEqual({});
  });

  it('handles structured validation error with both field and form errors', () => {
    const result = parseApiError({
      detail: validationErrorBody({
        message: 'Multiple errors.',
        field_errors: { year: 'Must be ≤ 2100.' },
        form_errors: ['Unknown slugs: [foo]'],
      }),
    });
    expect(result.message).toBe('Unknown slugs: [foo] year: Must be ≤ 2100.');
    expect(result.fieldErrors).toEqual({ year: 'Must be ≤ 2100.' });
  });

  it('handles legacy string detail', () => {
    const result = parseApiError({
      detail: 'Ensure this value is less than or equal to 10.',
    });
    expect(result.message).toBe('Ensure this value is less than or equal to 10.');
    expect(result.fieldErrors).toEqual({});
  });

  it('handles a malformed-body 422 reshaped by the global ValidationError handler', () => {
    // After the backend ValidationError override, malformed bodies arrive
    // in the structured envelope with field keys derived from `loc[-1]`.
    const result = parseApiError({
      detail: validationErrorBody({
        message: 'Invalid request.',
        field_errors: { count: 'Input should be a valid integer' },
      }),
    });
    expect(result.fieldErrors).toEqual({ count: 'Input should be a valid integer' });
    expect(result.message).toBe('count: Input should be a valid integer');
  });

  it('extracts message from rate-limit error body', () => {
    // Regression: rate-limit bodies previously fell through to JSON.stringify
    // because they lacked field_errors. Now dispatched via kind discriminator.
    const result = parseApiError({
      detail: rateLimitErrorBody({ bucket: 'catalog-edits', retry_after: 30 }),
    });
    expect(result.message).toBe('Rate limit exceeded.');
    expect(result.fieldErrors).toEqual({});
  });

  it('falls back to JSON for an unknown kind', () => {
    // A body with a kind the frontend doesn't recognize means the backend
    // emitted a shape the frontend hasn't been updated for. Surface loudly.
    const result = parseApiError({
      detail: { kind: 'unknown_future_thing', message: 'something' },
    });
    expect(result.fieldErrors).toEqual({});
    expect(result.message).toContain('unknown_future_thing');
  });

  it('falls back to JSON for a structured detail with no kind', () => {
    const result = parseApiError({
      detail: { message: 'oops', field_errors: {}, form_errors: [] },
    });
    expect(result.fieldErrors).toEqual({});
    expect(result.message).toContain('oops');
  });

  it('falls back to JSON for the legacy Pydantic-array shape', () => {
    // The ValidationError override (config/api.py) intercepts malformed
    // bodies before they can produce this shape, so it should never reach
    // the parser. This test pins the defensive fallback in case a future
    // upgrade reintroduces the array shape through an uncovered path.
    const result = parseApiError({
      detail: [
        {
          loc: ['body', 'fields', 'year'],
          msg: 'value is not a valid integer',
          type: 'type_error',
        },
      ],
    });
    expect(result.fieldErrors).toEqual({});
    expect(result.message).toContain('value is not a valid integer');
  });

  it('handles plain string error', () => {
    const result = parseApiError('Something went wrong');
    expect(result.message).toBe('Something went wrong');
    expect(result.fieldErrors).toEqual({});
  });

  it('falls back to JSON for unknown shapes', () => {
    const result = parseApiError({ unexpected: 'shape' });
    expect(result.message).toBe('{"unexpected":"shape"}');
    expect(result.fieldErrors).toEqual({});
  });
});
