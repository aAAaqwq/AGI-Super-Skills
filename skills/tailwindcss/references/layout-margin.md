---
name: layout-margin
description: Controlling element margins with spacing scale, negative values, logical properties, and space utilities
---

# Margin

Utilities for controlling an element's margin.

## Usage

### All sides

Use `m-<number>` to set margin on all sides:

```html
<div class="m-4">Margin on all sides</div>
<div class="m-8">Larger margin</div>
```

### Individual sides

Use `mt-<number>`, `mr-<number>`, `mb-<number>`, `ml-<number>`:

```html
<div class="mt-6">Top margin</div>
<div class="mr-4">Right margin</div>
<div class="mb-8">Bottom margin</div>
<div class="ml-2">Left margin</div>
```

### Horizontal and vertical

Use `mx-<number>` for horizontal, `my-<number>` for vertical:

```html
<div class="mx-8">Horizontal margin</div>
<div class="my-8">Vertical margin</div>
```

### Negative margins

Prefix with dash for negative values:

```html
<div class="-mt-8">Negative top margin</div>
<div class="-mx-4">Negative horizontal margin</div>
```

### Auto margins

Use `m-auto` or directional auto margins for centering:

```html
<div class="mx-auto">Centered horizontally</div>
<div class="ml-auto">Pushed to right</div>
```

### Logical properties

Use `ms-<number>` (margin-inline-start) and `me-<number>` (margin-inline-end) for RTL support:

```html
<div dir="ltr">
  <div class="ms-8">Left margin in LTR</div>
  <div class="me-8">Right margin in LTR</div>
</div>
<div dir="rtl">
  <div class="ms-8">Right margin in RTL</div>
  <div class="me-8">Left margin in RTL</div>
</div>
```

### Space between children

Use `space-x-<number>` or `space-y-<number>` to add margin between children:

```html
<div class="flex space-x-4">
  <div>01</div>
  <div>02</div>
  <div>03</div>
</div>

<div class="flex flex-col space-y-8">
  <div>01</div>
  <div>02</div>
  <div>03</div>
</div>
```

### Reversing space

Use `space-x-reverse` or `space-y-reverse` with reversed flex directions:

```html
<div class="flex flex-row-reverse space-x-4 space-x-reverse">
  <div>01</div>
  <div>02</div>
  <div>03</div>
</div>
```

### Custom values

Use arbitrary values for custom margins:

```html
<div class="m-[5px]">Custom margin</div>
<div class="mx-[calc(50%-1rem)]">Custom calculation</div>
```

## Key Points

- Spacing scale: `m-0` through `m-96` (and beyond)
- Negative: prefix with dash (`-m-4`, `-mt-8`, `-mx-4`)
- Auto: `m-auto`, `mx-auto`, `my-auto`, `mt-auto`, etc.
- Logical: `ms-*` (start), `me-*` (end) adapt to text direction
- Space utilities: `space-x-*`, `space-y-*` add margin to all children except last
- Space reverse: `space-x-reverse`, `space-y-reverse` for reversed flex layouts
- Limitations: Space utilities don't work well with grids or complex layouts - use `gap` utilities instead

<!--
Source references:
- https://tailwindcss.com/docs/margin
-->
