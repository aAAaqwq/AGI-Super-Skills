#!/usr/bin/env python3
"""
News Fetcher - Python implementation
Fetches news from web_search and web_fetch tools
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class NewsFetcher:
    """Fetches and aggregates news from multiple sources"""

    def __init__(self, config_path=None):
        """Initialize news fetcher with configuration"""
        if config_path is None:
            config_path = Path(__file__).parent / "news-sources.conf"

        self.config_path = Path(config_path)
        self.sources = self._load_sources()
        self.articles = []

    def _load_sources(self):
        """Load news sources from configuration file"""
        sources = []

        if not self.config_path.exists():
            print(f"Warning: Config file not found: {self.config_path}")
            return self._get_default_sources()

        with open(self.config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Parse source configuration
                parts = line.split('|')
                if len(parts) >= 4:
                    source = {
                        'name': parts[0].strip(),
                        'url': parts[1].strip(),
                        'method': parts[2].strip(),
                        'priority': int(parts[3].strip()) if parts[3].strip().isdigit() else 5,
                        'selector': parts[4].strip() if len(parts) > 4 else ''
                    }
                    sources.append(source)

        return sorted(sources, key=lambda x: -x['priority'])

    def _get_default_sources(self):
        """Return default news sources if config not found"""
        return [
            {
                'name': '机器之心',
                'url': 'https://www.jiqizhixin.com/',
                'method': 'web_search',
                'priority': 10,
                'selector': 'ai artificial intelligence'
            },
            {
                'name': 'TechCrunch',
                'url': 'https://techcrunch.com/',
                'method': 'web_search',
                'priority': 8,
                'selector': 'artificial intelligence AI'
            }
        ]

    def fetch_from_search(self, source, count=5):
        """
        Fetch articles using web_search
        Note: This is a placeholder - actual implementation would call OpenClaw's web_search tool
        """
        print(f"[SEARCH] {source['name']}: {source['selector']}")

        # In real implementation, this would call:
        # results = web_search(query=source['selector'], count=count)

        # Placeholder results
        return [
            {
                'title': f"Sample article from {source['name']}",
                'url': f"{source['url']}article/1",
                'snippet': f"Latest AI news from {source['name']}",
                'source': source['name'],
                'published': '2 hours ago',
                'fetched_at': datetime.now().isoformat()
            }
        ]

    def fetch_from_url(self, source):
        """
        Fetch articles using web_fetch
        Note: This is a placeholder - actual implementation would call OpenClaw's web_fetch tool
        """
        print(f"[FETCH] {source['name']}: {source['url']}")

        # In real implementation, this would call:
        # content = web_fetch(url=source['url'], extract_mode='markdown')
        # Then parse HTML to extract articles

        return []

    def fetch_all(self, max_per_source=5):
        """Fetch news from all configured sources"""
        all_articles = []

        for source in self.sources:
            try:
                if source['method'] == 'web_search':
                    articles = self.fetch_from_search(source, count=max_per_source)
                elif source['method'] == 'web_fetch':
                    articles = self.fetch_from_url(source)
                else:
                    print(f"Unknown method: {source['method']}")
                    continue

                all_articles.extend(articles)

            except Exception as e:
                print(f"Error fetching from {source['name']}: {e}")
                continue

        self.articles = all_articles
        return all_articles

    def deduplicate(self):
        """Remove duplicate articles based on URL similarity"""
        seen_urls = set()
        unique_articles = []

        for article in self.articles:
            url = article.get('url', '')
            # Simple deduplication by exact URL
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)

        self.articles = unique_articles
        return unique_articles

    def filter_by_keywords(self, keywords):
        """Filter articles by AI/tech keywords"""
        if not keywords:
            return self.articles

        keywords_lower = [k.lower() for k in keywords]
        filtered = []

        for article in self.articles:
            title = article.get('title', '').lower()
            snippet = article.get('snippet', '').lower()

            if any(kw in title or kw in snippet for kw in keywords_lower):
                filtered.append(article)

        self.articles = filtered
        return filtered

    def sort_by_recency(self):
        """Sort articles by publication time"""
        # In real implementation, parse dates and sort
        # For now, keep original order
        pass

    def get_top_articles(self, n=5):
        """Get top N articles"""
        return self.articles[:n]

    def to_json(self, output_path=None):
        """Export articles to JSON"""
        data = {
            'articles': self.articles,
            'total': len(self.articles),
            'timestamp': datetime.now().isoformat()
        }

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        return json.dumps(data, ensure_ascii=False, indent=2)


def main():
    """Main entry point for testing"""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch news from multiple sources')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--count', '-n', type=int, default=5, help='Number of articles per source')
    args = parser.parse_args()

    # Initialize fetcher
    fetcher = NewsFetcher(config_path=args.config)

    # Fetch news
    print(f"Fetching from {len(fetcher.sources)} sources...")
    fetcher.fetch_all(max_per_source=args.count)

    # Deduplicate
    fetcher.deduplicate()

    # Output
    print(f"\nFetched {len(fetcher.articles)} articles")
    output = fetcher.to_json(output_path=args.output)

    if args.output:
        print(f"Saved to: {args.output}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
