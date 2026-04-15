---
name: core-theme
description: Understanding theme variables, design tokens, and customizing Tailwind's default theme
---

# Theme Variables

Theme variables are special CSS variables defined using the `@theme` directive that influence which utility classes exist in your project.

## Overview

Theme variables store design tokens like colors, fonts, spacing, shadows, and breakpoints. They're defined using the `@theme` directive:

```css
@import "tailwindcss";

@theme {
  --color-mint-500: oklch(0.72 0.11 178);
  --font-display: "Satoshi", "sans-serif";
  --breakpoint-3xl: 120rem;
}
```

Now utilities like `bg-mint-500`, `font-display`, and `3xl:grid-cols-6` become available.

## Why @theme Instead of :root?

Theme variables aren't just CSS variables - they also instruct Tailwind to create new utility classes. Using `@theme` makes this explicit and ensures variables are defined top-level.

Use `@theme` for design tokens that map to utilities. Use `:root` for regular CSS variables that shouldn't have corresponding utilities.

## Theme Variable Namespaces

Theme variables are organized into namespaces that map to utility classes:

| Namespace | Utility Classes |
|-----------|----------------|
| `--color-*` | `bg-red-500`, `text-sky-300`, `border-indigo-600`, etc. |
| `--font-*` | `font-sans`, `font-serif`, `font-mono` |
| `--breakpoint-*` | Responsive variants like `md:`, `lg:`, `xl:` |
| `--spacing-*` | Spacing scale for padding, margin, gap utilities |
| `--shadow-*` | `shadow-sm`, `shadow-md`, `shadow-lg` |
| `--ease-*` | Transition timing functions |

## Extending the Default Theme

Add new theme variables to extend the default theme:

```css
@import "tailwindcss";

@theme {
  /* Add new color */
  --color-brand-500: oklch(0.65 0.2 250);
  
  /* Add new breakpoint */
  --breakpoint-3xl: 120rem;
  
  /* Add new font */
  --font-display: "Satoshi", "sans-serif";
}
```

## Using Theme Variables

Tailwind generates CSS variables for your theme variables, so you can reference them:

```html
<!-- Use utility classes -->
<div class="bg-brand-500 text-display">Content</div>

<!-- Reference CSS variables directly -->
<div style="background-color: var(--color-brand-500)">
  Content
</div>
```

## Default Theme

When you import `tailwindcss`, it includes default theme variables:

```css
@layer theme, base, components, utilities;

@import "./theme.css" layer(theme);
@import "./preflight.css" layer(base);
@import "./utilities.css" layer(utilities);
```

The default theme includes:
- Color palette (red, blue, green, etc. with 50-950 shades)
- Font families (sans, serif, mono)
- Spacing scale
- Shadows
- Breakpoints (sm, md, lg, xl, 2xl)

## Key Points

- Theme variables define which utilities exist in your project
- Use `@theme` directive to define design tokens
- Variables must be defined top-level, not nested
- Tailwind generates both utilities and CSS variables
- Default theme provides a solid starting point

<!--
Source references:
- https://tailwindcss.com/docs/theme
-->
