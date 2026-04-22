/**
 * Focus-mode routes render their own minimal chrome (no site Nav/Footer or
 * page-content wrapper). Patterns:
 *   /:entity/new                         create a top-level record
 *   /:entity/:slug/:child/new            create a nested record
 *   /:entity/:slug/edit                  edit (no section)
 *   /:entity/:slug/edit/:section         edit a section
 *   /:entity/:slug/delete                destructive confirmation
 *
 * `edit` and `delete` require a slug segment before them so a catalog record
 * with slug='edit' or 'delete' (e.g. /titles/delete) still gets full chrome.
 * `new` is safe without that guard because SvelteKit's route priority gives
 * /:entity/new to the create page, not the detail page.
 */
const FOCUS_MODE_RE = /\/new$|\/[^/]+\/[^/]+\/edit(\/|$)|\/[^/]+\/[^/]+\/delete$/;

export function isFocusModePath(pathname: string): boolean {
	return FOCUS_MODE_RE.test(pathname);
}
