# Vercel Deployment & Infrastructure

You have access to Vercel CLI for deployment and project management.
Follow these rules when working with Vercel-deployed projects.

## Environment Detection

Check if the project is Vercel-connected:
```bash
# Look for .vercel/project.json
cat .vercel/project.json 2>/dev/null
# Check for vercel.json config
cat vercel.json 2>/dev/null
```

## Deployment Rules

### DO:
- Use `vercel --prod` for production deploys (only when explicitly asked)
- Use `vercel` (no flags) for preview deploys
- Always run `npm run build` locally BEFORE deploying to catch errors early
- Check `vercel env ls` to know what env vars are available
- Use `vercel logs` to debug deployment failures

### DO NOT:
- Never hardcode secrets in code — use `vercel env add` or `.env.local`
- Never deploy without a successful local build first
- Never run `vercel env rm` without explicit approval
- Never modify `vercel.json` routing without understanding existing config
- Never use `--force` flag

## Environment Variables

```bash
# List current env vars (names only, no values)
vercel env ls

# Add a new env var (interactive)
vercel env add VARIABLE_NAME

# Pull env vars to local .env.local
vercel env pull .env.local
```

**Security**: Never echo, log, or commit env var values. If you need to verify a value exists, check the variable name only.

## Common Patterns

### Next.js on Vercel
- Build command: `next build` (auto-detected)
- Output directory: `.next` (auto-detected)
- Framework: auto-detected from `package.json`
- Node version: set in `package.json` engines or Vercel dashboard

### Static Assets
- Put in `public/` directory
- Accessible at `/{filename}` after deploy
- Large assets (>50MB) should use external CDN

### API Routes
- `app/api/*/route.ts` → serverless functions
- Max execution time: 10s (Hobby) / 60s (Pro)
- Use `export const runtime = 'edge'` for edge functions

### Redirects & Rewrites
```json
// vercel.json
{
  "redirects": [{ "source": "/old", "destination": "/new", "permanent": true }],
  "rewrites": [{ "source": "/api/:path*", "destination": "https://backend.example.com/:path*" }]
}
```

## Debugging Deploy Failures

1. Check build logs: `vercel logs <deployment-url>`
2. Common issues:
   - **Module not found**: Missing dependency in `package.json`
   - **Build timeout**: Reduce build complexity or increase timeout
   - **Env var missing**: `vercel env ls` to verify
   - **Edge runtime incompatible**: Some Node.js APIs not available in Edge
3. Test locally first: `vercel dev` mirrors production behavior

## Domain Management

```bash
vercel domains ls                    # List domains
vercel domains add example.com       # Add domain
vercel domains inspect example.com   # DNS details
```

## Project Linking

If `.vercel/project.json` doesn't exist:
```bash
vercel link    # Interactive project linking
```

## Reporting

When performing Vercel operations, include in `.task-result.json`:
```json
{
  "infra_actions": ["vercel deploy --prod", "vercel env add X"],
  "deploy_url": "https://project-abc123.vercel.app"
}
```
