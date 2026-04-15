/**
 * Amazon Product Scraper using Olostep API
 *
 * Based on n8n workflow "Olostep API" node configuration (v81)
 * Reference: 工作流配置.json
 *
 * Features:
 * - Scrapes Amazon product pages (title, price, rating, reviews, images)
 * - Returns structured data (markdown)
 * - Error handling with retry logic
 */

// Olostep API Configuration
const OLOSTEP_API_ENDPOINT = 'https://api.olostep.com/v1/scrapes';
const OLOSTEP_API_KEY = process.env.OLOSTEP_API_KEY || '';

// Amazon URL patterns
const AMAZON_PATTERNS = {
  asin: /\/dp\/([A-Z0-9]{10})/i,
  product_url: /amazon\.(com|co\.uk|de|es|fr|it|ca|co\.jp)\/.*\/([A-Z0-9]{10})/i
};

/**
 * Extract ASIN from various input formats
 * @param {string} input - ASIN, URL, or product identifier
 * @returns {string|null} - Extracted ASIN or null
 */
function extractASIN(input) {
  // Direct ASIN format (10 alphanumeric characters)
  const asinPattern = /^[A-Z0-9]{10}$/i;
  if (asinPattern.test(input.trim())) {
    return input.trim().toUpperCase();
  }

  // Extract from URL
  for (const pattern of Object.values(AMAZON_PATTERNS)) {
    const match = input.match(pattern);
    if (match) {
      return match[1] ? match[1].toUpperCase() : match[2].toUpperCase();
    }
  }

  return null;
}

/**
 * Build Amazon product URL from ASIN
 * @param {string} asin - Amazon product ASIN
 * @param {string} domain - Amazon domain (default: amazon.com)
 * @returns {string} - Full product URL
 */
function buildAmazonURL(asin, domain = 'amazon.com') {
  return `https://www.${domain}/dp/${asin}`;
}

/**
 * Scrape Amazon product using Olostep API
 * @param {string} asin - Amazon product ASIN
 * @param {Object} options - Scraping options
 * @returns {Promise<Object>} - Scraped data
 */
async function scrapeAmazonProduct(asin, options = {}) {
  const {
    domain = 'amazon.com',
    timeout = 120000, // 2 minutes timeout
    retries = 3
  } = options;

  const url = buildAmazonURL(asin, domain);

  // Validate ASIN
  if (!asin) {
    throw new Error('Invalid ASIN provided');
  }

  // Prepare API request (matching n8n HTTP Request node)
  // Only use 'url' parameter - let Olostep auto-detect and scrape all content
  const requestBody = {
    url: url
  };

  // API call with retry logic
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const response = await fetch(OLOSTEP_API_ENDPOINT, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${OLOSTEP_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`Olostep API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      // v1 API returns data.result.markdown_content
      const markdownContent = data.result?.markdown_content ||
                              data.markdown_content || '';

      // Validate response structure
      if (!markdownContent) {
        throw new Error('Invalid response: missing content');
      }

      // Return structured data matching n8n workflow
      return {
        success: true,
        asin: asin,
        url: url,
        markdownContent: markdownContent,
        timestamp: new Date().toISOString()
      };

    } catch (error) {
      console.error(`Scraping attempt ${attempt}/${retries} failed:`, error.message);

      if (attempt === retries) {
        // All retries exhausted
        return {
          success: false,
          asin: asin,
          url: url,
          error: error.message,
          timestamp: new Date().toISOString()
        };
      }

      // Exponential backoff
      await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
    }
  }
}

/**
 * Batch scrape multiple Amazon products
 * @param {string[]} inputs - Array of ASINs or URLs
 * @param {Object} options - Scraping options
 * @returns {Promise<Object[]>} - Array of results
 */
async function batchScrapeAmazon(inputs, options = {}) {
  const results = [];

  // Process in parallel with concurrency limit
  const CONCURRENCY_LIMIT = 5;
  const chunks = [];
  for (let i = 0; i < inputs.length; i += CONCURRENCY_LIMIT) {
    chunks.push(inputs.slice(i, i + CONCURRENCY_LIMIT));
  }

  for (const chunk of chunks) {
    const chunkResults = await Promise.allSettled(
      chunk.map(input => {
        const asin = extractASIN(input);
        if (!asin) {
          return Promise.resolve({
            success: false,
            input: input,
            error: 'Invalid ASIN or URL format'
          });
        }
        return scrapeAmazonProduct(asin, options);
      })
    );

    // Convert PromiseSettledResults to standard format
    for (let i = 0; i < chunkResults.length; i++) {
      const result = chunkResults[i];
      if (result.status === 'fulfilled') {
        results.push(result.value);
      } else {
        results.push({
          success: false,
          input: chunk[i],
          error: result.reason?.message || 'Unknown error'
        });
      }
    }
  }

  return results;
}

// Export for use in skill
module.exports = {
  extractASIN,
  buildAmazonURL,
  scrapeAmazonProduct,
  batchScrapeAmazon
};

// For Node.js ES modules
// export { extractASIN, buildAmazonURL, scrapeAmazonProduct, batchScrapeAmazon };
