<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';
  import SiteShell from '$lib/components/SiteShell.svelte';
  import FocusSiteShell from '$lib/components/FocusSiteShell.svelte';
  import ToastHost from '$lib/toast/ToastHost.svelte';
  import { isFocusModePath } from '$lib/focus-mode';
  import { isKioskCookieSet } from '$lib/kiosk/config';
  import { onMount } from 'svelte';

  let { children } = $props();

  let isFocusMode = $derived(isFocusModePath(page.url.pathname));

  // Cookie is checked client-side so the kiosk path doesn't pollute every
  // page's load type. KioskMode itself is client-only (window event listeners).
  let isKiosk = $state(false);
  onMount(() => {
    isKiosk = isKioskCookieSet();
  });
</script>

<div class="app-root">
  {#if isFocusMode}
    <FocusSiteShell>
      {@render children()}
    </FocusSiteShell>
  {:else}
    <SiteShell>
      {@render children()}
    </SiteShell>
  {/if}

  <ToastHost />

  {#if isKiosk}
    {#await import('$lib/kiosk/KioskMode.svelte') then m}
      <m.default />
    {/await}
  {/if}
</div>

<style>
  .app-root {
    display: flex;
    flex-direction: column;
    min-height: 100dvh;
  }
</style>
