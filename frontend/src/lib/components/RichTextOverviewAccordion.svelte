<script lang="ts">
	import AccordionSection from '$lib/components/AccordionSection.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import type { InlineCitation } from '$lib/components/citation-tooltip';
	import type { RichTextAccordionState } from '$lib/components/rich-text-accordion-state.svelte';

	type RichTextValue = {
		text?: string;
		html?: string;
		citations?: InlineCitation[];
		attribution?: object | null;
	} | null;

	let {
		richText = null,
		state,
		heading = 'Overview',
		emptyText = 'No description yet.',
		open = true,
		onEdit = undefined
	}: {
		richText?: RichTextValue;
		state: RichTextAccordionState;
		heading?: string;
		emptyText?: string;
		open?: boolean;
		onEdit?: (() => void) | undefined;
	} = $props();
</script>

<AccordionSection {heading} {open} {onEdit}>
	{#if richText?.html}
		<div bind:this={state.descriptionContentEl}>
			<Markdown
				html={richText.html}
				citations={richText.citations ?? []}
				showReferences={false}
				onNavigateToRef={state.scrollToRefEntry}
			/>
			<AttributionLine attribution={richText.attribution} />
		</div>
	{:else}
		<p class="muted">{emptyText}</p>
	{/if}
</AccordionSection>

<style>
	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}
</style>
