// Shared responsive breakpoints (rem). Plain JS so `svelte.config.js`
// (which Node loads directly, before any TS toolchain) can import them
// alongside `lib/constants.ts`. Single source of truth for both JS hooks
// and the CSS `@custom-media` declarations injected by svelte.config.js.
// See also: app.css (where the named breakpoints are documented for
// component <style> consumers).

export const NARROW_BREAKPOINT = 40;
export const WIDE_BREAKPOINT = 52;
