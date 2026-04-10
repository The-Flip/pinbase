<script lang="ts">
	import client from '$lib/api/client';
	import { createDebouncedSearch, formatCitationResult } from '../search-helpers';
	import {
		suppressChildResults,
		detectSourceFromUrl,
		type CitationSourceResult
	} from './citation-types';
	import DropdownHeader from '../DropdownHeader.svelte';
	import DropdownItem from '../DropdownItem.svelte';
	import DropdownSearchInput from '../DropdownSearchInput.svelte';

	let {
		onselectsource,
		onselectsourcewithid,
		onstartcreate,
		oncancel,
		onback
	}: {
		onselectsource: (source: CitationSourceResult) => void;
		onselectsourcewithid: (source: CitationSourceResult, identifier: string) => void;
		onstartcreate: (prefillName: string) => void;
		oncancel: () => void;
		onback: () => void;
	} = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let searchQuery = $state('');
	let searchResults = $state<CitationSourceResult[]>([]);
	let activeIndex = $state(-1);
	let searchInputEl: HTMLInputElement | undefined = $state();
	let resultsListEl: HTMLDivElement | undefined = $state();
	let resolving = $state(false);
	let resolveError = $state(false);
	let resolveGeneration = 0;

	// -----------------------------------------------------------------------
	// URL detection (synchronous, runs on every input change)
	// -----------------------------------------------------------------------

	let detected = $derived(detectSourceFromUrl(searchQuery));

	// -----------------------------------------------------------------------
	// Debounced search
	// -----------------------------------------------------------------------

	const debouncedSearch = createDebouncedSearch<CitationSourceResult>(
		async (q: string) => {
			if (!q.trim()) return [];
			const { data } = await client.GET('/api/citation-sources/search/', {
				params: { query: { q } }
			});
			return (data ?? []) as CitationSourceResult[];
		},
		(results) => {
			searchResults = suppressChildResults(results);
		},
		100
	);

	function handleSearchInput(e: Event) {
		searchQuery = (e.currentTarget as HTMLInputElement).value;
		activeIndex = -1;
		if (resolving || resolveError) {
			resolving = false;
			resolveError = false;
			resolveGeneration++;
		}
		debouncedSearch.search(searchQuery);
	}

	// -----------------------------------------------------------------------
	// Item index math
	// -----------------------------------------------------------------------

	let showCreateNew = $derived(searchQuery.trim().length > 0);
	let resultsStartIndex = $derived(detected ? 1 : 0);
	let createNewIndex = $derived(resultsStartIndex + searchResults.length);
	let totalItems = $derived((detected ? 1 : 0) + searchResults.length + (showCreateNew ? 1 : 0));

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	$effect(() => {
		requestAnimationFrame(() => searchInputEl?.focus());
	});

	function selectSource(source: CitationSourceResult) {
		debouncedSearch.cancel();
		onselectsource(source);
	}

	async function selectDetected() {
		if (!detected || resolving) return;
		debouncedSearch.cancel();
		resolving = true;
		const gen = ++resolveGeneration;
		const { sourceName, machineId } = detected;

		try {
			const { data } = await client.GET('/api/citation-sources/search/', {
				params: { query: { q: sourceName } }
			});
			if (gen !== resolveGeneration) return;

			const results = (data ?? []) as CitationSourceResult[];
			const parent = results.find((r) => r.is_abstract);
			resolving = false;

			if (parent) {
				onselectsourcewithid(parent, machineId);
			} else {
				resolveError = true;
				console.warn(`Citation search: no abstract parent found for "${sourceName}"`);
			}
		} catch (err) {
			if (gen === resolveGeneration) {
				resolving = false;
				resolveError = true;
				console.warn('Citation search: failed to resolve parent source', err);
			}
		}
	}

	function startCreate() {
		debouncedSearch.cancel();
		onstartcreate(searchQuery);
	}

	// -----------------------------------------------------------------------
	// Keyboard navigation
	// -----------------------------------------------------------------------

	function handleKeydown(e: KeyboardEvent) {
		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				activeIndex = Math.min(activeIndex + 1, totalItems - 1);
				scrollActiveIntoView();
				break;
			case 'ArrowUp':
				e.preventDefault();
				activeIndex = Math.max(activeIndex - 1, -1);
				scrollActiveIntoView();
				break;
			case 'Enter':
				e.preventDefault();
				if (activeIndex < 0) break;
				if (detected && activeIndex === 0) {
					selectDetected();
				} else if (activeIndex >= resultsStartIndex && activeIndex < createNewIndex) {
					selectSource(searchResults[activeIndex - resultsStartIndex]);
				} else if (showCreateNew && activeIndex === createNewIndex) {
					startCreate();
				}
				break;
			case 'Escape':
				e.preventDefault();
				oncancel();
				break;
			case 'Backspace':
				if (!searchQuery) {
					e.preventDefault();
					onback();
				}
				break;
			case 'ArrowLeft':
				if (searchInputEl && searchInputEl.selectionStart === 0) {
					e.preventDefault();
					onback();
				}
				break;
		}
	}

	function scrollActiveIntoView() {
		requestAnimationFrame(() => {
			resultsListEl?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
		});
	}
</script>

<DropdownHeader {onback}>Citation</DropdownHeader>
<DropdownSearchInput
	placeholder="Search sources..."
	value={searchQuery}
	oninput={handleSearchInput}
	onkeydown={handleKeydown}
	bind:inputRef={searchInputEl}
/>
<div class="results-list" bind:this={resultsListEl}>
	{#if detected}
		<DropdownItem
			active={activeIndex === 0}
			onselect={selectDetected}
			onhover={() => (activeIndex = 0)}
		>
			<span class="item-label">{detected.sourceName} Machine {detected.machineId}</span>
			{#if resolving}
				<span class="item-desc">Loading…</span>
			{:else if resolveError}
				<span class="item-desc item-error">Not found</span>
			{/if}
		</DropdownItem>
	{/if}
	{#each searchResults as source, i (source.id)}
		<DropdownItem
			active={i + resultsStartIndex === activeIndex}
			onselect={() => selectSource(source)}
			onhover={() => (activeIndex = i + resultsStartIndex)}
		>
			<span class="item-label">{formatCitationResult(source)}</span>
			<span class="item-desc">{source.source_type}</span>
		</DropdownItem>
	{/each}
	{#if showCreateNew}
		<DropdownItem
			active={activeIndex === createNewIndex}
			onselect={startCreate}
			onhover={() => (activeIndex = createNewIndex)}
		>
			<span class="item-label create-new">+ Create "{searchQuery}"</span>
		</DropdownItem>
	{/if}
	{#if !detected && !searchResults.length && !searchQuery.trim()}
		<div class="no-results">Type to search sources…</div>
	{:else if !detected && !searchResults.length && searchQuery.trim()}
		<div class="no-results">No matches</div>
	{/if}
</div>

<style>
	.item-label {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.item-desc {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
		flex-shrink: 0;
	}

	.item-error {
		color: var(--color-danger, #c00);
	}

	.create-new {
		color: var(--color-text-muted);
		font-style: italic;
	}

	.results-list {
		max-height: 14rem;
		overflow-y: auto;
	}

	.no-results {
		padding: var(--size-3);
		color: var(--color-text-muted);
		text-align: center;
		font-size: var(--font-size-1);
	}
</style>
