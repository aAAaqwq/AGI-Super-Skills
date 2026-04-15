---
name: effects-visibility-interactivity
description: Visibility, cursor, pointer-events, user-select, and z-index
---

# Visibility & Interactivity

Utilities for visibility, cursor, pointer-events, user-select, and stacking.

## Usage

### Visibility

```html
<div class="visible">Visible (default)</div>
<div class="invisible">Hidden but in layout</div>
<div class="collapse">Table collapse</div>
```

Use `invisible` when you need to keep layout space; use `hidden` (display:none) to remove from flow.

### Cursor

```html
<button class="cursor-pointer">Pointer</button>
<div class="cursor-not-allowed">Disabled</div>
<div class="cursor-wait">Loading</div>
<div class="cursor-move">Draggable</div>
<div class="cursor-grab">Grab</div>
<div class="cursor-grabbing">Grabbing</div>
<div class="cursor-text">Text select</div>
<div class="cursor-default">Default</div>
<div class="cursor-none">No cursor</div>
```

### Pointer events

```html
<div class="pointer-events-none">Ignore all pointer events</div>
<div class="pointer-events-auto">Default behavior</div>
```

Useful for overlays: make overlay `pointer-events-none` so clicks pass through, or `pointer-events-none` on disabled elements.

### User select

```html
<p class="select-none">Cannot select</p>
<p class="select-text">Select text (default)</p>
<p class="select-all">Select all on click</p>
<p class="select-auto">Browser default</p>
```

### Z-index

```html
<div class="z-0">0</div>
<div class="z-10">10</div>
<div class="z-20">20</div>
<div class="z-50">50</div>
<div class="z-auto">Auto</div>
<div class="z-[100]">Arbitrary</div>
```

Common: `z-0` (base), `z-10` (dropdowns), `z-20` (fixed nav), `z-50` (modal), `z-40` (overlay).

## Key Points

- Visibility: `visible`, `invisible`, `collapse`
- Cursor: `cursor-{pointer,not-allowed,wait,move,grab,text,default,none}`
- Pointer events: `pointer-events-none`, `pointer-events-auto`
- User select: `select-none`, `select-text`, `select-all`
- Z-index: `z-{0,10,20,30,40,50,auto}`, `z-[n]`

<!--
Source references:
- https://tailwindcss.com/docs/visibility
- https://tailwindcss.com/docs/cursor
- https://tailwindcss.com/docs/pointer-events
- https://tailwindcss.com/docs/user-select
- https://tailwindcss.com/docs/z-index
-->
