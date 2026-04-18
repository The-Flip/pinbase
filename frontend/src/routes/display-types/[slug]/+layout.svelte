<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { SITE_NAME } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import PageActionBar from '$lib/components/PageActionBar.svelte';
	import RecordDetailShell from '$lib/components/RecordDetailShell.svelte';
	import SectionEditorHost from '$lib/components/SectionEditorHost.svelte';
	import { type EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import {
		findDisplayTypeSectionByKey,
		findDisplayTypeSectionBySegment,
		DISPLAY_TYPE_EDIT_SECTIONS,
		type DisplayTypeEditSectionKey
	} from '$lib/components/editors/display-type-edit-sections';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import { resolveDetailSubrouteMode } from '$lib/detail-subroute-mode';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';
	import DisplayTypeEditorSwitch from './edit/DisplayTypeEditorSwitch.svelte';

	let { data, children } = $props();
	let profile = $derived(data.profile);
	let slug = $derived(page.params.slug);

	let metaDescription = $derived(profile.description?.text || `${profile.name} — ${SITE_NAME}`);
	let mode = $derived(resolveDetailSubrouteMode(page.url.pathname));
	let isDetail = $derived(mode === 'detail');
	let isEdit = $derived(mode === 'edit');
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT);
	let isMobile = $derived(isMobileFlag.current);
	let editing = $state<DisplayTypeEditSectionKey | null>(null);
	let syncEnabled = $derived(!isMobile && !isEdit);
	let lastUrlEditing = $state<DisplayTypeEditSectionKey | null>(null);

	$effect(() => {
		auth.load();
	});

	function updateEditQuery(nextEditing: DisplayTypeEditSectionKey | null) {
		const current = page.url.searchParams.get('edit') ?? null;
		const desired = nextEditing
			? (findDisplayTypeSectionByKey(nextEditing)?.segment ?? null)
			: null;
		if (current === desired) return;
		const url = new URL(page.url);
		if (desired) url.searchParams.set('edit', desired);
		else url.searchParams.delete('edit');
		goto(`${url.pathname}${url.search}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	function resolveEditingFromUrl(): DisplayTypeEditSectionKey | null {
		if (!syncEnabled) return null;
		const section = page.url.searchParams.get('edit');
		const matched = section ? findDisplayTypeSectionBySegment(section) : undefined;
		return matched?.key ?? null;
	}

	$effect(() => {
		const nextEditing = resolveEditingFromUrl();
		lastUrlEditing = nextEditing;
		editing = nextEditing;
	});

	$effect(() => {
		if (!syncEnabled) return;
		if (editing === lastUrlEditing) return;
		lastUrlEditing = editing;
		updateEditQuery(editing);
	});

	let editSections: EditSectionMenuItem[] = $derived(
		DISPLAY_TYPE_EDIT_SECTIONS.map((section) =>
			isMobile
				? {
						key: section.key,
						label: section.label,
						href: resolve(`/display-types/${slug}/edit/${section.segment}`)
					}
				: {
						key: section.key,
						label: section.label,
						onclick: () => (editing = section.key)
					}
		)
	);
</script>

<MetaTags title={profile.name} description={metaDescription} url={page.url.href} />

{#if isEdit}
	{@render children()}
{:else}
	{#snippet actionBar()}
		<PageActionBar
			detailHref={isDetail ? undefined : resolve(`/display-types/${slug}`)}
			editSections={auth.isAuthenticated ? editSections : undefined}
			historyHref={resolve(`/display-types/${slug}/edit-history`)}
			sourcesHref={resolve(`/display-types/${slug}/sources`)}
		/>
	{/snippet}

	{#snippet main()}
		{@render children()}
	{/snippet}

	<RecordDetailShell
		name={profile.name}
		parentLink={{ text: 'Display Types', href: resolve('/display-types') }}
		{actionBar}
		{main}
	/>

	<SectionEditorHost
		bind:editingKey={editing}
		sections={DISPLAY_TYPE_EDIT_SECTIONS.map((section) => ({
			...section,
			usesSectionEditorForm: true
		}))}
		switcherItems={editSections}
	>
		{#snippet editor(key, { ref, onsaved, onerror, ondirtychange })}
			<DisplayTypeEditorSwitch
				sectionKey={key}
				initialData={profile}
				slug={profile.slug}
				bind:editorRef={ref.current}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{/snippet}
	</SectionEditorHost>
{/if}
