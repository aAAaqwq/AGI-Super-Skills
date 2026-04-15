---
name: typography-list-style
description: Controlling list marker style and position with list-style-type and list-style-position
---

# List Style

Utilities for controlling the marker style and position of list items.

## Usage

### List style type

```html
<ul class="list-disc">
  <li>Disc bullets (default for ul)</li>
</ul>

<ol class="list-decimal">
  <li>Decimal numbers (default for ol)</li>
</ol>

<ul class="list-none">
  <li>No markers (often with custom bullets via before/after)</li>
</ul>

<!-- Custom value -->
<ol class="list-[upper-roman]">Roman numerals</ol>
<ul class="list-(--my-marker)">Custom property</ul>
```

### List style position

```html
<!-- Bullets inside content flow -->
<ul class="list-inside list-disc">
  <li>5 cups chopped Porcini mushrooms</li>
</ul>

<!-- Bullets outside content flow (default) -->
<ul class="list-outside list-disc">
  <li>5 cups chopped Porcini mushrooms</li>
</ul>
```

### Responsive

```html
<ul class="list-none md:list-disc md:list-outside">...</ul>
```

## Key Points

- `list-disc` - disc bullets (ul default)
- `list-decimal` - decimal numbers (ol default)
- `list-none` - no markers
- Custom: `list-[upper-roman]`, `list-[lower-alpha]`, `list-(--var)`
- `list-inside` - markers inside content box
- `list-outside` - markers outside content box (default)

<!--
Source references:
- https://tailwindcss.com/docs/list-style-type
- https://tailwindcss.com/docs/list-style-position
-->
