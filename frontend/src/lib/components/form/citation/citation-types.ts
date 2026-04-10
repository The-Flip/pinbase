import type { components } from '$lib/api/schema';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CitationSourceResult = components['schemas']['CitationSourceSearchSchema'];
export type ChildSource = components['schemas']['CitationSourceChildSchema'];

/** Subset of a search result carried through the state machine after selecting an abstract source. */
export type ParentContext = {
	id: number;
	name: string;
	source_type: string;
	author: string;
	child_input_mode: string | null;
	/** Stable key for identifier parsing dispatch. Pending backend model field. */
	identifier_key: string | null;
};

/** An unsaved draft of a CitationInstance.  Accumulates across stages: search sets sourceId, identify may change it, locator sets locator. */
export type CitationInstanceDraft = {
	sourceId: number | null;
	sourceName: string;
	locator: string;
	skipLocator: boolean;
};

/** Which stage the citation flow is in. Each variant carries only the context that stage needs. */
export type CiteState =
	| { stage: 'search'; draft: CitationInstanceDraft }
	| {
			stage: 'identify';
			draft: CitationInstanceDraft;
			parent: ParentContext;
			prefillIdentifier?: string;
	  }
	| {
			stage: 'create';
			draft: CitationInstanceDraft;
			parent: ParentContext | null;
			prefillName: string;
	  }
	| { stage: 'locator'; draft: CitationInstanceDraft };

/** Inputs to the state machine, dispatched by stage components via the orchestrator. */
export type CiteAction =
	| { type: 'select_source'; source: CitationSourceResult }
	| { type: 'select_source_with_id'; source: CitationSourceResult; identifier: string }
	| { type: 'select_child'; sourceId: number; sourceName: string; skipLocator: boolean }
	| { type: 'start_create'; prefillName: string }
	| { type: 'created'; sourceId: number; sourceName: string; skipLocator: boolean };

// ---------------------------------------------------------------------------
// Pure functions
// ---------------------------------------------------------------------------

export function suppressChildResults(results: CitationSourceResult[]): CitationSourceResult[] {
	const resultIds = new Set(results.map((r) => r.id));
	return results.filter((r) => !r.parent_id || !resultIds.has(r.parent_id));
}

const IPDB_RE = /^https?:\/\/(?:www\.)?ipdb\.org\/machine\.cgi\?id=(\d+)/;
const OPDB_RE = /^https?:\/\/(?:www\.)?opdb\.org\/machines\/([A-Za-z0-9_-]+)/;

/** Pre-selection: matches a pasted URL before any source is selected. */
export function detectSourceFromUrl(url: string): { sourceName: string; machineId: string } | null {
	let match = IPDB_RE.exec(url);
	if (match) return { sourceName: 'IPDB', machineId: match[1] };

	match = OPDB_RE.exec(url);
	if (match) return { sourceName: 'OPDB', machineId: match[1] };

	return null;
}

const BARE_DIGITS = /^\d+$/;
const BARE_OPDB_ID = /^[A-Za-z0-9_-]+$/;

/**
 * Post-selection: extracts a normalized identifier from user input.
 *
 * Instance-level rules (identifierKey: 'ipdb', 'opdb') take precedence.
 * Type-level rules (sourceType: 'book' → ISBN) are the fallback.
 */
export function parseIdentifierInput(
	sourceType: string,
	identifierKey: string | null,
	input: string
): string | null {
	if (!input) return null;

	// Instance-level: dispatch on backend-provided key
	if (identifierKey) {
		switch (identifierKey) {
			case 'ipdb': {
				const urlMatch = IPDB_RE.exec(input);
				if (urlMatch) return urlMatch[1];
				return BARE_DIGITS.test(input) ? input : null;
			}
			case 'opdb': {
				const urlMatch = OPDB_RE.exec(input);
				if (urlMatch) return urlMatch[1];
				return BARE_OPDB_ID.test(input) ? input : null;
			}
			default:
				return null;
		}
	}

	// Type-level: derive from source type
	switch (sourceType) {
		case 'book':
			return parseIsbn(input);
		default:
			return null;
	}
}

