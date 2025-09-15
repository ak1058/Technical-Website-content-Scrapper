import requests
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
import time
import json
import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from markdownify import markdownify as md
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ContentItem:
    title: str
    content: str
    content_type: str
    source_url: str

@dataclass
class ScrapingResult:
    site: str
    items: List[ContentItem]
    errors: List[str] = None

class UniversalWebScraper:
    def __init__(self, delay: float = 1.0, timeout: int = 30, respect_robots: bool = False):
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.respect_robots = respect_robots
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Content patterns for URL classification
        self.content_patterns = [
            r'/blog/', r'/article/', r'/post/', r'/guide/', r'/tutorial/', r'/news/',r'/case-study/', r'/insights/', r'/press/',
            r'/learn/', r'/resources/', r'/docs/', r'/knowledge/', r'/tech/', r'/updates?/', r'/faq/',
            r'/\d{4}/\d{2}/', r'/\d{4}/\d{2}/\d{2}/',  # Date patterns
            r'/(p|posts?|articles?|guides?)/',
        ]
        
        self.skip_patterns = [
            r'/category/', r'/tag/', r'/author/', r'/archive/',r'/book-a-demo/',r'/book',
            r'/(contact|about|privacy|terms|cookie)', r'/feed', r'/rss',
            r'/(login|register|signup)', r'/search', r'/admin/',
            r'\.(pdf|jpg|jpeg|png|gif|css|js|ico)$'
        ]
        
    def scrape_site(self, url: str) -> ScrapingResult:
        """Main entry point - scrape entire site"""
        logger.info(f"Starting to scrape: {url}")
        
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        base_url = self._get_base_url(url)
        errors = []
        
        try:
            # Step 1: Check robots.txt
            if self.respect_robots and not self._check_robots_txt(base_url):
                return ScrapingResult(url, [], [f"Robots.txt disallows scraping"])
            
            # Step 2: Discover URLs
            urls = self._discover_urls(url, base_url)
            logger.info(f"Discovered {len(urls)} potential content URLs")
            
            # Step 3: Extract content from each URL
            items = []
            url_list = list(urls)[:20]  # Convert set to list and limit to 20 for testingwe can set more number as many as we can
            logger.info(f"Testing first {len(url_list)} URLs: {url_list[:3]}...")
            
            for i, content_url in enumerate(url_list):
                try:
                    logger.info(f"Processing URL {i+1}/{len(url_list)}: {content_url}")
                    item = self._extract_content(content_url)
                    if item:
                        if self._is_quality_content(item):
                            items.append(item)
                            logger.info(f"✅ Successfully extracted: {item.title[:50]}...")
                        else:
                            logger.info(f"❌ Content didn't pass quality check")
                    else:
                        logger.info(f"❌ No content extracted")
                    time.sleep(self.delay)
                except Exception as e:
                    error_msg = f"Failed to extract {content_url}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    
            logger.info(f"Successfully extracted {len(items)} items")
            return ScrapingResult(url, items, errors)
            
        except Exception as e:
            return ScrapingResult(url, [], [f"Major error: {str(e)}"])
    
    def _get_base_url(self, url: str) -> str:
        """Get base URL from full URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def _check_robots_txt(self, base_url: str) -> bool:
        """Check if we're allowed to scrape based on robots.txt"""
        try:
            rp = RobotFileParser()
            rp.set_url(urljoin(base_url, '/robots.txt'))
            rp.read()
            return rp.can_fetch('*', base_url)
        except:
            return True  
    
    def _discover_urls(self, start_url: str, base_url: str) -> Set[str]:
        """Discover all content URLs using multiple strategies"""
        urls = set()
        
        # Strategy 1: Try sitemap.xml
        sitemap_urls = self._get_sitemap_urls(base_url)
        urls.update(sitemap_urls)
        logger.info(f"Found {len(sitemap_urls)} URLs from sitemap")
        
        # Strategy 2: Crawl from start page
        crawled_urls = self._crawl_for_urls(start_url, base_url, max_depth=2)  # Reduced depth for testing
        urls.update(crawled_urls)
        logger.info(f"Found {len(crawled_urls)} URLs from crawling")
        
        # Filter and classify URLs
        content_urls = self._filter_content_urls(urls, base_url)
        return content_urls
    
    def _get_sitemap_urls(self, base_url: str) -> Set[str]:
        """Extract URLs from sitemap.xml and robots.txt"""
        urls = set()
        sitemap_candidates = [
            '/sitemap.xml', '/sitemap_index.xml', '/sitemap-index.xml',
            '/sitemaps.xml'
        ]

        # Step 1: Try common sitemap locations
        for sitemap_path in sitemap_candidates:
            try:
                response = self.session.get(urljoin(base_url, sitemap_path), timeout=self.timeout)
                if response.status_code == 200 and 'xml' in response.headers.get('content-type', '').lower():
                    urls.update(self._parse_sitemap_xml(response.text))
                    break  # stop once we find a valid sitemap
            except Exception as e:
                logger.debug(f"Failed to get sitemap {sitemap_path}: {e}")

        # Step 2: Parse robots.txt for Sitemap entries (if direct sitemap not found)
        try:
            robots_url = urljoin(base_url, '/robots.txt')
            response = self.session.get(robots_url, timeout=self.timeout)
            if response.status_code == 200:
                for line in response.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line.split(":", 1)[1].strip()
                        try:
                            resp = self.session.get(sitemap_url, timeout=self.timeout)
                            if resp.status_code == 200 and 'xml' in resp.headers.get('content-type', '').lower():
                                urls.update(self._parse_sitemap_xml(resp.text))
                        except Exception as e:
                            logger.debug(f"Failed to fetch sitemap from robots.txt {sitemap_url}: {e}")
        except Exception as e:
            logger.debug(f"Failed to read robots.txt: {e}")

        return urls

    def _parse_sitemap_xml(self, xml_content: str) -> Set[str]:
        """Parse sitemap XML and extract URLs"""
        urls = set()
        try:
            root = ET.fromstring(xml_content)
            # Handle different sitemap namespaces
            for url_elem in root.iter():
                if url_elem.tag.endswith('loc'):
                    urls.add(url_elem.text)
        except Exception as e:
            logger.debug(f"Failed to parse sitemap XML: {e}")
        return urls
    
    def _crawl_for_urls(self, start_url: str, base_url: str, max_depth: int = 1, max_urls: int = 200) -> Set[str]:
        """Optimized crawl to discover internal URLs"""
        urls = set()
        visited = set()
        to_visit = [(start_url, 0)]

        # Common "trap" patterns to skip
        bad_patterns = ["?page=", "?sort=", "?utm", "/login", "/cart", "/account", "/signup"]

        while to_visit and len(urls) < max_urls:
            url, depth = to_visit.pop(0)

            if depth > max_depth or url in visited:
                continue
            visited.add(url)

            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code != 200:
                    continue

                # Only process HTML pages
                if "text/html" not in response.headers.get("content-type", ""):
                    continue

                soup = BeautifulSoup(response.content, "html.parser")

                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    full_url = urljoin(url, href)

                    # Only follow internal URLs
                    if not self._is_internal_url(full_url, base_url):
                        continue

                    # Skip bad/trap URLs
                    if any(bad in full_url.lower() for bad in bad_patterns):
                        continue

                    if full_url not in visited:
                        urls.add(full_url)
                        if depth < max_depth and len(urls) < max_urls:
                            to_visit.append((full_url, depth + 1))

            except Exception as e:
                logger.debug(f"Failed to crawl {url}: {e}")

        return urls
    
    def _is_internal_url(self, url: str, base_url: str) -> bool:
        """Check if URL belongs to the same domain"""
        return urlparse(url).netloc == urlparse(base_url).netloc
    
    def _filter_content_urls(self, urls: Set[str], base_url: str) -> Set[str]:
        """Filter URLs to keep only content pages"""
        content_urls = set()
        
        for url in urls:
            # Skip if matches skip patterns
            if any(re.search(pattern, url, re.IGNORECASE) for pattern in self.skip_patterns):
                continue
                
            # Include if matches content patterns OR has potential content structure
            if (any(re.search(pattern, url, re.IGNORECASE) for pattern in self.content_patterns) or
                self._looks_like_content_url(url)):
                content_urls.add(url)
        
        return content_urls
    
    def _looks_like_content_url(self, url: str) -> bool:
        """Heuristic to detect content URLs"""
        path = urlparse(url).path.lower()
        
        # Long paths often indicate content
        if len(path.split('/')) >= 3:
            return True
            
        # Has meaningful slug
        if re.search(r'/[\w-]{10,}', path):
            return True
            
        return False
    
    def _extract_content(self, url: str) -> Optional[ContentItem]:
        """Extract content from a single URL using multiple strategies"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                return None
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try multiple extraction strategies in order
            strategies = [
                self._extract_with_structured_data,
                self._extract_with_article_tag,
                self._extract_with_heuristics,
                self._extract_fallback
            ]
            
            for strategy in strategies:
                result = strategy(soup, url)
                if result:
                    return result
                    
        except Exception as e:
            logger.debug(f"Failed to extract content from {url}: {e}")
            
        return None
    
    def _extract_with_structured_data(self, soup: BeautifulSoup, url: str) -> Optional[ContentItem]:
        """Extract using JSON-LD structured data"""
        try:
            json_ld = soup.find('script', {'type': 'application/ld+json'})
            if json_ld:
                data = json.loads(json_ld.string)
                if isinstance(data, list):
                    data = data[0]
                    
                if data.get('@type') in ['Article', 'BlogPosting', 'NewsArticle']:
                    title = data.get('headline', '')
                    content = data.get('articleBody', '')
                    if title and content:
                        return ContentItem(
                            title=title,
                            content=md(content),
                            content_type=self._classify_content_type(url, title, content),
                            source_url=url
                        )
        except:
            pass
        return None
    
    def _extract_with_article_tag(self, soup: BeautifulSoup, url: str) -> Optional[ContentItem]:
        """Extract using HTML5 article tag"""
        article = soup.find('article')
        if article:
            title = self._extract_title(soup, article)
            content = self._clean_html_content(article)
            
            if title and content and len(str(content).strip()) > 200:
                return ContentItem(
                    title=title,
                    content=md(str(content)),
                    content_type=self._classify_content_type(url, title, str(content)),
                    source_url=url
                )
        return None
    
    def _extract_with_heuristics(self, soup: BeautifulSoup, url: str) -> Optional[ContentItem]:
        """Extract using content detection heuristics"""
        # Look for main content containers
        main_selectors = [
            'main', '.main', '#main', '.content', '#content',
            '.post-content', '.entry-content', '.article-content',
            '.blog-post', '.single-post'
        ]
        
        for selector in main_selectors:
            container = soup.select_one(selector)
            if container:
                title = self._extract_title(soup, container)
                content = self._clean_html_content(container)
                
                if title and content and len(content.get_text().strip()) > 200:
                    return ContentItem(
                        title=title,
                        content=md(str(content)),
                        content_type=self._classify_content_type(url, title, str(content)),
                        source_url=url
                    )
        return None
    
    def _extract_fallback(self, soup: BeautifulSoup, url: str) -> Optional[ContentItem]:
        """Last resort extraction method"""
        # Remove unwanted elements
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            elem.decompose()
        
        title = self._extract_title(soup)
        
        # Find the element with most text content
        text_elements = []
        for elem in soup.find_all(['div', 'section', 'article']):
            text_length = len(elem.get_text().strip())
            if text_length > 300:
                text_elements.append((elem, text_length))
        
        if text_elements:
            # Get the element with most content
            best_elem = max(text_elements, key=lambda x: x[1])[0]
            content = self._clean_html_content(best_elem)
            
            if title and content:
                return ContentItem(
                    title=title,
                    content=md(str(content)),
                    content_type=self._classify_content_type(url, title, str(content)),
                    source_url=url
                )
        return None
    
    def _extract_title(self, soup: BeautifulSoup, container: BeautifulSoup = None) -> str:
        """Extract title from page"""
        if container:
            # Look for title in container first
            title_elem = container.find(['h1', 'h2'])
            if title_elem:
                return title_elem.get_text().strip()
        
        # Fallback to page title
        title_elem = soup.find('title')
        if title_elem:
            return title_elem.get_text().strip()
        
        # Try meta title
        meta_title = soup.find('meta', property='og:title')
        if meta_title:
            return meta_title.get('content', '').strip()
            
        return "Untitled"
    
    def _clean_html_content(self, element) -> BeautifulSoup:
        """Clean HTML content while preserving structure"""
        # Create a copy to avoid modifying the original
        element_copy = BeautifulSoup(str(element), 'html.parser')
        
        # Remove unwanted elements
        for unwanted in element_copy.find_all(['script', 'style', 'nav', 'header', 'footer']):
            unwanted.decompose()
        
        # Remove ads and social media
        for ad_elem in element_copy.find_all(attrs={'class': re.compile(r'ad|advertisement|social|share', re.I)}):
            ad_elem.decompose()
            
        return element_copy
    
    def _classify_content_type(self, url: str, title: str, content: str) -> str:
        """Classify content type based on URL and content analysis"""
        url_lower = url.lower()
        title_lower = title.lower()
        
        if any(term in url_lower for term in ['tutorial', 'guide', 'how-to', 'learn']):
            return 'tutorial'
        elif any(term in url_lower for term in ['blog', 'post', 'article']):
            return 'blog'
        elif 'podcast' in url_lower or 'podcast' in title_lower:
            return 'podcast_transcript'
        else:
            return 'other'
    
    def _is_quality_content(self, item: ContentItem) -> bool:
        """Check if content meets quality thresholds"""
        # Convert markdown back to text for analysis
        content_text = BeautifulSoup(item.content, 'html.parser').get_text()
        
        # Quality checks
        if len(content_text.strip()) < 100:  # Lowered threshold for testing
            logger.debug(f"Content too short: {len(content_text)} chars")
            return False
        
        if len(item.title.strip()) < 3:  # Lowered threshold
            logger.debug(f"Title too short: {item.title}")
            return False
            
        return True


def main():
    scraper = UniversalWebScraper(delay=0.5, respect_robots=False)
    
    # Test with a sample URL
    test_url = input("Enter URL to scrape: ") or "https://interviewing.io/blog"
    print(f"🚀 Starting scrape of: {test_url}")
    
    
    result = scraper.scrape_site(test_url)
    

    output = {
        "site": result.site,
        "items": [
            {
                "title": item.title,
                "content": item.content,  
                "content_type": item.content_type,
                "source_url": item.source_url
            }
            for item in result.items
        ],
        "summary": {
            "total_items": len(result.items),
            "total_errors": len(result.errors) if result.errors else 0,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    
    # Save full JSON output to file
    json_filename = f"scraped_data_{urlparse(test_url).netloc}_{int(time.time())}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Save markdown content to separate file (just for seeing purpose how it is looks like)
    md_filename = f"scraped_content_{urlparse(test_url).netloc}_{int(time.time())}.md"
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write(f"# Scraped Content from {result.site}\n\n")
        f.write(f"**Scraped at:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Total items:** {len(result.items)}  \n\n")
        f.write("---\n\n")
        
        for i, item in enumerate(result.items, 1):
            f.write(f"## Item {i}: {item.title}\n\n")
            f.write(f"**Source:** {item.source_url}  \n")
            f.write(f"**Type:** {item.content_type}  \n")
            f.write(f"**Content Length:** {len(item.content)} characters  \n\n")
            f.write("### Content:\n\n")
            f.write(item.content)
            f.write("\n\n---\n\n")
        
        if result.errors:
            f.write("## Errors Encountered\n\n")
            for error in result.errors:
                f.write(f"- {error}\n")
    
    # Print summary to console
    print(f"\n✅ Scraping completed!")
    print(f"📄 Full JSON saved to: {json_filename}")
    print(f"📝 Markdown content saved to: {md_filename}")
    print(f"📊 Found {len(result.items)} items")
    
    # Show brief preview
    if result.items:
        print(f"\n📋 Preview of items found:")
        for i, item in enumerate(result.items[:3], 1):
            print(f"{i}. {item.title[:60]}{'...' if len(item.title) > 60 else ''}")
            print(f"   Type: {item.content_type} | Length: {len(item.content)} chars")
    
    if result.errors:
        print(f"\n⚠️ {len(result.errors)} errors encountered (see .md file for details)")

if __name__ == "__main__":
    main()