<script lang="ts">
  import type { ClaimAttributionSchema } from '$lib/api/schema';
  import UserLink from './UserLink.svelte';

  let { attribution }: { attribution: ClaimAttributionSchema } = $props();
</script>

{#if attribution.source_name}
  <span class="source-badge">{attribution.source_name}</span>
{:else if attribution.user_username}
  <UserLink username={attribution.user_username} />
{:else}
  system
{/if}

<style>
  .source-badge {
    display: inline-block;
    padding: 1px var(--size-2);
    font-size: var(--font-size-00, 0.7rem);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-radius: var(--radius-1);
    background-color: var(--color-surface);
    border: 1px solid var(--color-border-soft);
    color: var(--color-text-muted);
  }
</style>
