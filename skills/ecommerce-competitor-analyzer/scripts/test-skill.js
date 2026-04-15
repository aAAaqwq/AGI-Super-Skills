#!/usr/bin/env node

/**
 * Test Script for E-commerce Competitor Analyzer Skill
 * Tests the complete workflow: Scraping → AI Analysis → Google Sheets Write
 */

const fs = require('fs');
const path = require('path');
const { validateProductData } = require('./data-validator.js');
const { scrapeWithOlostep } = require('./olostep-client.js');

// Load environment variables
function loadEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  const envContent = fs.readFileSync(envPath, 'utf8');
  const lines = envContent.split('\n');

  for (const line of lines) {
    const trimmedLine = line.trim();
    if (trimmedLine && !trimmedLine.startsWith('#')) {
      const [key, ...valueParts] = trimmedLine.split('=');
      const value = valueParts.join('=').trim();
      if (key && value) {
        process.env[key.trim()] = value;
      }
    }
  }
}

// Test scraping function (with v1/v2 compatibility)
async function testScrape(asin) {
  console.log(`\n🔍 Testing scrape for ASIN: ${asin}`);

  try {
    // Use compatible client with auto-fallback
    const result = await scrapeWithOlostep(asin, {
      apiVersion: process.env.OLOSTEP_API_VERSION || 'v1',  // Default to v1
      comments: 100
    });

    if (!result.success) {
      throw new Error(result.error || 'Scraping failed');
    }

    console.log(`✅ Scrape successful with API ${result.apiVersion}: ${result.markdownContent.length} characters`);

    // Extract basic data for validation
    const extractedData = {
      title: extractTitle(result.markdownContent),
      price: extractPrice(result.markdownContent),
      rating: extractRating(result.markdownContent)
    };

    // Validate scraped data
    const validation = validateProductData(asin, extractedData);

    if (!validation.isValid) {
      console.error(`\n⚠️ Validation Failed for ASIN ${asin}:`);
      validation.issues.forEach(issue => console.error(`   ❌ ${issue}`));
      validation.warnings.forEach(warning => console.warn(`   ⚠️  ${warning}`));
      console.error(`   ${validation.summary}`);
    } else {
      console.log(`✅ Validation passed`);
    }

    if (validation.warnings.length > 0) {
      console.warn(`\n⚠️ Validation Warnings for ASIN ${asin}:`);
      validation.warnings.forEach(warning => console.warn(`   ⚠️  ${warning}`));
    }

    return {
      success: true,
      data: result.rawData,
      markdownContent: result.markdownContent,
      apiVersion: result.apiVersion,
      validation: {
        passed: validation.isValid,
        ...validation
      },
      extractedData
    };

  } catch (error) {
    console.error(`❌ Scrape failed: ${error.message}`);
    return { success: false, error: error.message };
  }
}

// Helper functions to extract data from markdown content
function extractTitle(markdown) {
  // Try to find title in various markdown formats
  const patterns = [
    /^#\s+(.+)$/m,           // # Title
    /##\s+Title\s*\n\s*(.+)$/m,  // ## Title\n content
    /##\s+产品标题\s*\n\s*(.+)$/m,
  ];

  for (const pattern of patterns) {
    const match = markdown.match(pattern);
    if (match && match[1]) {
      return match[1].trim();
    }
  }

  // Fallback: return first non-empty line
  const lines = markdown.split('\n').filter(l => l.trim());
  return lines[0] || 'Unknown Title';
}

function extractPrice(markdown) {
  // Try to extract price from markdown
  const patterns = [
    /\$\s*(\d+\.?\d*)/,  // $19.99
    /价格[：\s]*[^\d]*([\d,]+\.?\d*)/i,  // 价格：$19.99
    /Price[：\s]*[^\d]*([\d,]+\.?\d*)/i,
  ];

  for (const pattern of patterns) {
    const match = markdown.match(pattern);
    if (match && match[1]) {
      return match[1].replace(/,/g, '');
    }
  }

  return null;
}

function extractRating(markdown) {
  // Try to extract rating from markdown
  const patterns = [
    /(\d\.?\d*)\s*[☆★]/,  // 4.5 ⭐
    /评分[：\s]*[^\d]*(\d\.?\d*)/i,  // 评分：4.5
    /Rating[：\s]*[^\d]*(\d\.?\d*)/i,
  ];

  for (const pattern of patterns) {
    const match = markdown.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }

  return null;
}