/** Strip hyphens/spaces from input, validate check digit, return normalized ISBN or null. */
function parseIsbn(input: string): string | null {
	const stripped = input.replace(/[-\s]/g, '').toUpperCase();
	if (stripped.length === 13 && /^\d{13}$/.test(stripped)) {
		return isValidIsbn13(stripped) ? stripped : null;
	}
	if (stripped.length === 10 && /^\d{9}[\dX]$/.test(stripped)) {
		return isValidIsbn10(stripped) ? stripped : null;
	}
	return null;
}

function isValidIsbn13(isbn: string): boolean {
	let sum = 0;
	for (let i = 0; i < 13; i++) {
		sum += Number(isbn[i]) * (i % 2 === 0 ? 1 : 3);
	}
	return sum % 10 === 0;
}

function isValidIsbn10(isbn: string): boolean {
	let sum = 0;
	for (let i = 0; i < 10; i++) {
		const val = isbn[i] === 'X' ? 10 : Number(isbn[i]);
		sum += val * (10 - i);
	}
	return sum % 11 === 0;
}

/** Construct a canonical URL for a child source from its identifier key and parsed ID. */
export function buildChildUrl(identifierKey: string | null, parsedId: string): string | null {
	switch (identifierKey) {
		case 'ipdb':
			return `https://www.ipdb.org/machine.cgi?id=${parsedId}`;
		case 'opdb':
			return `https://opdb.org/machines/${parsedId}`;
		default:
			return null;
	}
}

export function isDraftSubmittable(draft: CitationInstanceDraft): boolean {
	return draft.sourceId !== null && (draft.locator.length > 0 || draft.skipLocator);
}

export function emptyDraft(): CitationInstanceDraft {
	return { sourceId: null, sourceName: '', locator: '', skipLocator: false };
}

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

function parentContextFromSource(source: CitationSourceResult): ParentContext {
	return {
		id: source.id,
		name: source.name,
		source_type: source.source_type,
		author: source.author,
		child_input_mode: source.child_input_mode ?? null,
		// TODO: clean up cast once backend adds identifier_key to the schema
		identifier_key: ((source as Record<string, unknown>).identifier_key as string | null) ?? null
	};
}

/** Invalid action/state combos return current state unchanged. */
export function transition(state: CiteState, action: CiteAction): CiteState {
	switch (action.type) {
		case 'select_source': {
			if (state.stage !== 'search') return state;
			const draft = { ...state.draft, sourceId: action.source.id, sourceName: action.source.name };
			if (action.source.is_abstract) {
				return {
					stage: 'identify',
					draft: { ...draft, skipLocator: action.source.skip_locator },
					parent: parentContextFromSource(action.source)
				};
			}
			return {
				stage: 'locator',
				draft: { ...draft, skipLocator: action.source.skip_locator }
			};
		}

		case 'select_source_with_id': {
			if (state.stage !== 'search') return state;
			return {
				stage: 'identify',
				draft: {
					...state.draft,
					sourceId: action.source.id,
					sourceName: action.source.name
				},
				parent: parentContextFromSource(action.source),
				prefillIdentifier: action.identifier
			};
		}

		case 'select_child': {
			if (state.stage !== 'identify') return state;
			return {
				stage: 'locator',
				draft: {
					...state.draft,
					sourceId: action.sourceId,
					sourceName: action.sourceName,
					skipLocator: action.skipLocator
				}
			};
		}

		case 'start_create': {
			if (state.stage !== 'search' && state.stage !== 'identify') return state;
			return {
				stage: 'create',
				draft: state.draft,
				parent: state.stage === 'identify' ? state.parent : null,
				prefillName: action.prefillName
			};
		}

		case 'created': {
			if (state.stage !== 'create') return state;
			return {
				stage: 'locator',
				draft: {
					...state.draft,
					sourceId: action.sourceId,
					sourceName: action.sourceName,
					skipLocator: action.skipLocator
				}
			};
		}
	}
}
