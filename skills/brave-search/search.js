#!/usr/bin/env node
const { BraveSearch } = require('brave-search');
const fs = require('fs');
const { execSync } = require('child_process');

// Get API key from pass or environment
let apiKey = process.env.BRAVE_API_KEY;
if (!apiKey) {
  try {
    apiKey = execSync('pass show api/brave-search 2>/dev/null', { encoding: 'utf8' }).trim();
  } catch (e) {
    console.error('Error: BRAVE_API_KEY not found. Set it in environment or store in pass as api/brave-search');
    process.exit(1);
  }
}

const braveSearch = new BraveSearch(apiKey);

// Parse command line arguments
const args = process.argv.slice(2);
let query = '';
let count = 5;
let includeContent = false;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '-n' || args[i] === '--count') {
    count = parseInt(args[i + 1]) || 5;
    i++;
  } else if (args[i] === '--content' || args[i] === '-c') {
    includeContent = true;
  } else if (!args[i].startsWith('-')) {
    query = args[i];
  }
}

if (!query) {
  console.error('Usage: ./search.js "query" [-n count] [--content]');
  process.exit(1);
}

async function search() {
  try {
    const results = await braveSearch.webSearch(query, {
      count: count,
      safesearch: 'off',
      search_lang: 'zh-hans',
      country: 'CN',
      text_decorations: false,
    });

    if (results.web && results.web.results) {
      results.web.results.forEach((result, index) => {
        console.log(`\n--- Result ${index + 1} ---`);
        console.log(`Title: ${result.title}`);
        console.log(`Link: ${result.url}`);
        console.log(`Snippet: ${result.description}`);
        
        if (includeContent) {
          console.log(`\nContent: [Use content.js to fetch full content from URL]`);
        }
      });
    } else {
      console.log('No results found');
    }
  } catch (error) {
    console.error('Search error:', error.message);
    process.exit(1);
  }
}

search();
