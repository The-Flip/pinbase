<script lang="ts">
	import { untrack } from 'svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import { fetchFieldConstraints, fc, type FieldConstraints } from '$lib/field-constraints';
	import { diffScalarFields } from '$lib/edit-helpers';
	import {
		EMPTY_EDIT_OPTIONS,
		fetchModelEditOptions,
		type ModelEditOptions
	} from './model-edit-options';
	import { saveModelClaims, type SaveResult, type SaveMeta } from './save-model-claims';

	const TECHNOLOGY_FIELDS = [
		{
			field: 'technology_generation',
			optionsKey: 'technology_generations',
			label: 'Technology generation'
		},
		{
			field: 'technology_subgeneration',
			optionsKey: 'technology_subgenerations',
			label: 'Technology subgeneration'
		},
		{ field: 'display_type', optionsKey: 'display_types', label: 'Display type' },
		{ field: 'display_subtype', optionsKey: 'display_subtypes', label: 'Display subtype' },
		{ field: 'system', optionsKey: 'systems', label: 'System' }
	] as const;

	const MACHINE_FK_FIELDS = [
		{ field: 'cabinet', optionsKey: 'cabinets', label: 'Cabinet' },
		{ field: 'game_format', optionsKey: 'game_formats', label: 'Game format' }
	] as const;

	type SpecsModel = {
		technology_generation?: { slug: string } | null;
		technology_subgeneration?: { slug: string } | null;
		system?: { slug: string } | null;
		display_type?: { slug: string } | null;
		display_subtype?: { slug: string } | null;
		cabinet?: { slug: string } | null;
		game_format?: { slug: string } | null;
		player_count?: number | null;
		flipper_count?: number | null;
		production_quantity: string;
	};

	let {
		initialModel,
		slug,
		onsaved,
		onerror
	}: {
		initialModel: SpecsModel;
		slug: string;
		onsaved: () => void;
		onerror: (message: string) => void;
	} = $props();

	type SpecFormFields = {
		technology_generation: string;
		technology_subgeneration: string;
		system: string;
		display_type: string;
		display_subtype: string;
		cabinet: string;
		game_format: string;
		player_count: string | number;
		flipper_count: string | number;
		production_quantity: string | number;
	};

	function extractFields(m: SpecsModel): SpecFormFields {
		return {
			technology_generation: m.technology_generation?.slug ?? '',
			technology_subgeneration: m.technology_subgeneration?.slug ?? '',
			system: m.system?.slug ?? '',
			display_type: m.display_type?.slug ?? '',
			display_subtype: m.display_subtype?.slug ?? '',
			cabinet: m.cabinet?.slug ?? '',
			game_format: m.game_format?.slug ?? '',
			player_count: m.player_count ?? '',
			flipper_count: m.flipper_count ?? '',
			production_quantity: m.production_quantity ?? ''
		};
	}

	// untrack: intentional one-time capture; component re-mounts when modal reopens
	const original = untrack(() => extractFields(initialModel));
	let fields = $state<SpecFormFields>({ ...original });

	let editOptions = $state<ModelEditOptions>(EMPTY_EDIT_OPTIONS);
	let constraints = $state<FieldConstraints>({});

	$effect(() => {
		fetchFieldConstraints('model').then((c) => {
			constraints = c;
		});
	});

	$effect(() => {
		fetchModelEditOptions().then((opts) => {
			editOptions = opts;
		});
	});

	export async function save(meta?: SaveMeta): Promise<void> {
		const changed = diffScalarFields(fields, original);

		if (Object.keys(changed).length === 0) {
			onsaved();
			return;
		}

		const result: SaveResult = await saveModelClaims(slug, {
			fields: changed,
			...meta
		});

		if (result.ok) {
			onsaved();
		} else {
			onerror(result.error);
		}
	}
</script>

<div class="specs-editor">
	<fieldset class="field-group">
		<legend>Technology</legend>
		<div class="specs-grid">
			{#each TECHNOLOGY_FIELDS as fk (fk.field)}
				<SearchableSelect
					label={fk.label}
					options={editOptions[fk.optionsKey] ?? []}
					bind:selected={fields[fk.field]}
					allowZeroCount
					showCounts={false}
					placeholder="Search {fk.label.toLowerCase()}..."
				/>
			{/each}
		</div>
	</fieldset>

	<fieldset class="field-group">
		<legend>Machine Facts</legend>
		<div class="specs-grid">
			<NumberField
				label="Players"
				bind:value={fields.player_count}
				{...fc(constraints, 'player_count')}
			/>
			<NumberField
				label="Flippers"
				bind:value={fields.flipper_count}
				{...fc(constraints, 'flipper_count')}
			/>
			{#each MACHINE_FK_FIELDS as fk (fk.field)}
				<SearchableSelect
					label={fk.label}
					options={editOptions[fk.optionsKey] ?? []}
					bind:selected={fields[fk.field]}
					allowZeroCount
					showCounts={false}
					placeholder="Search {fk.label.toLowerCase()}..."
				/>
			{/each}
			<NumberField label="Production quantity" bind:value={fields.production_quantity} min={0} />
		</div>
	</fieldset>
</div>

<style>
	.specs-editor {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}

	.field-group {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-3);
		margin: 0;
	}

	.field-group > legend {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		padding: 0 var(--size-1);
	}

	.specs-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: var(--size-3);
	}
</style>
