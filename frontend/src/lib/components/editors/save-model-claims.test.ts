import { describe, expect, it, vi, beforeEach } from 'vitest';

const { PATCH } = vi.hoisted(() => ({
	PATCH: vi.fn()
}));

const { invalidateAll } = vi.hoisted(() => ({
	invalidateAll: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	default: { PATCH }
}));

vi.mock('$app/navigation', () => ({
	invalidateAll
}));

import { saveModelClaims } from './save-model-claims';

describe('saveModelClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
	});

	it('returns ok and invalidates on success', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		const result = await saveModelClaims('medieval-madness', {
			fields: { description: 'new text' }
		});

		expect(result).toEqual({ ok: true });
		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { description: 'new text' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledOnce();
	});

	it('returns error string on failure', async () => {
		PATCH.mockResolvedValue({ data: undefined, error: { detail: 'bad request' } });

		const result = await saveModelClaims('medieval-madness', {
			fields: { description: 'x' }
		});

		expect(result).toEqual({ ok: false, error: '{"detail":"bad request"}' });
		expect(invalidateAll).not.toHaveBeenCalled();
	});

	it('handles string errors', async () => {
		PATCH.mockResolvedValue({ data: undefined, error: 'Something went wrong' });

		const result = await saveModelClaims('medieval-madness', {
			fields: { description: 'x' }
		});

		expect(result).toEqual({ ok: false, error: 'Something went wrong' });
	});

	it('sends credits-only body with default fields', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		const credits = [{ person_slug: 'pat-lawlor', role: 'game-design' }];
		await saveModelClaims('medieval-madness', { credits });

		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: {}, note: '', credits }
		});
	});

	it('passes note override', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		await saveModelClaims('medieval-madness', {
			fields: { year: 1997 },
			note: 'Corrected per IPDB'
		});

		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { year: 1997 }, note: 'Corrected per IPDB' }
		});
	});

	it('passes citation override', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		const citation = { citation_instance_id: 42 };
		await saveModelClaims('medieval-madness', {
			fields: { year: 1997 },
			citation
		});

		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { year: 1997 }, note: '', citation }
		});
	});
});
