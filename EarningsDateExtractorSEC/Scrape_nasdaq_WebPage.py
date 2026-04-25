import asyncio
from crawl4ai import *
import os
import base64

async def extract_Article_body():

    browser_config = BrowserConfig(
        browser_type="chromium",  # Options: "chromium", "firefox", "webkit"
        headless=False,            # Set to False if you want to see the browser window
        viewport_width=1280,
        viewport_height=800,
        verbose=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )
    async with AsyncWebCrawler(config = browser_config) as crawler:

        crawler_config = CrawlerRunConfig(
            screenshot=False,
            verbose=True,
            cache_mode=CacheMode.DISABLED,
            wait_until="domcontentloaded",
            delay_before_return_html = 5,
            log_console=True,
            exclude_social_media_links=True,
            exclude_external_links = True,
            exclude_all_images=True,
            magic=True,
            remove_overlay_elements=True,
            simulate_user=True, 
            scan_full_page=True,  # Tells the crawler to try scrolling the entire page
            scroll_delay=1    # Delay (seconds) between scroll steps
        )

        result = await crawler.arun(
            url = "https://www.nasdaq.com/market-activity/stocks/aapl/earnings",
            config = crawler_config,
            screenshot = True
        )

        # print(result.markdown)
        print(result.cleaned_html)
        # print(result.extracted_content)

if __name__ == "__main__":
    asyncio.run(extract_Article_body())