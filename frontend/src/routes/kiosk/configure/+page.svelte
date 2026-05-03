<!--
  Kiosk configuration page. Staff use this to choose machines, edit hooks,
  reorder, and launch the kiosk. Configuration is saved to localStorage on
  the device.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import client from '$lib/api/client';
  import {
    clearKioskCookie,
    DEFAULT_IDLE_SECONDS,
    DEFAULT_TITLE,
    HOOK_MAX_LENGTH,
    isKioskCookieSet,
    loadConfig,
    saveConfig,
    setKioskCookie,
    type KioskConfig,
    type KioskItem,
  } from '$lib/kiosk/config';
  import { normalizeText } from '$lib/utils';
  import type { ModelGridItemSchema } from '$lib/api/schema';

  let title = $state(DEFAULT_TITLE);
  let idleSeconds = $state(DEFAULT_IDLE_SECONDS);
  let items = $state<KioskItem[]>([]);
  let allModels = $state<ModelGridItemSchema[]>([]);
  let search = $state('');
  let kioskActive = $state(false);
  let saved = $state(false);

  let configuredSlugs = $derived(new Set(items.map((i) => i.modelSlug)));

  let searchResults = $derived.by(() => {
    const q = normalizeText(search);
    if (!q) return [];
    return allModels
      .filter((m) => !configuredSlugs.has(m.slug))
      .filter((m) => normalizeText(m.search_text ?? m.name).includes(q))
      .slice(0, 12);
  });

  let modelBySlug = $derived(new Map(allModels.map((m) => [m.slug, m])));

  onMount(async () => {
    const existing = loadConfig();
    if (existing) {
      title = existing.title;
      idleSeconds = existing.idleSeconds;
      items = [...existing.items];
    }
    kioskActive = isKioskCookieSet();
    const res = await client.GET('/api/models/all/');
    if (res.data) allModels = res.data;
  });

  function addModel(slug: string) {
    items = [...items, { modelSlug: slug, hook: '' }];
    search = '';
    saved = false;
  }

  function removeAt(index: number) {
    items = items.filter((_, i) => i !== index);
    saved = false;
  }

  function moveUp(index: number) {
    if (index === 0) return;
    const next = [...items];
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    items = next;
    saved = false;
  }

  function moveDown(index: number) {
    if (index === items.length - 1) return;
    const next = [...items];
    [next[index + 1], next[index]] = [next[index], next[index + 1]];
    items = next;
    saved = false;
  }

  function buildConfig(): KioskConfig {
    return {
      title: title.trim() || DEFAULT_TITLE,
      idleSeconds: idleSeconds > 0 ? idleSeconds : DEFAULT_IDLE_SECONDS,
      items: items.map((i) => ({
        modelSlug: i.modelSlug,
        hook: i.hook.slice(0, HOOK_MAX_LENGTH),
      })),
    };
  }

  function handleSave() {
    saveConfig(buildConfig());
    saved = true;
  }

  async function handleLaunch() {
    saveConfig(buildConfig());
    setKioskCookie();
    await goto('/kiosk');
  }

  function handleExit() {
    clearKioskCookie();
    kioskActive = false;
  }
</script>

<svelte:head>
  <title>Configure Kiosk</title>
</svelte:head>

