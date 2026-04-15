---
name: core-utility-classes
description: Understanding Tailwind's utility-first approach and how to style elements with utility classes
---

# Utility Classes

Tailwind CSS uses a utility-first approach where you style elements by combining many single-purpose utility classes directly in your markup.

## Overview

Instead of writing custom CSS, you compose designs using utility classes:

```html
<div class="mx-auto flex max-w-sm items-center gap-x-4 rounded-xl bg-white p-6 shadow-lg">
  <img class="size-12 shrink-0" src="/logo.svg" alt="Logo" />
  <div>
    <div class="text-xl font-medium text-black">ChitChat</div>
    <p class="text-gray-500">You have a new message!</p>
  </div>
</div>
```

## Benefits

- **Faster development** - No need to come up with class names or switch between HTML and CSS files
- **Safer changes** - Adding or removing utilities only affects that element
- **Easier maintenance** - Find the element and change classes, no need to remember custom CSS
- **More portable** - Copy entire UI chunks between projects easily
- **Smaller CSS** - Utilities are reusable, so CSS doesn't grow linearly

## Why Not Inline Styles?

Utility classes have important advantages over inline styles:

- **Design constraints** - Choose from a predefined design system instead of magic numbers
- **State variants** - Target hover, focus, and other states with variants like `hover:bg-blue-600`
- **Responsive design** - Use responsive variants like `md:flex` for media queries

## Utility Class Structure

Utility classes follow consistent naming patterns:

- **Property-value**: `bg-blue-500`, `text-lg`, `rounded-xl`
- **Responsive**: `md:flex`, `lg:text-center`
- **State variants**: `hover:bg-blue-600`, `focus:outline-2`
- **Arbitrary values**: `top-[117px]`, `bg-[#bada55]`

## Key Points

- Every utility class is single-purpose and composable
- Utilities can be combined with variants for conditional styling
- Use complete class names - Tailwind scans your files as plain text
- Avoid dynamically constructing class names with string interpolation

<!--
Source references:
- https://tailwindcss.com/docs/styling-with-utility-classes
-->
