import asyncio
import os
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def scrape_rules_directly():
    # Folder to save the rules
    output_dir = "data/raw_markdown/rules"
    os.makedirs(output_dir, exist_ok=True)

    browser_config = BrowserConfig(headless=True, verbose=True)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED, # Enable cache to save time on retries
        delay_before_return_html=2.0
    )

    # Generate list of URLs to try (e.g., Rule 1 to 10)
    # Note: Some rules have sub-letters like '2da', but let's start with numbers
    test_numbers = [str(i) for i in range(1, 11)] 
    base_url = "https://incometaxindia.gov.in/pages/rules/rule-"
    urls = [f"{base_url}{n}.aspx" for n in test_numbers]

    async with AsyncWebCrawler(config=browser_config) as crawler:
        print(f"--- Attempting to scrape {len(urls)} rules directly ---")
        
        # arun_many is very fast - it scrapes in parallel
        results = await crawler.arun_many(urls, config=run_config)

        for i, result in enumerate(results):
            url = urls[i]
            if result.success and "Rule not found" not in result.markdown:
                filename = f"rule_{test_numbers[i]}.md"
                with open(os.path.join(output_dir, filename), "w") as f:
                    f.write(result.markdown)
                print(f"✅ Success: Saved {filename}")
            else:
                print(f"❌ Failed or Empty: Rule {test_numbers[i]}")

if __name__ == "__main__":
    asyncio.run(scrape_rules_directly())