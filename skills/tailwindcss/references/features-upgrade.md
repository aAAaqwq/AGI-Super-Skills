---
name: features-upgrade
description: Migrating from Tailwind CSS v3 to v4
---

# Upgrade Guide (v3 → v4)

Key changes when upgrading from Tailwind CSS v3 to v4. Use the automated upgrade tool when possible.

## Upgrade Tool

```bash
npx @tailwindcss/upgrade
```

Requires Node.js 20+. Run in a new branch, review diff, test. Handles most migration automatically.

## Installation Changes

- **PostCSS**: Use `@tailwindcss/postcss`; remove `postcss-import` and `autoprefixer` (handled by v4)
- **Vite**: Prefer `@tailwindcss/vite` over PostCSS
- **CLI**: Use `npx @tailwindcss/cli` instead of `npx tailwindcss`

## Import Change

```css
/* v3 */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* v4 */
@import "tailwindcss";
```

## Renamed Utilities

| v3 | v4 |
|----|-----|
| `shadow-sm` | `shadow-xs` |
| `shadow` | `shadow-sm` |
| `rounded-sm` | `rounded-xs` |
| `rounded` | `rounded-sm` |
| `blur-sm` | `blur-xs` |
| `blur` | `blur-sm` |
| `outline-none` | `outline-hidden` |
| `ring` | `ring-3` |

## Removed / Replaced

- `bg-opacity-*`, `text-opacity-*`, etc. → use `bg-black/50`, `text-black/50`
- `flex-shrink-*` → `shrink-*`
- `flex-grow-*` → `grow-*`
- `overflow-ellipsis` → `text-ellipsis`

## Important Modifier

```html
<!-- v3: ! at start -->
<div class="!bg-red-500">

<!-- v4: ! at end -->
<div class="bg-red-500!">
```

## Ring & Border Defaults

- `ring` width: 3px → 1px; use `ring-3` for v3 behavior
- `ring` / `border` default color: `currentColor` (was gray-200 / blue-500)
- Always specify color: `ring-3 ring-blue-500`, `border border-gray-200`

## Other Breaking Changes

- **Space/divide selectors**: Changed from `:not([hidden]) ~ :not([hidden])` to `:not(:last-child)`; may affect layout
- **Variant stacking**: Left-to-right in v4 (was right-to-left)
- **Transform reset**: `transform-none` no longer resets rotate/scale/translate; use `scale-none`, `rotate-none`, etc.
- **Hover on mobile**: `hover` only applies when device supports hover; override with `@custom-variant hover (&:hover)` if needed
- **Arbitrary values**: Use `bg-(--var)` not `bg-[--var]` for CSS variables
- **theme()**: Use `theme(--breakpoint-xl)` not `theme(screens.xl)`
- **@layer utilities/components**: Use `@utility` directive instead
- **corePlugins, safelist, separator**: Not supported; use `@source inline()` for safelisting
- **Sass/Less/Stylus**: v4 not designed for use with CSS preprocessors

## Browser Support

v4 targets Safari 16.4+, Chrome 111+, Firefox 128+. For older browsers, stay on v3.4.

<!--
Source references:
- https://tailwindcss.com/docs/upgrade-guide
-->
