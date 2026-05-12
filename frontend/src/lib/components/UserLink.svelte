<script lang="ts">
  import { resolveHref } from '$lib/utils';

  let {
    username,
    displayName,
  }: {
    username: string | null | undefined;
    displayName: string | null | undefined;
  } = $props();
</script>

{#if username}
  <a href={resolveHref(`/users/${username}`)}>{displayName || username}</a>
{:else}
  <span class="system">system</span>
{/if}

<style>
  .system {
    color: var(--color-text-muted);
  }
</style>
