---
name: core-preflight
description: Understanding Tailwind's Preflight base styles and how to extend or disable them
---

# Preflight

Preflight is Tailwind's opinionated set of base styles that smooth over cross-browser inconsistencies.

## Overview

Built on top of modern-normalize, Preflight is automatically injected when you import `tailwindcss`:

```css
@layer theme, base, components, utilities;

@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/preflight.css" layer(base);
@import "tailwindcss/utilities.css" layer(utilities);
```

## Key Resets

### Margins Removed

All default margins are removed from headings, paragraphs, blockquotes, etc:

```css
*,
::after,
::before {
  margin: 0;
  padding: 0;
}
```

This prevents accidentally relying on browser default margins that aren't part of your spacing scale.

### Border Styles Reset

Borders are reset to make adding borders easier:

```css
*,
::after,
::before {
  box-sizing: border-box;
  border: 0 solid;
}
```

Since the `border` utility only sets `border-width`, this ensures adding `border` always creates a solid `1px` border using `currentColor`.

### Headings Unstyled

All headings are unstyled by default:

```css
h1, h2, h3, h4, h5, h6 {
  font-size: inherit;
  font-weight: inherit;
}
```

**Reasons:**
- Avoids deviating from your type scale
- In UI development, headings should often be visually de-emphasized

### Lists Unstyled

Ordered and unordered lists have no bullets or numbers:

```css
ol, ul, menu {
  list-style: none;
}
```

Style lists using utilities:

```html
<ul class="list-inside list-disc">
  <li>One</li>
  <li>Two</li>
</ul>
```

**Accessibility:** Add `role="list"` for screen readers when keeping lists unstyled:

```html
<ul role="list">
  <li>One</li>
  <li>Two</li>
</ul>
```

### Images Are Block-Level

Images and replaced elements are `display: block`:

```css
img, svg, video, canvas, audio, iframe, embed, object {
  display: block;
  vertical-align: middle;
}
```

Use `inline` utility if needed:

```html
<img class="inline" src="..." alt="..." />
```

### Images Are Constrained

Images and videos are constrained to parent width:

```css
img, video {
  max-width: 100%;
  height: auto;
}
```

Override with `max-w-none`:

```html
<img class="max-w-none" src="..." alt="..." />
```

### Hidden Attribute

Elements with `hidden` attribute stay hidden:

```css
[hidden]:where(:not([hidden="until-found"])) {
  display: none !important;
}
```

## Extending Preflight

Add base styles to the `base` layer:

```css
@layer base {
  h1 {
    font-size: var(--text-2xl);
    font-weight: 600;
  }
  
  h2 {
    font-size: var(--text-xl);
    font-weight: 600;
  }
  
  a {
    color: var(--color-blue-600);
    text-decoration-line: underline;
  }
}
```

## Disabling Preflight

Import Tailwind components individually, omitting Preflight:

```css
@layer theme, base, components, utilities;

@import "tailwindcss/theme.css" layer(theme);
/* @import "tailwindcss/preflight.css" layer(base); */ /* Omitted */
@import "tailwindcss/utilities.css" layer(utilities);
```

## Working Around Third-Party Libraries

Some libraries may conflict with Preflight. Override Preflight styles:

```css
@layer base {
  .google-map * {
    border-style: none;
  }
}
```

## Key Points

- Preflight normalizes cross-browser inconsistencies
- Margins, borders, headings, and lists are reset
- Images are block-level and constrained by default
- Extend Preflight with `@layer base`
- Disable by omitting the preflight import
- Override Preflight styles when needed for third-party libraries

<!--
Source references:
- https://tailwindcss.com/docs/preflight
-->
