/**
 * Parse backend API error responses into a human-readable message and
 * per-field error map. Shared across every save / delete / create flow.
 */

import type { RateLimitErrorBodySchema, ValidationErrorBodySchema } from './schema';

export type FieldErrors = Record<string, string>;

type ParsedError = { message: string; fieldErrors: FieldErrors };

type StructuredErrorBody = ValidationErrorBodySchema | RateLimitErrorBodySchema;

function isStructuredErrorBody(value: unknown): value is StructuredErrorBody {
  if (typeof value !== 'object' || value === null || !('kind' in value)) return false;
  // Defer the closed-set check to the switch's `satisfies never` default —
  // the type system is the source of truth for which kinds are valid.
  return typeof (value as { kind: unknown }).kind === 'string';
}

function plain(message: string): ParsedError {
  return { message, fieldErrors: {} };
}

/**
 * Structured error bodies are dispatched by `detail.kind` — a discriminator
 * emitted by every structured handler in `backend/config/api.py`. Cases:
 *
 * - `kind: "validation_error"` — `{ message, field_errors, form_errors }`
 *   from `StructuredValidationError` and Ninja's malformed-body handler.
 *   The only branch that produces field-level errors.
 * - `kind: "rate_limit"` — `{ message, bucket, retry_after }` from
 *   `RateLimitExceededError`.
 *
 * Plain-string `detail` from `HttpError(...)` and stock Ninja 401/404/etc.
 * remains supported as the unstructured fallback. Anything else (unknown
 * `kind`, structured detail without `kind`, raw arrays) falls through to
 * `JSON.stringify` — surfacing a backend/frontend mismatch loudly rather
 * than rendering garbage.
 */
export function parseApiError(error: unknown): ParsedError {
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    const { detail } = error as { detail: unknown };

    if (typeof detail === 'string') return plain(detail);

    if (isStructuredErrorBody(detail)) {
      switch (detail.kind) {
        case 'validation_error': {
          const { field_errors, form_errors, message } = detail;
          const parts = [
            ...form_errors,
            ...Object.entries(field_errors).map(([k, v]) => `${k}: ${v}`),
          ];
          return {
            message: parts.length > 0 ? parts.join(' ') : message,
            fieldErrors: field_errors,
          };
        }
        case 'rate_limit':
          return plain(detail.message);
        default:
          // Exhaustiveness: adding a new kind to StructuredErrorBody without
          // adding a case here fails to compile. Unknown kinds at runtime fall
          // through to the outer JSON.stringify return.
          detail satisfies never;
      }
    }
  }

  if (typeof error === 'string') return plain(error);
  return plain(JSON.stringify(error));
}
