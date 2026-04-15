---
name: layout-columns
description: Multi-column layout with columns utility for masonry-like or newspaper layouts
---

# Columns

Utilities for CSS multi-column layout. Content flows into multiple columns within a single element.

## Usage

### By number of columns

```html
<div class="columns-3 gap-8">
  <img class="aspect-3/2" src="1.jpg" />
  <img class="aspect-square" src="2.jpg" />
  <!-- Content flows into 3 columns -->
</div>
```

### By column width

Use container scale for ideal column width; column count adjusts automatically:

```html
<div class="columns-3xs gap-4">...</div>
<div class="columns-sm gap-6">...</div>
<div class="columns-md">...</div>
```

### Column gap

Use `gap-*` utilities for space between columns:

```html
<div class="columns-3 gap-8">...</div>
```

### Responsive

```html
<div class="columns-2 gap-4 sm:columns-3 sm:gap-8">...</div>
```

### Custom value

```html
<div class="columns-[30vw]">...</div>
<div class="columns-(--my-columns)">...</div>
```

### Column / page breaks

Use with multi-column or print layouts:

```html
<div class="columns-2">
  <p>Content...</p>
  <p class="break-after-column">Force break after this</p>
  <p>Next column...</p>
</div>
```

- `break-after-column` / `break-before-column` - column break
- `break-after-page` / `break-before-page` - page break (print)
- `break-after-avoid` / `break-inside-avoid` - avoid breaking

## Key Points

- `columns-<n>` - fixed number of columns (e.g. `columns-3`)
- `columns-3xs` through `columns-7xl` - column width from container scale
- `columns-auto` - auto columns
- `gap-*` controls column gap (same as flex/grid gap)
- Use for magazine-style layouts, image galleries, long text

<!--
Source references:
- https://tailwindcss.com/docs/columns
-->
