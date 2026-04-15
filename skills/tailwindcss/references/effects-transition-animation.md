---
name: effects-transition-animation
description: CSS transitions, animation keyframes, and reduced motion support
---

# Transition & Animation

Utilities for CSS transitions and animations.

## Usage

### Transition property

```html
<button class="transition hover:bg-blue-600">Transitions common properties</button>
<button class="transition-all hover:scale-110">All properties</button>
<button class="transition-colors hover:bg-indigo-500">Colors only</button>
<button class="transition-opacity hover:opacity-75">Opacity only</button>
<button class="transition-transform hover:translate-y-1">Transform only</button>
<button class="transition-none">No transition</button>
```

### Transition duration and delay

```html
<button class="transition duration-150">150ms (default)</button>
<button class="transition duration-300">300ms</button>
<button class="transition duration-500">500ms</button>
<button class="transition delay-150">Delay 150ms</button>
<button class="transition duration-300 delay-100">Both</button>
```

### Transition timing

```html
<button class="transition ease-linear">Linear</button>
<button class="transition ease-in">Ease in</button>
<button class="transition ease-out">Ease out</button>
<button class="transition ease-in-out">Ease in-out (default)</button>
<button class="transition ease-[cubic-bezier(0.4,0,0.2,1)]">Arbitrary</button>
```

### Animation keyframes

```html
<div class="animate-spin">Spinning</div>
<div class="animate-ping">Ping effect</div>
<div class="animate-pulse">Pulse</div>
<div class="animate-bounce">Bounce</div>
```

Built-in: `animate-spin`, `animate-ping`, `animate-pulse`, `animate-bounce`. Use `@keyframes` in custom CSS for more.

### Reduced motion

```html
<button class="transition hover:-translate-y-1 motion-reduce:transition-none motion-reduce:hover:translate-y-0">
  Respects prefers-reduced-motion
</button>
<div class="animate-spin motion-reduce:animate-none">Spinner hidden when reduced motion</div>
```

Use `motion-reduce:` to disable or simplify animations when user prefers reduced motion.

## Key Points

- Transition: `transition`, `transition-all`, `transition-colors`, `transition-opacity`, `transition-transform`
- Duration: `duration-{75,100,150,200,300,500,700,1000}`
- Delay: `delay-{75,100,150,200,300,500,700,1000}`
- Timing: `ease-{linear,in,in-out,out}`
- Animation: `animate-spin`, `animate-ping`, `animate-pulse`, `animate-bounce`
- Always consider `motion-reduce:` for accessibility

<!--
Source references:
- https://tailwindcss.com/docs/transition-property
- https://tailwindcss.com/docs/transition-duration
- https://tailwindcss.com/docs/transition-timing-function
- https://tailwindcss.com/docs/animation
-->
