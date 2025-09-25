# Capri Pizzeria Automated Ordering Bot

This Python script automates the process of ordering pizza from capripizzeria.hu using Selenium WebDriver.

## Features

- ✅ Zip code validation for delivery areas
- 🍕 Automatic pizza catalog scraping
- 🔍 Fuzzy search for pizza selection
- 📏 Size and quantity configuration
- 💾 Shipping details persistence
- 🛒 Automated checkout form filling
- 💰 Order total calculation

## Supported Zip Codes

3035, 3036, 3200, 3211, 3212, 3213, 3214, 3231, 3232, 3261, 3281, 3292

## Prerequisites

1. **Python 3.7+** installed on your system
2. **Google Chrome** browser installed
3. **ChromeDriver** - The script will attempt to use Chrome WebDriver

## Installation

1. Install the required Python packages:
```bash
pip install -r requirements.txt
```

2. Make sure ChromeDriver is available:
   - Download from: https://chromedriver.chromium.org/
   - Add to your system PATH, or
   - Place in the same directory as the script

## Usage

Run the script:
```bash
python pizza_ordering_bot.py
```

The bot will guide you through:
1. Zip code validation
2. Pizza selection with fuzzy matching
3. Size and quantity configuration
4. Adding multiple pizzas to cart
5. Checkout form completion
6. Order total display

## Files Created

- `shipping_details.json` - Stores your shipping information for future orders

## Notes

- The browser window will remain open for debugging purposes
- Your shipping details are saved locally for convenience
- The script stops at the final order confirmation - you need to manually place the order
- Supported zip codes are validated before starting the ordering process

## Troubleshooting

- If ChromeDriver issues occur, ensure Chrome and ChromeDriver versions match
- For timeout errors, check your internet connection
- If elements aren't found, the website structure may have changed