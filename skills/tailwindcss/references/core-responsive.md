---
name: core-responsive
description: Building responsive designs with Tailwind's mobile-first breakpoint system and container queries
---

# Responsive Design

Every utility class in Tailwind can be applied conditionally at different breakpoints using responsive variants.

## Mobile-First Breakpoints

Tailwind uses a mobile-first approach. Unprefixed utilities apply to all screen sizes, while prefixed utilities apply at that breakpoint and above.

```html
<!-- Center text on mobile, left align on sm screens and up -->
<div class="text-center sm:text-left">Content</div>
```

## Default Breakpoints

| Breakpoint | Minimum Width | CSS |
|------------|---------------|-----|
| `sm` | 40rem (640px) | `@media (width >= 40rem)` |
| `md` | 48rem (768px) | `@media (width >= 48rem)` |
| `lg` | 64rem (1024px) | `@media (width >= 64rem)` |
| `xl` | 80rem (1280px) | `@media (width >= 80rem)` |
| `2xl` | 96rem (1536px) | `@media (width >= 96rem)` |

## Usage

Prefix any utility with a breakpoint name:

```html
<!-- Width of 16 by default, 32 on medium screens, 48 on large screens -->
<img class="w-16 md:w-32 lg:w-48" src="..." />
```

## Example: Responsive Card

```html
<div class="mx-auto max-w-md md:max-w-2xl">
  <div class="md:flex">
    <div class="md:shrink-0">
      <img class="h-48 w-full object-cover md:h-full md:w-48" src="..." />
    </div>
    <div class="p-8">
      <h2 class="text-lg font-semibold">Title</h2>
      <p class="text-gray-500">Description</p>
    </div>
  </div>
</div>
```

## Targeting Mobile Screens

Use unprefixed utilities for mobile, not `sm:`. Think of `sm:` as "at the small breakpoint", not "on small screens".

```html
<!-- ❌ Only centers on screens 640px+, not mobile -->
<div class="sm:text-center"></div>

<!-- ✅ Centers on mobile, left aligns on 640px+ -->
<div class="text-center sm:text-left"></div>
```

## Breakpoint Ranges

Target a specific breakpoint range by stacking responsive variants with `max-*` variants:

```html
<!-- Only applies between md and xl -->
<div class="md:max-xl:flex">Content</div>
```

## Max-Width Variants

Tailwind generates `max-*` variants for each breakpoint:

| Variant | Media Query |
|---------|-------------|
| `max-sm` | `@media (width < 40rem)` |
| `max-md` | `@media (width < 48rem)` |
| `max-lg` | `@media (width < 64rem)` |
| `max-xl` | `@media (width < 80rem)` |
| `max-2xl` | `@media (width < 96rem)` |

## Custom Breakpoints

Add custom breakpoints using `--breakpoint-*` theme variables:

```css
@theme {
  --breakpoint-xs: 30rem;
  --breakpoint-3xl: 120rem;
}
```

```html
<div class="xs:grid-cols-2 3xl:grid-cols-6">Content</div>
```

## Arbitrary Breakpoints

Use arbitrary values for one-off breakpoints:

```html
<div class="min-[320px]:text-center max-[600px]:bg-sky-300">
  Content
</div>
```

## Container Queries

Style elements based on parent container size instead of viewport:

```html
<!-- Mark container -->
<div class="@container">
  <!-- Style based on container size -->
  <div class="flex flex-col @md:flex-row">
    Content
  </div>
</div>
```

### Container Query Variants

| Variant | Minimum Width |
|---------|---------------|
| `@3xs` | 16rem (256px) |
| `@xs` | 20rem (320px) |
| `@sm` | 24rem (384px) |
| `@md` | 28rem (448px) |
| `@lg` | 32rem (512px) |
| `@xl` | 36rem (576px) |
| `@2xl` | 42rem (672px) |
| `@3xl` | 48rem (768px) |
| ... up to `@7xl` | 80rem (1280px) |

### Named Containers

Name containers to target specific ones in nested structures:

```html
<div class="@container/main">
  <div class="flex flex-row @sm/main:flex-col">
    Content
  </div>
</div>
```

## Key Points

- Mobile-first: unprefixed = mobile, prefixed = breakpoint and up
- Use unprefixed utilities for mobile, not `sm:`
- Stack variants for complex responsive behavior
- Container queries enable component-based responsive design
- Customize breakpoints with theme variables

<!--
Source references:
- https://tailwindcss.com/docs/responsive-design
-->
