# GRIN Website Screenshot Crawler

A Python web crawler that automatically captures full-page screenshots of the GRIN website (grin.co) and packages them into a convenient ZIP file.




## Installation & Setup

### 1. Clone or Download the Project

```bash
# Create project directory
mkdir grin-crawler
cd grin-crawler

# Copy the provided files:
# - grin_crawler.py
# - requirements.txt
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv grin_env

# Activate virtual environment
source grin_env/bin/activate

# Verify activation (you should see (grin_env) in your terminal prompt)
which python
```

### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt
```

### 4. Install Chrome and ChromeDriver (if not already installed)

```bash
# Install Google Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install google-chrome-stable

# ChromeDriver will be automatically managed by selenium
```

## Project Structure

```
grin-crawler/
├── grin_crawler.py          # Main crawler script
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── grin_env/              # Virtual environment (created after setup)
├── grin_screenshots/      # Screenshots folder (auto-created)
│   ├── homepage.png
│   ├── about.png
│   ├── product.png
│   └── ...
└── grin_website_screenshots.zip  # Final ZIP archive
```

### Expected Output

```
🎯 GRIN Website Screenshot Crawler - FIXED IMAGE LOADING
============================================================
✓ Chrome driver initialized successfully
🚀 Starting GRIN website crawl...

🔍 Crawling: https://grin.co/ (depth: 0)
  📸 Taking enhanced screenshot...
    ✅ Screenshot captured
    📋 Found 15 new links

🔍 Crawling: https://grin.co/product (depth: 0)
  📸 Taking enhanced screenshot...
    ✅ Screenshot captured
    📋 Found 12 new links

... (continues for all pages)

📊 Crawl Summary:
  ✓ Pages visited: 25
  ✗ Pages failed: 0

✓ Created zip file: grin_website_screenshots.zip
  Total screenshots: 25
✓ Browser closed

🎉 Crawling completed successfully!
📁 Zip file created: grin_website_screenshots.zip
📸 Screenshots saved in: grin_screenshots/
```


## Output Files

### Automatically Created Folders/Files

1. **`grin_screenshots/`** - Folder containing all individual PNG screenshots
2. **`grin_website_screenshots.zip`** - ZIP archive with all screenshots