// Test AI analysis function
async function testAIAnalysis(markdownContent, asin) {
  console.log(`\n🤖 Testing AI analysis for ASIN: ${asin}`);

  const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

  // Load prompt template
  const promptPath = path.join(__dirname, '..', 'prompts', 'analysis-prompt-base.md');
  let promptTemplate = '';
  try {
    promptTemplate = fs.readFileSync(promptPath, 'utf8');
  } catch (error) {
    promptTemplate = `你是亚马逊竞品分析专家。请分析以下产品页面的内容：\n\n{{ PRODUCT_CONTENT }}`;
  }

  // Replace placeholder
  const prompt = promptTemplate.replace('{{ PRODUCT_CONTENT }}', markdownContent.substring(0, 10000)); // Limit content length

  try {
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=${GEMINI_API_KEY}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        contents: [{
          parts: [{
            text: prompt
          }]
        }]
      })
    });

    if (!response.ok) {
      throw new Error(`Gemini API error: ${response.status}`);
    }

    const data = await response.json();
    const analysisText = data.candidates?.[0]?.content?.parts?.[0]?.text || '';

    console.log(`✅ AI analysis successful: ${analysisText.length} characters`);
    return { success: true, content: analysisText };

  } catch (error) {
    console.error(`❌ AI analysis failed: ${error.message}`);
    return { success: false, error: error.message };
  }
}

// Test Google Sheets write function
async function testGoogleSheetsWrite(asin, title, price, rating, analysis) {
  console.log(`\n📊 Testing Google Sheets write for ASIN: ${asin}`);

  try {
    // Check if tokens exist
    const tokenPath = path.join(__dirname, '..', '.google-tokens.json');
    if (!fs.existsSync(tokenPath)) {
      console.log(`   ⚠️  Not authenticated yet`);
      console.log(`   Run: node scripts/auth-google-sheets.js`);
      console.log(`✅ Google Sheets write skipped (not authenticated)`);
      return { success: true, authenticated: false };
    }

    // Load the writer module
    const { writeAnalysisResults, config } = require('./google-sheets-writer.js');

    console.log(`   Target Sheet: ${config.sheetId}`);
    console.log(`   Target GID: ${config.gid || 'default'}`);
    console.log(`   - ASIN: ${asin}`);
    console.log(`   - Title: ${title}`);
    console.log(`   - Price: ${price}`);
    console.log(`   - Rating: ${rating}`);

    // Note: We'll write all results at the end, not per-item
    console.log(`✅ Google Sheets ready to write`);

    return { success: true, authenticated: true };
  } catch (error) {
    console.error(`   ❌ Google Sheets error: ${error.message}`);
    return { success: false, error: error.message };
  }
}

// Extract structured data from AI response
function extractData(aiResponse) {
  let title = '未知';
  let price = '未知';
  let rating = '未知';

  // Title patterns (handle multiple formats including markdown bold)
  const titlePatterns = [
    /\*\*1\.\s*产品标题\*\*[^\n]*\n([^\n]+)/,
    /\*\*产品标题\*\*[^\n]*\n([^\n]+)/,
    /产品标题[：\s]+([^\n]+)/,
    /Title[：\s]+([^\n]+)/,
    /产品标题[：:]+([^\n]+)/,
    /Title[：:]+([^\n]+)/,
    /1\.\s*产品标题[^\n]*\n([^\n]+)/
  ];
  for (const pattern of titlePatterns) {
    const match = aiResponse.match(pattern);
    if (match) {
      title = match[1].trim();
      break;
    }
  }

  // Price patterns (handle multiple formats)
  const pricePatterns = [
    /\*\*2\.\s*价格\*\*[^\n]*\n[^0-9\$¥]*([0-9]+\.?[0-9]*)/,
    /\*\*价格\*\*[^\n]*\n[^0-9\$¥]*([0-9]+\.?[0-9]*)/,
    /价格[：\s]+[^0-9\$¥]*([0-9]+\.?[0-9]*)/,
    /Price[：\s]+[^0-9\$¥]*([0-9]+\.?[0-9]*)/,
    /价格[：:]+[^0-9]*([0-9]+\.?[0-9]*)/,
    /Price[：:]+[^0-9]*([0-9]+\.?[0-9]*)/,
    /2\.\s*价格[^\n]*\n[^0-9\$¥]*([0-9]+\.?[0-9]*)/
  ];
  for (const pattern of pricePatterns) {
    const match = aiResponse.match(pattern);
    if (match) {
      price = match[1];
      break;
    }
  }

  // Rating patterns (handle multiple formats)
  const ratingPatterns = [
    /\*\*3\.\s*评分\*\*[^\n]*\n[^0-9\.]*([0-9]+\.?[0-9]*)/,
    /\*\*评分\*\*[^\n]*\n[^0-9\.]*([0-9]+\.?[0-9]*)/,
    /评分[：\s]+[^0-9\.]*([0-9]+\.?[0-9]*)/,
    /Rating[：\s]+[^0-9\.]*([0-9]+\.?[0-9]*)/,
    /评分[：:]+[^0-9]*([0-9]+\.?[0-9]*)/,
    /Rating[：:]+[^0-9]*([0-9]+\.?[0-9]*)/,
    /3\.\s*评分[^\n]*\n[^0-9\.]*([0-9]+\.?[0-9]*)/
  ];
  for (const pattern of ratingPatterns) {
    const match = aiResponse.match(pattern);
    if (match) {
      rating = match[1];
      break;
    }
  }

  return { title, price, rating };
}

