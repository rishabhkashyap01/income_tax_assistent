import asyncio
import os
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# 1. Configuration
TARGET_URLS = [
    f"https://incometaxindia.gov.in/Pages/acts/index.aspx", # Main Services page 
]
OUTPUT_DIR = "data/raw_markdown"

async def scrape_tax_docs():
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 2. Browser & Crawler Config
    browser_config = BrowserConfig(headless=True, verbose=True)
    
    # We use a markdown generator to ensure the output is LLM-friendly
    # Configuration to handle the complex layout of a government portal
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(
            options={
                "ignore_links": False, # Keep links initially to find PDF documents
                "remove_comments": True,
                "body_width": 120
            }
        )
    )

    print(f"--- Starting Scrape of {len(TARGET_URLS)} URLs ---")

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in TARGET_URLS:
            print(f"Scraping: {url}")
            result = await crawler.arun(url=url, config=run_config)
            
            if result.success:
                # 3. Save the result as a .md file
                filename = url.split("/")[-1] + ".md"
                file_path = os.path.join(OUTPUT_DIR, filename)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(result.markdown)
                print(f"Saved: {file_path}")
            else:
                print(f"Failed to scrape {url}: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(scrape_tax_docs())