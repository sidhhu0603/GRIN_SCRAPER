#!/usr/bin/env python3

import os
import time
import zipfile
import requests
import io
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from collections import deque
import json

class GRINWebsiteCrawler:
    def __init__(self, base_url="https://grin.co", max_depth=3):
        self.base_url = base_url
        self.max_depth = max_depth
        self.visited_urls = set()
        self.failed_urls = set()
        self.screenshots_dir = "grin_screenshots"
        self.driver = None
        self.url_queue = deque([(base_url, 0)]) 

        # Create screenshots directory
        os.makedirs(self.screenshots_dir, exist_ok=True)

        self.navigation_selectors = [
            'nav a',
            '.nav a',
            '.navigation a',
            '.menu a',
            '.header a',
            '[role="navigation"] a',
            '.navbar a',
            '.main-nav a',
            '.primary-nav a'
        ]

        self.dropdown_selectors = [
            '.dropdown-menu a',
            '.sub-menu a',
            '.submenu a',
            '.mega-menu a',
            '.dropdown a',
            '.nav-dropdown a'
        ]

    def setup_driver(self):
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        
        # Critical image loading
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        
        
        # Better user agent
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Enable image loading explicitly
        chrome_options.add_argument('--enable-features=NetworkService')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        
        # Memory and cache settings for better image loading
        chrome_options.add_argument('--max_old_space_size=8192')
        chrome_options.add_argument('--memory-pressure-off')
        
        # Explicitly allow images and media
        prefs = {
            "profile.managed_default_content_settings.images": 1,  
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.media_stream": 1
        }
        chrome_options.add_experimental_option("prefs", prefs)

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(120)  
            
            # Enable full-page screenshots
            self.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'mobile': False,
                'width': 1920,
                'height': 1080,
                'deviceScaleFactor': 1,
            })

            print("✓ Chrome driver initialized successfully")
        except Exception as e:
            print(f"✗ Failed to initialize Chrome driver: {e}")
            raise

    def wait_for_complete_page_load(self):
        # Waiting for complete page load including images
        try:
            # Step 1: Wait for basic DOM ready with longer timeout
            WebDriverWait(self.driver, 60).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            # Step 2: Wait for jQuery if present
            try:
                WebDriverWait(self.driver, 20).until(
                    lambda driver: driver.execute_script("return typeof jQuery === 'undefined' || jQuery.active === 0")
                )
            except:
                pass

            # Step 3: CRITICAL - Wait for images with better detection
            self.wait_for_images_to_load()

            # Step 4: Wait for lazy loading content
            self.trigger_all_lazy_loading()

            # Step 5: Wait for network idle with longer timeout
            network_idle_count = 0
            for i in range(40):  # Check for 20 seconds
                try:
                    performance_entries = self.driver.execute_script("""
                        return window.performance.getEntriesByType('resource')
                            .filter(entry => entry.responseEnd === 0).length;
                    """)

                    if performance_entries == 0:
                        network_idle_count += 1
                        if network_idle_count >= 5:
                            break
                    else:
                        network_idle_count = 0

                    time.sleep(0.5)
                except:
                    break

            # Step 6: Force image loading by scrolling to each image
            self.force_load_all_images()

            # Step 7: Final wait for any animations
            time.sleep(8)  
        except Exception as e:
            # Fallback longer wait
            time.sleep(12)

    def wait_for_images_to_load(self):
        #Image loading detection with better error handling
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                
                WebDriverWait(self.driver, 30).until(
                    lambda driver: driver.execute_script("""
                        var images = Array.from(document.querySelectorAll('img'));
                        var backgroundImages = Array.from(document.querySelectorAll('*')).filter(function(el) {
                            var bg = window.getComputedStyle(el).backgroundImage;
                            return bg && bg !== 'none' && bg.includes('url');
                        });
                        
                        var allImages = images.concat(backgroundImages);
                        
                        if (allImages.length === 0) return true;
                        
                        var loadedCount = 0;
                        var errorCount = 0;
                        
                        // Check regular images
                        for (var i = 0; i < images.length; i++) {
                            var img = images[i];
                            if (img.complete) {
                                if (img.naturalHeight > 0) {
                                    loadedCount++;
                                } else {
                                    errorCount++;
                                }
                            }
                        }
                        
                        // For background images, assume loaded after DOM complete
                        loadedCount += backgroundImages.length;
                        
                        var totalImages = images.length + backgroundImages.length;
                        var successfullyLoaded = loadedCount / totalImages;
                        
                        return successfullyLoaded >= 0.7; // 70% threshold
                    """)
                )
                break
                
            except TimeoutException:
                if attempt < max_attempts - 1:
                    time.sleep(5)
                else:
                    pass
            except Exception as e:
                break

    def force_load_all_images(self):
        # Force load images by scrolling to each one and triggering load events
        try:
            # Get all images and scroll to each one
            self.driver.execute_script("""
                var images = document.querySelectorAll('img');
                var loadPromises = [];
                
                for (var i = 0; i < images.length; i++) {
                    var img = images[i];
                    
                    // Scroll image into view
                    img.scrollIntoView({behavior: 'instant', block: 'center'});
                    
                    // Force reload if not loaded
                    if (!img.complete || img.naturalHeight === 0) {
                        var src = img.src;
                        img.src = '';
                        img.src = src;
                    }
                    
                    // Trigger load event
                    var event = new Event('load');
                    img.dispatchEvent(event);
                }
                
                // Also check for lazy loading attributes and trigger them
                var lazyImages = document.querySelectorAll('img[data-src], img[data-lazy-src], img[loading="lazy"]');
                for (var j = 0; j < lazyImages.length; j++) {
                    var lazyImg = lazyImages[j];
                    lazyImg.scrollIntoView({behavior: 'instant', block: 'center'});
                    
                    // Copy data-src to src if present
                    if (lazyImg.dataset.src && !lazyImg.src) {
                        lazyImg.src = lazyImg.dataset.src;
                    }
                    if (lazyImg.dataset.lazySrc && !lazyImg.src) {
                        lazyImg.src = lazyImg.dataset.lazySrc;
                    }
                }
            """)
            
            time.sleep(5)  
            
        except Exception as e:
            pass

    def trigger_all_lazy_loading(self):
        # Comprehensive lazy loading trigger
        try:
            
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            scroll_positions = []
            for i in range(0, total_height + viewport_height, 150):  
                scroll_positions.append(min(i, total_height))
            
            scroll_positions.extend([0, total_height * 0.25, total_height * 0.5, total_height * 0.75, total_height])
            scroll_positions = sorted(set(scroll_positions))
            
            for position in scroll_positions:
                self.driver.execute_script(f"window.scrollTo(0, {position});")
                time.sleep(2)
                
                self.driver.execute_script("""
                    // Trigger intersection observer manually
                    if (window.IntersectionObserver) {
                        var images = document.querySelectorAll('img[data-src], img[loading="lazy"]');
                        images.forEach(function(img) {
                            var rect = img.getBoundingClientRect();
                            if (rect.top < window.innerHeight && rect.bottom > 0) {
                                if (img.dataset.src) {
                                    img.src = img.dataset.src;
                                }
                                img.loading = 'eager';
                            }
                        });
                    }
                """)
                
                time.sleep(1)
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(3)
            
        except Exception as e:
            pass

    def enhanced_lazy_loading_scroll(self):
        # Enhanced scrolling to trigger all lazy loading content
        try:
            # Get initial page height
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Multiple scroll passes with different strategies
            for pass_num in range(3):  # Three passes
                current_position = 0
                scroll_step = 100  # Smaller steps for better lazy loading
                
                while current_position < last_height:
                    # Scroll down
                    self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                    time.sleep(2)  # Longer wait at each position
                    
                    # Force check for lazy images at current viewport
                    self.driver.execute_script("""
                        var lazyImages = document.querySelectorAll('img[data-src]:not([src]), img[data-lazy-src]:not([src])');
                        lazyImages.forEach(function(img) {
                            var rect = img.getBoundingClientRect();
                            if (rect.top >= 0 && rect.top <= window.innerHeight) {
                                if (img.dataset.src) img.src = img.dataset.src;
                                if (img.dataset.lazySrc) img.src = img.dataset.lazySrc;
                            }
                        });
                    """)
                    
                    # Check if new content was loaded
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height > last_height:
                        last_height = new_height
                    
                    current_position += scroll_step
                    
                    if current_position > 100000:
                        break
                
                time.sleep(3)
            
           
            sections = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
            
            for section in sections:
                scroll_to = int(last_height * section)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_to});")
                time.sleep(3)  
            
            # Scroll back to top and wait
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(5)

        except Exception as e:
            pass

    def safe_hover_trigger(self):
        # Safely trigger hover effects without causing stale element errors
        try:
            hover_selectors = [
                '.card', '.box', '.item', '.product',
                'nav li', '.menu-item', '.hero'
            ]

            for selector in hover_selectors:
                try:
                    
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for i, element in enumerate(elements[:5]):  
                        try:
                            element.is_displayed()  
                            webdriver.ActionChains(self.driver).move_to_element(element).perform()
                            time.sleep(0.5)
                        except (StaleElementReferenceException, Exception):
                            continue
                except Exception:
                    continue

        except Exception:
            pass  

    def is_valid_url(self, url):
        # Check if URL is valid and belongs to GRIN domain
        try:
            parsed = urlparse(url)
            return (
                parsed.netloc in ['grin.co', 'www.grin.co'] and
                not any(ext in url.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.css', '.js']) and
                not url.startswith('mailto:') and
                not url.startswith('tel:') and
                '#' not in url
            )
        except:
            return False

    def extract_navigation_links(self, page_source):
        # Extract navigation links from page source
        soup = BeautifulSoup(page_source, 'html.parser')
        links = set()

        # Extract links from navigation elements
        for selector in self.navigation_selectors + self.dropdown_selectors:
            try:
                nav_links = soup.select(selector)
                for link in nav_links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(self.base_url, href)
                        if self.is_valid_url(full_url):
                            links.add(full_url)
            except Exception:
                continue

        # Also extract from main content areas
        content_selectors = [
            '.main a',
            '.content a',
            '.hero a',
            '.cta a',
            'main a'
        ]

        for selector in content_selectors:
            try:
                content_links = soup.select(selector)
                for link in content_links:
                    href = link.get('href')
                    if href and not href.startswith('#'):
                        full_url = urljoin(self.base_url, href)
                        if self.is_valid_url(full_url):
                            links.add(full_url)
            except Exception:
                continue

        return list(links)

    def handle_dropdowns_safely(self):
        # Safely handle dropdown menus without stale element errors
        try:
            nav_selectors = ['nav li', '.nav li', '.menu li', '.navigation li']
            
            for selector in nav_selectors:
                try:
                    
                    nav_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for i in range(min(len(nav_items), 5)):  
                        try:
                            
                            nav_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if i < len(nav_items):
                                item = nav_items[i]
                                
                                item.is_displayed()
                                webdriver.ActionChains(self.driver).move_to_element(item).perform()
                                time.sleep(1.5)
                        except (StaleElementReferenceException, Exception):
                            continue
                except Exception:
                    continue

        except Exception:
            pass

    def take_enhanced_screenshot(self, url, filename):
        # Take enhanced full-page screenshot with better content loading
        try:
            print(f"Taking screenshot...")

            # Ensure all content is loaded before screenshot
            self.wait_for_complete_page_load()
            
            time.sleep(5)

            # Method 1: Chrome DevTools Protocol (preferred for full page)
            try:
                page_rect = self.driver.execute_cdp_cmd('Page.getLayoutMetrics', {})
                content_size = page_rect['contentSize']

                screenshot_data = self.driver.execute_cdp_cmd('Page.captureScreenshot', {
                    'format': 'png',
                    'captureBeyondViewport': True,
                    'clip': {
                        'x': 0,
                        'y': 0,
                        'width': content_size['width'],
                        'height': content_size['height'],
                        'scale': 1
                    }
                })

                screenshot_path = os.path.join(self.screenshots_dir, filename)
                with open(screenshot_path, 'wb') as f:
                    f.write(base64.b64decode(screenshot_data['data']))

                print(f"    ✓ Screenshot saved: {filename}")
                return True

            except Exception as e:
                # Method 2: Manual stitching with PIL
                try:
                    from PIL import Image

                    total_height = self.driver.execute_script("""
                        return Math.max(
                            document.body.scrollHeight,
                            document.body.offsetHeight,
                            document.documentElement.clientHeight,
                            document.documentElement.scrollHeight,
                            document.documentElement.offsetHeight
                        );
                    """)

                    viewport_height = 1080
                    self.driver.set_window_size(1920, viewport_height)
                    time.sleep(3)

                    screenshots = []
                    overlap = 100

                    for y in range(0, total_height, viewport_height - overlap):
                        self.driver.execute_script(f"window.scrollTo(0, {y});")
                        time.sleep(4)  

                        screenshot_png = self.driver.get_screenshot_as_png()
                        screenshot_img = Image.open(io.BytesIO(screenshot_png))
                        screenshots.append((screenshot_img, y))

                    if screenshots:
                        full_image = Image.new('RGB', (screenshots[0][0].size[0], total_height), (255, 255, 255))

                        for img, y_pos in screenshots:
                            paste_y = min(y_pos, total_height - img.size[1])
                            full_image.paste(img, (0, paste_y))

                        screenshot_path = os.path.join(self.screenshots_dir, filename)
                        full_image.save(screenshot_path, 'PNG', quality=95)
                        print(f"    ✓ Stitched screenshot saved: {filename}")
                        return True

                except Exception as e2:
                    total_height = self.driver.execute_script("return document.body.scrollHeight;")
                    max_height = min(total_height, 20000)  
                    
                    self.driver.set_window_size(1920, max_height)
                    time.sleep(6)
                    
                    screenshot_path = os.path.join(self.screenshots_dir, filename)
                    self.driver.save_screenshot(screenshot_path)
                    print(f"    ✓ Fallback screenshot saved: {filename}")
                    return True

        except Exception as e:
            return False

    def sanitize_filename(self, url):
        # Create a safe filename from URL
        path = urlparse(url).path
        if not path or path == '/':
            return "homepage.png"

        filename = path.strip('/').replace('/', '_')
        filename = re.sub(r'[^\w\-_.]', '_', filename)

        if not filename.endswith('.png'):
            filename += '.png'

        return filename

    def crawl_page(self, url, depth):
        # Crawl a single page with enhanced loading
        if url in self.visited_urls or depth > self.max_depth:
            return []

        print(f"\n{'  ' * depth}🔍 Crawling: {url} (depth: {depth})")

        try:
            self.driver.get(url)
            self.visited_urls.add(url)

            self.handle_dropdowns_safely()

            # Take enhanced screenshot
            filename = self.sanitize_filename(url)
            success = self.take_enhanced_screenshot(url, filename)

            if success:
                print(f"{'  ' * depth}    ✅ Screenshot captured")
            else:
                print(f"{'  ' * depth}    ⚠ Screenshot had issues")

            # Extract links
            page_source = self.driver.page_source
            links = self.extract_navigation_links(page_source)
            new_links = [link for link in links if link not in self.visited_urls]
            
            print(f"{'  ' * depth}    📋 Found {len(new_links)} new links")
            return new_links

        except Exception as e:
            print(f"{'  ' * depth}  ✗ Error: {e}")
            self.failed_urls.add(url)
            return []

    def crawl_website(self):
        # Main crawling method
        print("🚀 Starting GRIN website crawl...")

        # Predefined important pages
        important_pages = [
            "https://grin.co/",
            "https://grin.co/product",
            "https://grin.co/solutions",
            "https://grin.co/about",
            "https://grin.co/product/influencer-discovery-platform",
            "https://grin.co/product/influencer-relationship-management-platform",
            "https://grin.co/product/influencer-content-management-platform",
            "https://grin.co/product/influencer-marketing-reporting-platform/",
        ]

        for page in important_pages:
            if page not in [item[0] for item in self.url_queue]:
                self.url_queue.append((page, 0))

        while self.url_queue:
            url, depth = self.url_queue.popleft()

            if url in self.visited_urls or depth > self.max_depth:
                continue

            new_links = self.crawl_page(url, depth)

            for link in new_links:
                if link not in self.visited_urls:
                    self.url_queue.append((link, depth + 1))

            # Respectful delay
            time.sleep(4)

    def create_zip_file(self):
        # Create zip file with all screenshots
        zip_filename = "grin_website_screenshots.zip"

        try:
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.screenshots_dir):
                    for file in files:
                        if file.endswith('.png'):
                            file_path = os.path.join(root, file)
                            zipf.write(file_path, file)

            print(f"\n✓ Created zip file: {zip_filename}")
            print(f"  Total screenshots: {len(os.listdir(self.screenshots_dir))}")
            return zip_filename

        except Exception as e:
            print(f"✗ Error creating zip file: {e}")
            return None

    def run(self):
        # Main execution method
        try:
            self.setup_driver()
            self.crawl_website()

            print(f"\n📊 Crawl Summary:")
            print(f"  ✓ Pages visited: {len(self.visited_urls)}")
            print(f"  ✗ Pages failed: {len(self.failed_urls)}")

            if self.failed_urls:
                print(f"  Failed URLs: {list(self.failed_urls)}")

            zip_file = self.create_zip_file()
            return zip_file

        except Exception as e:
            print(f"✗ Critical error: {e}")

        finally:
            if self.driver:
                self.driver.quit()
                print("✓ Browser closed")

# Main execution
if __name__ == "__main__":
    print(" GRIN Website Screenshot Crawler - FIXED IMAGE LOADING")
    print("=" * 60)

    crawler = GRINWebsiteCrawler(max_depth=2)

    # Run the crawler
    zip_file = crawler.run()

    if zip_file and os.path.exists(zip_file):
        print(f"\n Crawling completed successfully!")
        print(f" Zip file created: {zip_file}")
        print(f" Screenshots saved in: {crawler.screenshots_dir}/")
    else:
        print("\n Task failed - no zip file created")

def run_custom_crawl(base_url="https://grin.co", max_depth=2):
    """Run crawler with custom parameters"""
    crawler = GRINWebsiteCrawler(base_url=base_url, max_depth=max_depth)
    return crawler.run()