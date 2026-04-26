import { resolve } from '$app/paths';
import { loadDeletePreview } from '$lib/delete-preview-loader';
import type { PersonDeletePreviewSchema } from '$lib/api/schema';
import type { PageLoad } from './$types';

export type DeletePreview = PersonDeletePreviewSchema;

export const load: PageLoad = ({ fetch, params }) =>
  loadDeletePreview<DeletePreview>({
    fetch,
    slug: params.slug,
    apiPath: 'people',
    notFoundRedirect: resolve('/'),
  });
