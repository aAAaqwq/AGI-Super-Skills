---
name: layout-tables
description: Table layout and border behavior with border-collapse, table-layout
---

# Table Layout

Utilities for controlling table display, border behavior, and layout algorithm.

## Usage

### Border collapse

```html
<!-- Collapsed: adjacent borders merge into single border -->
<table class="border-collapse border border-gray-400">
  <thead>
    <tr>
      <th class="border border-gray-300 p-2">State</th>
      <th class="border border-gray-300 p-2">City</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td class="border border-gray-300 p-2">Indiana</td>
      <td class="border border-gray-300 p-2">Indianapolis</td>
    </tr>
  </tbody>
</table>

<!-- Separate: each cell has its own borders -->
<table class="border-separate border border-gray-400">...</table>
```

### Table layout

```html
<!-- Auto: columns sized to content -->
<table class="table-auto">...</table>

<!-- Fixed: columns use first row widths -->
<table class="table-fixed">...</table>
```

### Table display (from layout-display)

Combine with `table`, `table-row`, `table-cell`, `table-header-group`, etc. for semantic table structure.

### Responsive

```html
<table class="border-collapse md:border-separate">...</table>
```

## Key Points

- `border-collapse` - adjacent borders merge (single border between cells)
- `border-separate` - each cell displays its own borders
- `table-auto` - column widths from content
- `table-fixed` - fixed layout; first row sets column widths
- In v4, `border-*` and `divide-*` default to `currentColor`; specify a color (e.g. `border-gray-200`) explicitly

<!--
Source references:
- https://tailwindcss.com/docs/border-collapse
- https://tailwindcss.com/docs/table-layout
-->
