<!--
  Invisible kiosk-mode shell. Loaded only when the `mode=kiosk` cookie is set
  (see root +layout.svelte). Watches for visitor inactivity and navigates back
  to /kiosk after the configured idle timeout. Renders no visible UI — the
  rest of the site is unmodified for kiosk visitors.
-->
<script lang="ts">
  import { goto } from '$app/navigation';
  import { DEFAULT_IDLE_SECONDS, loadConfig } from './config';

  $effect(() => {
    const idleSeconds = loadConfig()?.idleSeconds ?? DEFAULT_IDLE_SECONDS;
    const idleMs = idleSeconds * 1000;

    let timer: ReturnType<typeof setTimeout> | undefined;

    function reset() {
      if (timer !== undefined) clearTimeout(timer);
      timer = setTimeout(() => {
        void goto('/kiosk', { invalidateAll: true, replaceState: true });
      }, idleMs);
    }

    const events = ['pointerdown', 'keydown', 'touchstart'] as const;
    for (const ev of events) {
      window.addEventListener(ev, reset, { passive: true });
    }
    reset();

    return () => {
      if (timer !== undefined) clearTimeout(timer);
      for (const ev of events) {
        window.removeEventListener(ev, reset);
      }
    };
  });
</script>
