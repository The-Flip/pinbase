import { resolve } from '$app/paths';
import { loadDeletePreview } from '$lib/delete-preview-loader';
import type { TaxonomyDeletePreviewSchema } from '$lib/api/schema';
import type { PageLoad } from './$types';

export type DeletePreview = TaxonomyDeletePreviewSchema;

// The preview already carries `parent` because the CE registrar was wired
// with parent_field="manufacturer" — no separate detail fetch needed.
export const load: PageLoad = ({ fetch, params }) =>
  loadDeletePreview<DeletePreview>({
    fetch,
    slug: params.slug,
    apiPath: 'corporate-entities',
    notFoundRedirect: resolve('/corporate-entities'),
  });
