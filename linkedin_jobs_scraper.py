import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
import json

import os
from pathlib import Path

# Create a persistent user data directory
user_data_dir = os.path.join(Path.home(), ".crawl4ai", "linkedin_profile")
os.makedirs(user_data_dir, exist_ok=True)

# Configure browser settings with persistent profile
browser_config = BrowserConfig(
    headless=False,  # Keep False for initial login
    verbose=True,
    viewport_width=1920,
    viewport_height=1080,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    },
    user_data_dir=user_data_dir,  # Add persistent profile directory
    use_persistent_context=True    # Enable persistent context
)

async def scrape_linkedin_jobs(search_query, location=""):
    # Define the schema for job data extraction
    schema = {
        "name": "LinkedIn Jobs",
        "baseSelector": ".jobs-search-results__list-item",
        "fields": [
            {
                "name": "title",
                "selector": ".job-card-list__title",
                "type": "text"
            },
            {
                "name": "company",
                "selector": ".job-card-container__company-name",
                "type": "text"
            },
            {
                "name": "location",
                "selector": ".job-card-container__metadata-item",
                "type": "text"
            },
            {
                "name": "link",
                "selector": ".job-card-list__title",
                "type": "attribute",
                "attribute": "href"
            },
            {
                "name": "posted_time",
                "selector": ".job-card-container__listed-time",
                "type": "text"
            }
        ]
    }

    # Configure extraction strategy
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

    # Configure crawler with improved scrolling and wait time
    run_config = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        cache_mode=CacheMode.BYPASS,
        js_code=[
            """
            (async () => {
                const delay = ms => new Promise(r => setTimeout(r, ms));
                
                // Initial wait for page load
                await delay(2000);
                
                // Scroll multiple times to load more content
                let lastHeight = 0;
                let unchangedCount = 0;
                const MAX_UNCHANGED = 3;
                
                while (unchangedCount < MAX_UNCHANGED) {
                    window.scrollTo(0, document.body.scrollHeight);
                    await delay(1500 + Math.random() * 1000);  // Randomized delay
                    
                    const newHeight = document.body.scrollHeight;
                    if (newHeight === lastHeight) {
                        unchangedCount++;
                    } else {
                        unchangedCount = 0;
                    }
                    lastHeight = newHeight;
                    
                    // Click "Show more" buttons if they exist
                    const showMoreButtons = document.querySelectorAll('button.infinite-scroller__show-more-button');
                    showMoreButtons.forEach(button => button.click());
                }
                
                // Final wait for content to load
                await delay(2000);
            })();
            """
        ],
        delay_before_return_html=5000,  # Wait 5 seconds before extracting content
        wait_until="networkidle",  # Wait for network requests to finish
        page_timeout=30000,        # 30 second timeout
        ignore_body_visibility=True,
        simulate_user=True,        # Help avoid detection
        override_navigator=True    # Help avoid detection
    )

    # Format search URL (using LinkedIn's public jobs page)
    search_query = search_query.replace(' ', '%20')
    location = location.replace(' ', '%20')
    url = f"https://www.linkedin.com/jobs/search?keywords={search_query}&location={location}&trk=public_jobs_jobs-search-bar_search-submit&position=1&pageNum=0"

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

            try:
                # Parse and format results
                jobs = json.loads(result.extracted_content)
                return jobs
            except json.JSONDecodeError:
                print("No jobs found or error parsing results")
                return []

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return []

async def login_to_linkedin():
    """Handle the LinkedIn login process"""
    print("\nStarting LinkedIn Login Process")
    print("===============================")
    print("1. Opening browser...")
    
    # Create a proper CrawlerRunConfig for login
    login_config = CrawlerRunConfig(
        delay_before_return_html=15000,  # Longer delay for login
        js_code=["""
            (async () => {
                const delay = ms => new Promise(r => setTimeout(r, ms));
                
                // Wait for initial page load
                await delay(3000);
                
                // Try multiple selectors for the sign-in button
                const selectors = [
                    '.nav__button-secondary',
                    'a[href*="signin"]',
                    'button[data-tracking-control-name*="sign-in"]'
                ];
                
                for (const selector of selectors) {
                    const button = document.querySelector(selector);
                    if (button) {
                        console.log('Found login button:', selector);
                        button.click();
                        break;
                    }
                }
                
                await delay(2000);  // Wait after click
            })();
        """],
        cache_mode=CacheMode.BYPASS,  # Important: bypass cache for login
        wait_until="networkidle",     # Wait for network to be idle
        page_timeout=60000,           # Increase timeout for login
        ignore_body_visibility=True    # Don't wait for body visibility
    )

    try:
        # Initialize the crawler with both configs
        crawler = AsyncWebCrawler(config=browser_config)
        async with crawler as browser:
            print("2. Navigating to LinkedIn...")
            # Pass the login_config to arun
            result = await browser.arun(
                url="https://www.linkedin.com",
                config=login_config  # Pass the config here
            )
            print("3. Browser navigation complete")
            print("4. Please log in to LinkedIn in the opened browser")
            print("5. After logging in, the script will save your session")
            input("\nPress Enter once you have logged in to continue...")
            return True
            
    except Exception as e:
        print(f"Error during login process: {str(e)}")
        return False

async def main():
    print("\nLinkedIn Jobs Scraper")
    print("====================")
    
    # First handle login
    if not await login_to_linkedin():
        print("Failed to complete login process")
        return

    print("\nStarting Job Search")
    print("==================")
    print("1. Searching for Python developer jobs in United States...")
    
    try:
        jobs = await scrape_linkedin_jobs("python developer", "United States")
    except Exception as e:
        print(f"Error during job search: {str(e)}")
        return
    
    if not jobs:
        print("\nNo jobs were found. This could be due to:")
        print("1. Not logged in to LinkedIn (please run again and log in)")
        print("2. No matching jobs in the specified location")
        print("3. Network connectivity issues")
        return
    
    # Print results
    print(f"\nFound {len(jobs)} jobs:")
    for job in jobs:
        print("\n---")
        print(f"Title: {job['title']}")
        print(f"Company: {job['company']}")
        print(f"Location: {job['location']}")
        print(f"Posted: {job['posted_time']}")
        print(f"Link: {job['link']}")

if __name__ == "__main__":
    asyncio.run(main())