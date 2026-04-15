# CI/CD Templates for Cloudflare Pages

Complete GitHub Actions workflow templates for deploying to Cloudflare Pages. Copy the appropriate template to `.github/workflows/deploy.yml` in your repository.

**Required GitHub Secrets** (all templates):

| Secret | Description | Source |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | API token with Pages write permission | Dashboard → API Tokens → "Edit Cloudflare Workers" template |
| `CLOUDFLARE_ACCOUNT_ID` | Your Cloudflare account ID | Dashboard → any zone → Overview sidebar |

---

## Hugo

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true  # Hugo themes are often git submodules
          fetch-depth: 0    # Needed for .GitInfo and .Lastmod

      - uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: 'latest'
          extended: true

      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'

      - run: pnpm install --frozen-lockfile
      - run: hugo --minify

      - name: Deploy to Cloudflare Pages
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy public --project-name ${{ vars.PAGES_PROJECT_NAME }}
```

**Notes:**
- Hugo outputs to `public/` by default. Change to `dist/` if your `hugo.yaml` sets `publishDir: dist`.
- `extended: true` is needed for SCSS/SASS support.
- Remove the pnpm/Node steps if your Hugo site has no npm dependencies.

---

## Astro

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'

      - run: pnpm install --frozen-lockfile
      - run: pnpm build

      - name: Deploy to Cloudflare Pages
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy dist --project-name ${{ vars.PAGES_PROJECT_NAME }}
```

**Notes:**
- Astro outputs to `dist/` by default.
- For SSR mode, use the `@astrojs/cloudflare` adapter instead of static deploy.

---

## Next.js (Static Export)

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'

      - run: pnpm install --frozen-lockfile
      - run: pnpm build

      - name: Deploy to Cloudflare Pages
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy out --project-name ${{ vars.PAGES_PROJECT_NAME }}
```

**Notes:**
- Requires `output: 'export'` in `next.config.js` for static export.
- Next.js static export outputs to `out/`.
- Image optimization is disabled in static export mode — use `<img>` or a CDN.

---

## Generic npm Build

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'

      - run: pnpm install --frozen-lockfile
      - run: pnpm build

      - name: Deploy to Cloudflare Pages
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy dist --project-name ${{ vars.PAGES_PROJECT_NAME }}
```

---

## Customization Guide

### Using npm instead of pnpm

Replace the pnpm steps:

```yaml
      # Remove: - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'npm'

      - run: npm ci
      - run: npm run build
```

### Using yarn

```yaml
      # Remove: - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'yarn'

      - run: yarn install --frozen-lockfile
      - run: yarn build
```

### PR Preview Deployments

To deploy previews for pull requests, remove the `if` condition and add a branch flag:

```yaml
      - name: Deploy to Cloudflare Pages
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: >-
            pages deploy dist
            --project-name ${{ vars.PAGES_PROJECT_NAME }}
            --branch ${{ github.head_ref || github.ref_name }}
```

Preview deploys get a unique URL like `<branch>.<project>.pages.dev`.

### Build Environment Variables

Pass env vars to the build step:

```yaml
      - run: pnpm build
        env:
          NODE_ENV: production
          PUBLIC_API_URL: https://api.example.com
          # Prefix varies by framework:
          #   Astro:   PUBLIC_
          #   Next.js: NEXT_PUBLIC_
          #   Nuxt:    NUXT_PUBLIC_
          #   Vite:    VITE_
```

### Adding a Lint Job

Add a separate lint job that runs in parallel with (or before) the build:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm format:check  # if using Prettier

  build-deploy:
    runs-on: ubuntu-latest
    needs: [lint]              # wait for lint to pass
    steps:
      # ... rest of build-deploy steps
```

---

## Output Directory Reference

| Framework | Default Output Dir | Config Override |
|---|---|---|
| Hugo | `public/` | `publishDir` in `hugo.yaml` |
| Astro | `dist/` | `outDir` in `astro.config.mjs` |
| Next.js (static) | `out/` | `distDir` in `next.config.js` |
| Nuxt (static) | `.output/public/` | `nitro.output.dir` in `nuxt.config.ts` |
| SvelteKit | `build/` | Depends on adapter |
| Vite | `dist/` | `build.outDir` in `vite.config.ts` |
| Gatsby | `public/` | — |
| Eleventy | `_site/` | `dir.output` in `.eleventy.js` |
| Create React App | `build/` | — |

### Setting Project Name as a Variable

All templates use `${{ vars.PAGES_PROJECT_NAME }}` — set this at **Repository → Settings → Variables → Actions → New repository variable**.

Alternatively, hardcode the project name directly in the workflow:

```yaml
          command: pages deploy dist --project-name my-project
```
