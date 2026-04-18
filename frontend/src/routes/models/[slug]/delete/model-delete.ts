/**
 * Client shim for the Model delete flow. Mirrors title-delete.ts.
 *
 * The Undo helper lives in ``$lib/undo-delete`` and is re-exported here for
 * callers that want the whole surface from one module.
 */

import client from '$lib/api/client';
import { parseApiError } from '$lib/components/editors/save-claims-shared';
import type { components } from '$lib/api/schema';
import type { EditCitationSelection } from '$lib/edit-citation';
import { buildEditCitationRequest } from '$lib/edit-citation';

export type DeletePreview = components['schemas']['ModelDeletePreviewSchema'];
export type DeleteResponse = components['schemas']['ModelDeleteResponseSchema'];
export type BlockingReferrer = components['schemas']['BlockingReferrerSchema'];

export type DeleteOutcome =
	| { kind: 'ok'; data: DeleteResponse }
	| { kind: 'rate_limited'; retryAfterSeconds: number; message: string }
	| { kind: 'blocked'; blockedBy: BlockingReferrer[]; message: string }
	| { kind: 'form_error'; message: string };

export async function submitDelete(
	slug: string,
	opts: { note?: string; citation?: EditCitationSelection | null } = {}
): Promise<DeleteOutcome> {
	const { data, error, response } = await client.POST('/api/models/{slug}/delete/', {
		params: { path: { slug } },
		body: {
			note: opts.note ?? '',
			citation: buildEditCitationRequest(opts.citation ?? null)
		}
	});

	if (response.status === 429) {
		const retryAfter = Number(response.headers.get('Retry-After') ?? '86400');
		const hours = Math.max(1, Math.round(retryAfter / 3600));
		return {
			kind: 'rate_limited',
			retryAfterSeconds: retryAfter,
			message: `You've reached the delete limit. Try again in about ${hours} hour${hours === 1 ? '' : 's'}.`
		};
	}

	if (response.status === 422) {
		const body = (await response
			.clone()
			.json()
			.catch(() => null)) as { blocked_by?: BlockingReferrer[]; detail?: unknown } | null;
		if (body && Array.isArray(body.blocked_by)) {
			return {
				kind: 'blocked',
				blockedBy: body.blocked_by,
				message:
					typeof body.detail === 'string'
						? body.detail
						: 'Cannot delete: active references would be left dangling.'
			};
		}
	}

	if (error || !data) {
		const parsed = parseApiError(error);
		return { kind: 'form_error', message: parsed.message || 'Could not delete record.' };
	}

	return { kind: 'ok', data };
}

export { submitUndoDelete, type UndoOutcome } from '$lib/undo-delete';
