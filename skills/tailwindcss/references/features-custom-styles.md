---
name: features-custom-styles
description: Adding custom styles, utilities, variants, and working with arbitrary values
---

# Adding Custom Styles

Tailwind is designed to be extensible. This guide covers customizing your theme, using arbitrary values, adding custom CSS, and extending the framework.

## Customizing Your Theme

Add custom design tokens using `@theme`:

```css
@import "tailwindcss";

@theme {
  --font-display: "Satoshi", "sans-serif";
  --breakpoint-3xl: 120rem;
  --color-brand-500: oklch(0.65 0.2 250);
  --ease-fluid: cubic-bezier(0.3, 0, 0, 1);
}
```

## Arbitrary Values

Use square bracket notation for one-off values that don't belong in your theme:

```html
<!-- Arbitrary values -->
<div class="top-[117px] bg-[#bada55] text-[22px]">
  Content
</div>

<!-- With variants -->
<div class="top-[117px] lg:top-[344px]">
  Content
</div>
```

### CSS Variables as Arbitrary Values

Reference CSS variables:

```html
<div class="fill-(--my-brand-color)">
  Content
</div>
```

This is shorthand for `fill-[var(--my-brand-color)]`.

## Arbitrary Properties

Use square brackets for CSS properties Tailwind doesn't have utilities for:

```html
<div class="[mask-type:luminance]">
  Content
</div>

<!-- With variants -->
<div class="[mask-type:luminance] hover:[mask-type:alpha]">
  Content
</div>
```

### CSS Variables

Set CSS variables with arbitrary properties:

```html
<div class="[--scroll-offset:56px] lg:[--scroll-offset:44px]">
  Content
</div>
```

## Arbitrary Variants

Create custom selectors on the fly:

```html
<ul>
  <li class="lg:[&:nth-child(-n+3)]:hover:underline">Item</li>
</ul>
```

## Handling Whitespace

Use underscores for spaces in arbitrary values:

```html
<div class="grid-cols-[1fr_500px_2fr]">
  Content
</div>
```

Tailwind converts underscores to spaces, except in contexts where underscores are valid (like URLs).

## Custom Utilities

Add custom utilities with `@utility`:

```css
@import "tailwindcss";

@utility tab-4 {
  tab-size: 4;
}
```

Now you can use `tab-4` utility class, and it works with variants:

```html
<div class="tab-4 hover:tab-8">
  Content
</div>
```

## Custom Variants

Add custom variants with `@custom-variant`:

```css
@import "tailwindcss";

@custom-variant theme-midnight (&:where([data-theme="midnight"] *));
```

Now you can use `theme-midnight:` variant:

```html
<div class="theme-midnight:bg-black theme-midnight:text-white">
  Content
</div>
```

## Using Variants in CSS

Apply Tailwind variants to custom CSS with `@variant`:

```css
.my-element {
  background: white;
  
  @variant dark {
    background: black;
  }
  
  @variant hover {
    background: gray;
  }
}
```

## Base Styles

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

## Component Styles

Add component styles to the `components` layer:

```css
@layer components {
  .btn-primary {
    @apply bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded;
  }
}
```

## Key Points

- Use `@theme` to customize design tokens
- Arbitrary values with `[]` for one-off values
- Arbitrary properties for CSS properties without utilities
- `@utility` for custom utilities
- `@custom-variant` for custom variants
- `@layer` for organizing base and component styles

<!--
Source references:
- https://tailwindcss.com/docs/adding-custom-styles
-->
