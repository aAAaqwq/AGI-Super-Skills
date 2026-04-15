---
name: core-variants
description: Using variants to apply utilities conditionally based on states, pseudo-classes, and media queries
---

# Variants

Variants let you apply utility classes conditionally based on states, pseudo-classes, pseudo-elements, media queries, and more.

## Overview

Add a variant prefix to any utility class to apply it conditionally:

```html
<!-- Apply bg-sky-700 only on hover -->
<button class="bg-sky-500 hover:bg-sky-700">Save</button>
```

Variants can be stacked to target specific situations:

```html
<!-- Dark mode, medium breakpoint, on hover -->
<button class="dark:md:hover:bg-fuchsia-600">Save</button>
```

## Pseudo-Class Variants

### Interactive States

```html
<button class="bg-violet-500 hover:bg-violet-600 focus:outline-2 focus:outline-violet-500 active:bg-violet-700">
  Save changes
</button>
```

Common interactive variants:
- `hover:` - `:hover` pseudo-class
- `focus:` - `:focus` pseudo-class
- `active:` - `:active` pseudo-class
- `focus-visible:` - `:focus-visible`
- `focus-within:` - `:focus-within`
- `visited:` - `:visited`

### Structural Variants

```html
<ul>
  <li class="py-4 first:pt-0 last:pb-0">Item 1</li>
  <li class="py-4 first:pt-0 last:pb-0">Item 2</li>
  <li class="py-4 first:pt-0 last:pb-0">Item 3</li>
</ul>
```

Common structural variants:
- `first:` - `:first-child`
- `last:` - `:last-child`
- `odd:` - `:nth-child(odd)`
- `even:` - `:nth-child(even)`
- `only:` - `:only-child`

### Form States

```html
<input class="border-gray-300 required:border-red-500 invalid:border-red-500" />
```

Common form variants:
- `required:` - `:required`
- `optional:` - `:optional`
- `invalid:` - `:invalid`
- `valid:` - `:valid`
- `disabled:` - `:disabled`
- `enabled:` - `:enabled`
- `checked:` - `:checked`

## Pseudo-Element Variants

```html
<input class="placeholder:text-gray-400 before:content-['*'] after:content-['required']" />
```

Common pseudo-element variants:
- `before:` - `::before`
- `after:` - `::after`
- `placeholder:` - `::placeholder`
- `selection:` - `::selection`
- `first-line:` - `::first-line`
- `first-letter:` - `::first-letter`

## Media Query Variants

### Responsive Variants

```html
<div class="text-sm md:text-base lg:text-lg">Responsive text</div>
```

### Dark Mode

```html
<div class="bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
  Content
</div>
```

By default uses `prefers-color-scheme`, but can be customized to use a class or data attribute.

### Reduced Motion

```html
<div class="transition-all motion-reduce:transition-none">
  Animated content
</div>
```

## Attribute Selector Variants

```html
<!-- RTL support -->
<div class="text-left rtl:text-right">Content</div>

<!-- Open state -->
<details class="[&[open]]:bg-gray-100">Details</details>
```

## Arbitrary Variants

Use arbitrary variants for custom selectors:

```html
<ul>
  <li class="lg:[&:nth-child(-n+3)]:hover:underline">Item</li>
</ul>
```

## Child Selector Variants

```html
<div class="[&>*]:mb-4 [&>*:last-child]:mb-0">
  <p>Paragraph 1</p>
  <p>Paragraph 2</p>
</div>
```

## Key Points

- Variants prefix utilities to apply them conditionally
- Variants can be stacked: `dark:md:hover:bg-blue-600`
- Use variants for states, pseudo-classes, media queries, and more
- Arbitrary variants enable custom selector patterns
- Child selector variants target descendant elements

<!--
Source references:
- https://tailwindcss.com/docs/hover-focus-and-other-states
-->
