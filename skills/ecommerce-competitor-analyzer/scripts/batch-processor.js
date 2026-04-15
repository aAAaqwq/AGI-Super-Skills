/**
 * Batch Processor for E-commerce Competitor Analysis
 *
 * Core processing engine that orchestrates:
 * 1. Product scraping (Olostep API)
 * 2. AI analysis (Gemini)
 * 3. Structured output (Google Sheets + Markdown)
 *
 * Based on n8n workflow batch processing pattern (v81)
 * Reference: 工作流配置.json - "Code - 提取结构化数据" node
 */

const { scrapeAmazonProduct, batchScrapeAmazon, extractASIN } = require('./scrape-amazon.js');

/**
 * Parse Google Sheets specification from user input
 * @param {string} userInput - User's text input
 * @returns {Object} - Parsed sheet configuration
 */
function parseGoogleSheetsSpec(userInput) {
  if (!userInput) {
    // Return default from env
    return {
      sheetId: process.env.GOOGLE_SHEETS_ID_DEFAULT || null,
      sheetName: process.env.GOOGLE_SHEET_NAME_DEFAULT || '工作表1',
      source: 'default'
    };
  }

  const input = userInput.toLowerCase();

  // Pattern 1: Sheet ID (e.g., "Sheet ID: abc123" or "SheetID:abc123")
  const sheetIdMatch = userInput.match(/sheet\s*id\s*[:：]\s*([a-zA-Z0-9-_]+)/);
  if (sheetIdMatch) {
    return {
      sheetId: sheetIdMatch[1],
      sheetName: '工作表1',
      source: 'explicit_id'
    };
  }

  // Pattern 2: Google Sheets URL (e.g., "https://docs.google.com/spreadsheets/d/abc123")
  const urlMatch = userInput.match(/docs\.google\.com\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
  if (urlMatch) {
    return {
      sheetId: urlMatch[1],
      sheetName: '工作表1',
      source: 'url'
    };
  }

  // Pattern 3: Table name (e.g., "写入到表格\"我的竞品分析\"")
  const nameMatch = userInput.match(/表格["""](.+?)["""]|表格\s*[:：]\s*(.+)/);
  if (nameMatch) {
    return {
      sheetId: null,  // Will search by name
      sheetName: nameMatch[1] || nameMatch[2],
      source: 'name'
    };
  }

  // Return default
  return {
    sheetId: process.env.GOOGLE_SHEETS_ID_DEFAULT || null,
    sheetName: process.env.GOOGLE_SHEET_NAME_DEFAULT || '工作表1',
    source: 'default'
  };
}

/**
 * Process all input items (matching n8n $input.all() pattern)
 * @param {Array} items - Array of product identifiers (ASINs/URLs)
 * @param {Object} options - Processing options
 * @returns {Promise<Array>} - Processed results
 */
async function processBatch(items, options = {}) {
  const {
    platform = 'amazon',
    onProgress = null,  // Callback for progress updates
    onError = null      // Callback for error handling
  } = options;

  console.log(`[BatchProcessor] Starting batch processing: ${items.length} items`);

  const results = [];
  const errors = [];

  // Process each item (matching n8n .map() pattern)
  for (let index = 0; index < items.length; index++) {
    const item = items[index];

    try {
      // Progress callback
      if (onProgress) {
        onProgress({
          current: index + 1,
          total: items.length,
          item: item
        });
      }

      console.log(`[BatchProcessor] Processing item ${index + 1}/${items.length}: ${item}`);

      // Step 1: Scrape product data
      const scrapeResult = await scrapeAmazonProduct(item);
      if (!scrapeResult.success) {
        throw new Error(scrapeResult.error || 'Scraping failed');
      }

      // Step 2: AI analysis
      const analysisResult = await analyzeWithAI(scrapeResult);
      if (!analysisResult.success) {
        throw new Error(analysisResult.error || 'AI analysis failed');
      }

      // Step 3: Extract structured data
      const extractedData = extractStructuredData(
        analysisResult.content,
        scrapeResult.asin
      );

      // Step 4: Format output
      results.push({
        success: true,
        index: index,
        input: item,
        asin: scrapeResult.asin,
        scraped: scrapeResult,
        analysis: analysisResult,
        extracted: extractedData
      });

    } catch (error) {
      console.error(`[BatchProcessor] Error processing item ${index + 1}:`, error.message);

      const errorResult = {
        success: false,
        index: index,
        input: item,
        error: error.message,
        timestamp: new Date().toISOString()
      };

      results.push(errorResult);
      errors.push(errorResult);

      // Error callback
      if (onError) {
        onError(errorResult);
      }

      // Continue processing (error isolation pattern from n8n)
      continue;
    }
  }

  console.log(`[BatchProcessor] Batch complete: ${results.filter(r => r.success).length}/${results.length} succeeded`);

  return {
    results: results,
    summary: {
      total: results.length,
      succeeded: results.filter(r => r.success).length,
      failed: results.filter(r => !r.success).length,
      timestamp: new Date().toISOString()
    }
  };
}

/**
 * Analyze scraped content with AI (Gemini)
 * @param {Object} scrapedData - Data from scraper
 * @returns {Promise<Object>} - AI analysis result
 */
async function analyzeWithAI(scrapedData) {
  // Import prompt template
  const prompt = getAnalysisPrompt();

  // Prepare content for AI
  const content = prompt.replace('{{ PRODUCT_CONTENT }}', scrapedData.markdownContent);

  try {
    // Call Gemini API (using n8n's model: gemini-3-flash-preview)
    const response = await fetch('https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-goog-api-key': process.env.GEMINI_API_KEY || ''
      },
      body: JSON.stringify({
        contents: [{
          parts: [{
            text: content
          }]
        }]
      })
    });

    if (!response.ok) {
      throw new Error(`Gemini API error: ${response.status}`);
    }

    const data = await response.json();

    return {
      success: true,
      content: data.candidates?.[0]?.content?.parts?.[0]?.text || '',
      model: 'gemini-3-flash-preview',
      timestamp: new Date().toISOString()
    };

  } catch (error) {
    return {
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Extract structured data from AI response
 * Matching n8n "Code - 提取结构化数据" node logic (v81)
 * @param {string} aiResponse - AI analysis text
 * @param {string} asin - Product ASIN
 * @returns {Object} - Extracted structured data
 */
function extractStructuredData(aiResponse, asin) {
  // Initialize with defaults (matching n8n pattern)
  let title = '未知';
  let price = '未知';
  let rating = '未知';

  // Extract title
  const titlePatterns = [
    /产品标题[：:]+([^\n]+)/,
    /Title[：:]+([^\n]+)/
  ];
  for (const pattern of titlePatterns) {
    const match = aiResponse.match(pattern);
    if (match) {
      title = match[1].trim();
      break;
    }
  }

  // Extract price
  const pricePatterns = [
    /价格[：:]+[^0-9]*([0-9]+\.?[0-9]*)/,
    /Price[：:]+[^0-9]*([0-9]+\.?[0-9]*)/
  ];
  for (const pattern of pricePatterns) {
    const match = aiResponse.match(pattern);
    if (match) {
      price = match[1];
      break;
    }
  }

  // Extract rating
  const ratingPatterns = [
    /评分[：:]+[^0-9]*([0-9]+\.?[0-9]*)/,
    /Rating[：:]+[^0-9]*([0-9]+\.?[0-9]*)/
  ];
  for (const pattern of ratingPatterns) {
    const match = aiResponse.match(pattern);
    if (match) {
      rating = match[1];
      break;
    }
  }

  return {
    asin: asin,
    title: title,
    price: price,
    rating: rating,
    fullAnalysis: aiResponse
  };
}

/**
 * Format results for Google Sheets output
 * @param {Array} results - Processed results
 * @returns {Array} - Formatted rows for Google Sheets
 */
function formatForGoogleSheets(results) {
  const rows = [];

  // Header row
  rows.push([
    'ASIN',
    '产品标题',
    '价格',
    '评分',
    '文案分析摘要',
    '视觉分析摘要',
    '评论分析摘要',
    '市场分析摘要'
  ]);

  // Data rows (successful results only)
  for (const result of results) {
    if (!result.success) continue;

    const extracted = result.extracted;
    const analysis = result.analysis.content;

    // Extract summaries from analysis (300 chars each)
    rows.push([
      extracted.asin,
      extracted.title,
      extracted.price,
      extracted.rating,
      extractSummary(analysis, '文案构建', 300),
      extractSummary(analysis, '视觉资产', 300),
      extractSummary(analysis, '评论', 300),
      extractSummary(analysis, '市场', 300)
    ]);
  }

  return rows;
}

/**
 * Format results for Markdown report
 * @param {Array} results - Processed results
 * @returns {string} - Complete Markdown report
 */
function formatMarkdownReport(results) {
  const date = new Date().toISOString().split('T')[0];
  const successful = results.filter(r => r.success);

  let markdown = `# 亚马逊竞品分析报告\n\n`;
  markdown += `## 分析概览\n\n`;
  markdown += `- 分析产品数：${successful.length}\n`;
  markdown += `- 分析时间：${date}\n`;
  markdown += `- 成功率：${successful.length}/${results.length}\n\n`;
  markdown += `---\n\n`;

  for (let i = 0; i < successful.length; i++) {
    const result = successful[i];
    const extracted = result.extracted || {};

    // Use top-level asin and analysis, with fallback to extracted
    const asin = result.asin || extracted.asin || '未知';
    const title = extracted.title || '未知';
    const price = extracted.price || '未知';
    const rating = extracted.rating || '未知';
    const analysis = result.analysis || extracted.fullAnalysis || '暂无分析';

    markdown += `## 产品 ${i + 1}: ${asin}\n\n`;
    markdown += `### 基本信息\n`;
    markdown += `- 标题：${title}\n`;
    markdown += `- 价格：${price}\n`;
    markdown += `- 评分：${rating}\n\n`;
    markdown += `### 详细分析\n\n`;
    markdown += `${analysis}\n\n`;
    markdown += `---\n\n`;
  }

  // Failed items
  const failed = results.filter(r => !r.success);
  if (failed.length > 0) {
    markdown += `## 处理失败的产品\n\n`;
    for (const item of failed) {
      markdown += `- **${item.input}**: ${item.error}\n`;
    }
  }

  return markdown;
}

/**
 * Extract summary section from analysis
 * @param {string} analysis - Full analysis text
 * @param {string} keyword - Section keyword
 * @param {number} maxLength - Maximum length
 * @returns {string} - Extracted summary
 */
function extractSummary(analysis, keyword, maxLength) {
  // Find section containing keyword
  const index = analysis.indexOf(keyword);
  if (index === -1) {
    return analysis.substring(0, maxLength) + '...';
  }

  // Extract around the keyword
  const start = Math.max(0, index - 50);
  const end = Math.min(analysis.length, index + maxLength);
  let summary = analysis.substring(start, end).trim();

  if (summary.length > maxLength) {
    summary = summary.substring(0, maxLength) + '...';
  }

  return summary;
}

/**
 * Get analysis prompt from file
 * @returns {string} - Prompt template
 */
function getAnalysisPrompt() {
  // This would read from prompts/analysis-prompt-base.md
  // For now, return a placeholder
  return `你是亚马逊竞品分析专家。请分析以下产品页面的内容：

{{ PRODUCT_CONTENT }}

# Role / 身份角色
你是一位拥有 10 年经验的"亚马逊顶级运营总监"和"品牌战略官"...

[Full prompt from analysis-prompt-base.md]`;
}

// Export functions
module.exports = {
  processBatch,
  parseGoogleSheetsSpec,
  analyzeWithAI,
  extractStructuredData,
  formatForGoogleSheets,
  formatMarkdownReport
};