// Main test function
async function runTest(asins) {
  console.log('='.repeat(60));
  console.log('🧪 E-commerce Competitor Analyzer - Test Run');
  console.log('='.repeat(60));
  console.log(`\nTest ASINs: ${asins.join(', ')}`);
  console.log(`Target Sheet: ${process.env.GOOGLE_SHEETS_ID_DEFAULT} (GID: ${process.env.GOOGLE_SHEET_GID || 'default'})`);

  const results = [];

  for (const asin of asins) {
    console.log(`\n${'─'.repeat(60)}`);
    console.log(`Processing: ${asin}`);
    console.log('─'.repeat(60));

    // Step 1: Scrape
    const scrapeResult = await testScrape(asin);
    if (!scrapeResult.success) {
      results.push({ asin, success: false, error: 'Scrape failed' });
      continue;
    }

    // Step 2: AI Analysis
    const analysisResult = await testAIAnalysis(scrapeResult.markdownContent, asin);
    if (!analysisResult.success) {
      results.push({ asin, success: false, error: 'AI analysis failed' });
      continue;
    }

    // Step 3: Extract Data
    const extracted = extractData(analysisResult.content);
    console.log(`\n📋 Extracted Data:`);
    console.log(`   Title: ${extracted.title}`);
    console.log(`   Price: ${extracted.price}`);
    console.log(`   Rating: ${extracted.rating}`);

    // Step 4: Write to Google Sheets
    await testGoogleSheetsWrite(asin, extracted.title, extracted.price, extracted.rating, analysisResult.content);

    results.push({
      asin,
      success: true,
      extracted,
      analysis: analysisResult.content
    });
  }

  // Summary
  console.log(`\n${'='.repeat(60)}`);
  console.log('📊 Test Summary');
  console.log('='.repeat(60));
  console.log(`Total: ${asins.length}`);
  console.log(`Success: ${results.filter(r => r.success).length}`);
  console.log(`Failed: ${results.filter(r => !r.success).length}`);

  // Save results to file (append mode)
  const outputDir = path.join(__dirname, '..', 'output');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const outputFile = path.join(outputDir, 'analysis-results.json');

  // Load existing results or create new array
  let existingResults = [];
  if (fs.existsSync(outputFile)) {
    try {
      const existingData = fs.readFileSync(outputFile, 'utf8');
      existingResults = JSON.parse(existingData);
      console.log(`\n📂 Loaded ${existingResults.length} existing records`);
    } catch (error) {
      console.warn(`⚠️  Could not read existing file, starting fresh`);
    }
  }

  // Append new results
  const updatedResults = [...existingResults, ...results];
  fs.writeFileSync(outputFile, JSON.stringify(updatedResults, null, 2));
  console.log(`\n💾 Results saved to: ${outputFile}`);
  console.log(`   Total records: ${updatedResults.length}`);

  // Generate and save Markdown report
  const { formatMarkdownReport } = require('./batch-processor.js');
  const markdownReport = formatMarkdownReport(results);

  // Create reports directory if it doesn't exist
  const reportsDir = path.join(__dirname, '..', 'reports');
  if (!fs.existsSync(reportsDir)) {
    fs.mkdirSync(reportsDir, { recursive: true });
  }

  const dateStr = new Date().toISOString().split('T')[0];
  const markdownFile = path.join(reportsDir, `竞品分析-${dateStr}.md`);
  fs.writeFileSync(markdownFile, markdownReport);
  console.log(`\n📝 Markdown report saved to: ${markdownFile}`);

  // Write to Google Sheets (if authenticated)
  console.log(`\n${'='.repeat(60)}`);
  console.log('📊 Writing to Google Sheets');
  console.log('='.repeat(60));

  try {
    const { writeAnalysisResults, config } = require('./google-sheets-writer.js');
    console.log(`   Target Sheet: ${config.sheetId}`);
    console.log(`   Target GID: ${config.gid || 'default'}`);

    await writeAnalysisResults(results);
    console.log(`\n✅ Successfully wrote results to Google Sheets!`);
    console.log(`   View: https://docs.google.com/spreadsheets/d/${config.sheetId}`);
  } catch (error) {
    if (error.message.includes('Not authenticated')) {
      console.log(`\n⚠️  Google Sheets not authenticated`);
      console.log(`   To enable, run: node scripts/auth-google-sheets.js`);
    } else {
      console.error(`\n❌ Google Sheets write failed: ${error.message}`);
    }
  }
}

// Run the test
(async () => {
  loadEnv();

  const asins = process.argv.slice(2);
  if (asins.length === 0) {
    console.log('Usage: node test-skill.js <ASIN1> <ASIN2> ...');
    console.log('\nRunning with default test ASINs...');
    await runTest(['B08LNY11RK', 'B0F5HFG1N8']);
  } else {
    await runTest(asins);
  }
})();
