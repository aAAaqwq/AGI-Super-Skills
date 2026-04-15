---
name: features-functions-directives
description: Tailwind's CSS directives (@import, @theme, @utility, @variant) and functions (--alpha, --spacing)
---

# Functions and Directives

Tailwind provides custom CSS directives and functions for working with your design system.

## Directives

Directives are custom Tailwind-specific at-rules that offer special functionality.

### @import

Import CSS files, including Tailwind:

```css
@import "tailwindcss";
```

### @theme

Define your project's design tokens:

```css
@theme {
  --font-display: "Satoshi", "sans-serif";
  --breakpoint-3xl: 120rem;
  --color-brand-500: oklch(0.65 0.2 250);
  --ease-fluid: cubic-bezier(0.3, 0, 0, 1);
}
```

### @source

Explicitly specify source files for class detection:

```css
@import "tailwindcss";
@source "../node_modules/@my-company/ui-lib";
```

### @utility

Add custom utilities:

```css
@utility tab-4 {
  tab-size: 4;
}
```

Custom utilities work with variants:

```html
<div class="tab-4 hover:tab-8">Content</div>
```

### @variant

Apply Tailwind variants to styles in your CSS:

```css
.my-element {
  background: white;
  
  @variant dark {
    background: black;
  }
}
```

### @custom-variant

Add custom variants:

```css
@custom-variant theme-midnight (&:where([data-theme="midnight"] *));
```

```html
<div class="theme-midnight:bg-black">Content</div>
```

### @apply

Inline existing utility classes into custom CSS:

```css
.select2-dropdown {
  @apply rounded-b-lg shadow-md;
}

.select2-search {
  @apply rounded border border-gray-300;
}
```

### @reference

Import stylesheet for reference without including styles (useful for Vue/Svelte components):

```html
<style>
  @reference "../../app.css";
  
  h1 {
    @apply text-2xl font-bold text-red-500;
  }
</style>
```

Or reference Tailwind directly:

```html
<style>
  @reference "tailwindcss";
  
  h1 {
    @apply text-2xl font-bold;
  }
</style>
```

### Subpath Imports

Directives support subpath imports (like TypeScript path aliases):

```json
{
  "imports": {
    "#app.css": "./src/css/app.css"
  }
}
```

```html
<style>
  @reference "#app.css";
  
  h1 {
    @apply text-2xl font-bold;
  }
</style>
```

## Functions

Tailwind provides build-time functions for working with colors and spacing.

### --alpha()

Adjust the opacity of a color:

```css
.my-element {
  color: --alpha(var(--color-lime-300) / 50%);
}
```

Compiles to:

```css
.my-element {
  color: color-mix(in oklab, var(--color-lime-300) 50%, transparent);
}
```

### --spacing()

Generate spacing values based on your theme:

```css
.my-element {
  margin: --spacing(4);
}
```

Compiles to:

```css
.my-element {
  margin: calc(var(--spacing) * 4);
}
```

Useful in arbitrary values with `calc()`:

```html
<div class="py-[calc(--spacing(4)-1px)]">
  Content
</div>
```

## Compatibility Directives

For compatibility with Tailwind CSS v3.x:

### @config

Load a legacy JavaScript-based configuration:

```css
@config "../../tailwind.config.js";
```

### @plugin

Load a legacy JavaScript-based plugin:

```css
@plugin "@tailwindcss/typography";
```

### theme()

Access theme values using dot notation (deprecated):

```css
.my-element {
  margin: theme(spacing.12);
}
```

**Note:** Prefer using CSS theme variables instead.

## Key Points

- Directives are Tailwind-specific at-rules
- `@theme` defines design tokens
- `@utility` creates custom utilities
- `@custom-variant` creates custom variants
- `@apply` inlines utilities into CSS
- `--alpha()` and `--spacing()` are build-time functions
- Compatibility directives support v3.x configs

<!--
Source references:
- https://tailwindcss.com/docs/functions-and-directives
-->
