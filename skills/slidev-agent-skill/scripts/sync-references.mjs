#!/usr/bin/env node
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

const docs = [
  {
    target: 'references/slidev/core-syntax.md',
    url: 'https://sli.dev/guide/syntax.md',
  },
  {
    target: 'references/slidev/cli.md',
    url: 'https://sli.dev/builtin/cli.md',
  },
  {
    target: 'references/slidev/theme-addon.md',
    url: 'https://sli.dev/guide/theme-addon.md',
  },
  {
    target: 'references/slidev/write-theme.md',
    url: 'https://sli.dev/guide/write-theme.md',
  },
  {
    target: 'references/slidev/layout.md',
    url: 'https://sli.dev/guide/layout.md',
  },
  {
    target: 'references/slidev/directory-structure.md',
    url: 'https://sli.dev/custom/directory-structure.md',
  },
  {
    target: 'references/slidev/exporting.md',
    url: 'https://sli.dev/guide/exporting.md',
  },
  {
    target: 'references/slidev/hosting.md',
    url: 'https://sli.dev/guide/hosting.md',
  },
  {
    target: 'references/slidev/work-with-ai.md',
    url: 'https://sli.dev/guide/work-with-ai.md',
  },
  {
    target: 'references/platforms/codex-skills.md',
    url: 'https://developers.openai.com/codex/skills.md',
  },
  {
    target: 'references/platforms/claude-skills.md',
    url: 'https://code.claude.com/docs/en/skills.md',
  },
  {
    target: 'references/platforms/openclaw-skills.md',
    url: 'https://docs.openclaw.ai/tools/skills.md',
  },
]

const root = process.cwd()

async function fetchText(url) {
  const response = await fetch(url, {
    headers: {
      'user-agent': 'slidev-multi-agent-sync/1.0',
      accept: 'text/markdown,text/plain;q=0.9,*/*;q=0.5',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed ${url}: HTTP ${response.status}`)
  }

  const text = await response.text()
  if (!text.trim()) {
    throw new Error(`Failed ${url}: empty response body`)
  }

  return text.replace(/\r\n/g, '\n').trimEnd() + '\n'
}

async function writeIfChanged(targetPath, content) {
  let current = null
  try {
    current = await readFile(targetPath, 'utf8')
  } catch {
    current = null
  }

  if (current === content) {
    return false
  }

  await writeFile(targetPath, content, 'utf8')
  return true
}

async function main() {
  let updated = 0

  for (const doc of docs) {
    const outputPath = path.join(root, doc.target)
    await mkdir(path.dirname(outputPath), { recursive: true })

    const body = await fetchText(doc.url)
    const content = [`<!-- Source: ${doc.url} -->`, '', body].join('\n')

    const changed = await writeIfChanged(outputPath, content)
    if (changed) {
      updated += 1
      console.log(`updated ${doc.target}`)
    } else {
      console.log(`unchanged ${doc.target}`)
    }
  }

  console.log(`done: ${updated} file(s) updated`)
}

main().catch((error) => {
  console.error(error.message)
  process.exit(1)
})