<div class="page">
  <header class="header">
    <h1>Configure Kiosk</h1>
    {#if kioskActive}
      <button type="button" class="exit-btn" onclick={handleExit}>Exit kiosk mode</button>
    {/if}
  </header>

  <section class="settings">
    <label>
      <span>Title</span>
      <input type="text" bind:value={title} maxlength="60" />
    </label>
    <label>
      <span>Idle timeout (seconds)</span>
      <input type="number" min="10" max="3600" bind:value={idleSeconds} />
    </label>
  </section>

  <section class="machines">
    <h2>Machines ({items.length})</h2>

    <label class="search">
      <span>Add a machine</span>
      <input type="search" placeholder="Search by name…" bind:value={search} autocomplete="off" />
    </label>

    {#if searchResults.length > 0}
      <ul class="results">
        {#each searchResults as model (model.slug)}
          <li>
            <button type="button" onclick={() => addModel(model.slug)}>
              <strong>{model.name}</strong>
              <span class="result-meta">
                {#if model.manufacturer_name}{model.manufacturer_name}{/if}
                {#if model.year}· {model.year}{/if}
              </span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    {#if items.length === 0}
      <p class="empty">No machines added yet.</p>
    {:else}
      <ol class="items">
        {#each items as item, i (item.modelSlug)}
          {@const model = modelBySlug.get(item.modelSlug)}
          <li class="item">
            <div class="item-header">
              <span class="item-name">
                {model?.name ?? item.modelSlug}
                {#if model?.year}<span class="dim"> · {model.year}</span>{/if}
                {#if model?.manufacturer_name}<span class="dim">
                    · {model.manufacturer_name}</span
                  >{/if}
              </span>
              <div class="item-actions">
                <button
                  type="button"
                  onclick={() => moveUp(i)}
                  disabled={i === 0}
                  aria-label="Move up">↑</button
                >
                <button
                  type="button"
                  onclick={() => moveDown(i)}
                  disabled={i === items.length - 1}
                  aria-label="Move down">↓</button
                >
                <button type="button" onclick={() => removeAt(i)} aria-label="Remove">✕</button>
              </div>
            </div>
            <input
              type="text"
              placeholder="Hook (optional, e.g. 'First talking pinball machine')"
              bind:value={item.hook}
              maxlength={HOOK_MAX_LENGTH}
              oninput={() => (saved = false)}
            />
          </li>
        {/each}
      </ol>
    {/if}
  </section>

  <footer class="actions">
    <button type="button" onclick={handleSave}>Save</button>
    <button type="button" class="primary" onclick={handleLaunch}>Launch kiosk</button>
    {#if saved}<span class="saved-hint">Saved.</span>{/if}
  </footer>
</div>

<style>
  .page {
    max-width: 60rem;
    margin: 0 auto;
    padding: var(--size-5) var(--size-4);
    display: flex;
    flex-direction: column;
    gap: var(--size-5);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header h1 {
    margin: 0;
  }

  .exit-btn {
    background: transparent;
    border: 1px solid var(--color-border-soft);
    padding: var(--size-2) var(--size-3);
    border-radius: var(--radius-2);
    cursor: pointer;
  }

  .settings {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--size-4);
  }

  label {
    display: flex;
    flex-direction: column;
    gap: var(--size-1);
    font-size: var(--font-size-1);
  }

  label > span {
    color: var(--color-text-muted);
  }

  input[type='text'],
  input[type='search'],
  input[type='number'] {
    padding: var(--size-2) var(--size-3);
    border: 1px solid var(--color-border-soft);
    border-radius: var(--radius-2);
    font-size: var(--font-size-1);
  }

  .machines h2 {
    margin: 0 0 var(--size-3);
  }

  .results {
    list-style: none;
    padding: 0;
    margin: var(--size-2) 0 0;
    border: 1px solid var(--color-border-soft);
    border-radius: var(--radius-2);
    max-height: 18rem;
    overflow-y: auto;
  }

  .results li {
    border-bottom: 1px solid var(--color-border-soft);
  }

  .results li:last-child {
    border-bottom: none;
  }

  .results button {
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    padding: var(--size-2) var(--size-3);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: var(--size-1);
  }

  .results button:hover {
    background: var(--color-surface-muted, #f0f0f0);
  }

  .result-meta {
    font-size: var(--font-size-0);
    color: var(--color-text-muted);
  }

  .items {
    list-style: none;
    padding: 0;
    margin: var(--size-3) 0 0;
    display: flex;
    flex-direction: column;
    gap: var(--size-3);
  }

  .item {
    display: flex;
    flex-direction: column;
    gap: var(--size-2);
    padding: var(--size-3);
    border: 1px solid var(--color-border-soft);
    border-radius: var(--radius-2);
  }

  .item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--size-2);
  }

  .item-name {
    font-weight: 600;
  }

  .dim {
    color: var(--color-text-muted);
    font-weight: 400;
  }

  .item-actions {
    display: flex;
    gap: var(--size-1);
  }

  .item-actions button {
    background: transparent;
    border: 1px solid var(--color-border-soft);
    border-radius: var(--radius-2);
    padding: var(--size-1) var(--size-2);
    cursor: pointer;
    min-width: 2rem;
  }

  .item-actions button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .empty {
    color: var(--color-text-muted);
    font-style: italic;
    margin-top: var(--size-3);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: var(--size-3);
    padding-top: var(--size-4);
    border-top: 1px solid var(--color-border-soft);
  }

  .actions button {
    padding: var(--size-2) var(--size-4);
    border-radius: var(--radius-2);
    border: 1px solid var(--color-border-soft);
    background: transparent;
    font-size: var(--font-size-1);
    cursor: pointer;
  }

  .actions button.primary {
    background: var(--color-accent);
    color: white;
    border-color: var(--color-accent);
    font-weight: 600;
  }

  .saved-hint {
    color: var(--color-text-muted);
    font-size: var(--font-size-0);
  }
</style>
