<script lang="ts">
	import type { components } from '$lib/api/schema';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import type { ModelEditSectionKey } from '$lib/components/editors/model-edit-sections';
	import BasicsEditor from '$lib/components/editors/BasicsEditor.svelte';
	import ExternalDataEditor from '$lib/components/editors/ExternalDataEditor.svelte';
	import FeaturesEditor from '$lib/components/editors/FeaturesEditor.svelte';
	import OverviewEditor from '$lib/components/editors/OverviewEditor.svelte';
	import PeopleEditor from '$lib/components/editors/PeopleEditor.svelte';
	import RelatedModelsEditor from '$lib/components/editors/RelatedModelsEditor.svelte';
	import TechnologyEditor from '$lib/components/editors/TechnologyEditor.svelte';

	type ModelDetail = components['schemas']['MachineModelDetailSchema'];

	let {
		sectionKey,
		initialData,
		slug,
		slim = false,
		editorRef = $bindable<SectionEditorHandle | undefined>(undefined),
		onsaved,
		onerror,
		ondirtychange
	}: {
		sectionKey: ModelEditSectionKey;
		initialData: ModelDetail;
		slug: string;
		slim?: boolean;
		editorRef?: SectionEditorHandle | undefined;
		onsaved: () => void;
		onerror: (message: string) => void;
		ondirtychange: (dirty: boolean) => void;
	} = $props();
</script>

{#if sectionKey === 'basics'}
	<BasicsEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{slim}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'overview'}
	<OverviewEditor
		bind:this={editorRef}
		initialData={initialData.description?.text ?? ''}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'technology'}
	<TechnologyEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'features'}
	<FeaturesEditor bind:this={editorRef} {initialData} {slug} {onsaved} {onerror} {ondirtychange} />
{:else if sectionKey === 'people'}
	<PeopleEditor
		bind:this={editorRef}
		initialData={initialData.credits}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'related-models'}
	<RelatedModelsEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'external-data'}
	<ExternalDataEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{/if}
