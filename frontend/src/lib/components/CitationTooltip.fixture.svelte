<script lang="ts">
	import CitationTooltip from './CitationTooltip.svelte';

	let {
		html,
		htmlSignal = html
	}: {
		html: string;
		htmlSignal?: string;
	} = $props();

	let container: HTMLDivElement | undefined = $state();
</script>

<!-- eslint-disable-next-line svelte/no-at-html-tags -->
<div bind:this={container}>{@html html}</div>
<CitationTooltip {container} {htmlSignal} />
