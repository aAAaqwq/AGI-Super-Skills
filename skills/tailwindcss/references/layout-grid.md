---
name: layout-grid
description: CSS Grid utilities including grid-cols, grid-rows, gap, place-items, and grid placement
---

# Grid

Utilities for CSS Grid layouts: columns, rows, gap, and item placement.

## Usage

### Grid columns and rows

```html
<div class="grid grid-cols-3 gap-4">3 equal columns</div>
<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">Responsive</div>
<div class="grid grid-cols-none">No explicit tracks</div>

<div class="grid grid-rows-3 gap-2">3 rows</div>
<div class="grid grid-rows-[auto_1fr_auto]">Custom rows</div>
```

### Custom grid template

```html
<div class="grid grid-cols-[200px_minmax(900px,1fr)_100px]">Custom template</div>
<div class="grid grid-cols-(--my-cols)">CSS variable</div>
```

### Subgrid

```html
<div class="grid grid-cols-4 gap-4">
  <div>01</div><div>02</div><div>03</div><div>04</div>
  <div>05</div>
  <div class="col-span-3 grid grid-cols-subgrid gap-4">
    <div class="col-start-2">06</div>
  </div>
</div>
```

### Gap

```html
<div class="grid gap-4">Uniform gap</div>
<div class="grid gap-x-2 gap-y-4">Different x/y</div>
```

### Place items (align + justify)

```html
<div class="grid place-items-center">Center both</div>
<div class="grid place-items-start">Start both</div>
<div class="grid items-center justify-center">Equivalent</div>
```

### Grid placement (col/row span and start)

```html
<div class="grid grid-cols-4 gap-4">
  <div class="col-span-2">Spans 2 columns</div>
  <div class="col-start-3">Starts at col 3</div>
  <div class="row-span-2">Spans 2 rows</div>
  <div class="col-span-full">Full width</div>
</div>
```

## Key Points

- `grid` / `inline-grid` - Grid container (see layout-display)
- Columns: `grid-cols-{n}`, `grid-cols-none`, `grid-cols-subgrid`, `grid-cols-[...]`
- Rows: `grid-rows-{n}`, `grid-rows-[...]`
- Gap: `gap-{n}`, `gap-x-{n}`, `gap-y-{n}`
- Placement: `col-span-{n}`, `col-start-{n}`, `row-span-{n}`, `row-start-{n}`
- `col-span-full` / `row-span-full` - span all
- `place-items-*` - shorthand for align + justify
- Use `grid-cols-[...]` for custom templates like `minmax()` or `repeat()`

<!--
Source references:
- https://tailwindcss.com/docs/grid-template-columns
- https://tailwindcss.com/docs/grid-template-rows
- https://tailwindcss.com/docs/gap
- https://tailwindcss.com/docs/place-items
- https://tailwindcss.com/docs/grid-column
- https://tailwindcss.com/docs/grid-row
-->
