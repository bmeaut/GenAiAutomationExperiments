#!/usr/bin/env python3
"""
Capri Pizzeria Automated Ordering Bot
Automates the process of ordering pizza from capripizzeria.hu
"""

import json
import os
import time
from typing import List, Dict, Optional, Tuple

from fuzzywuzzy import fuzz, process
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
from tqdm import tqdm


class PizzaOrderingBot:
    def __init__(self):
        self.driver = None
        self.supported_zip_codes = [
            "3035", "3036", "3200", "3211", "3212", "3213",
            "3214", "3231", "3232", "3261", "3281", "3292"
        ]
        self.pizzas = []
        self.user_zip = None
        self.shipping_details_file = "shipping_details.json"

    def setup_driver(self):
        """Initialize Chrome WebDriver with options"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # Remove headless mode for better debugging
        # chrome_options.add_argument("--headless")

        # Suppress Chrome logs and errors
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)

    def greet_and_get_zip(self) -> bool:
        """Greet user and validate zip code"""
        print("🍕 Welcome to Capri Pizzeria Automated Ordering Bot!")
        print("=" * 50)

        # Check if zip code is saved in shipping details
        saved_details = self.load_shipping_details()
        if saved_details and 'billing_postcode' in saved_details:
            saved_zip = saved_details['billing_postcode']
            use_saved = input(f"Use saved zip code ({saved_zip})? (Y/n): ").lower().strip()
            if use_saved in ['y', 'yes', '']:
                return self._validate_and_set_zip(saved_zip)

        while True:
            zip_code = input("Please enter your zip code: ").strip()
            if self._validate_and_set_zip(zip_code):
                return True

    def _validate_and_set_zip(self, zip_code: str) -> bool:
        """Validate and set zip code"""
        if zip_code in self.supported_zip_codes:
            print(f"✅ Great! Zip code {zip_code} is supported.")
            self.user_zip = zip_code
            return True
        else:
            print(f"⚠️  Warning: Zip code {zip_code} is not in our supported list.")
            print("Supported zip codes:", ", ".join(self.supported_zip_codes))

            choice = input("You might not be able to order. Do you want to proceed anyway? (y/N): ").lower().strip()
            if choice in ['y', 'yes']:
                self.user_zip = zip_code
                return True
            elif choice in ['n', 'no', '']:
                print("👋 Thanks for using this bot. Goodbye!")
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")
                return False

    def scrape_pizzas(self) -> List[Dict[str, str]]:
        """Scrape all pizzas from the website"""
        print("\n🔍 Fetching available pizzas...")
        pizzas = []
        page = 1

        # Use tqdm without predetermined total
        pbar = tqdm(desc="Scraping pizzas", unit=" pages")

        try:
            while True:
                url = f"https://capripizzeria.hu/product-category/pizza/page/{page}/?count=36"

                try:
                    self.driver.get(url)
                    time.sleep(1)  # Reduced sleep time

                    # Check if page exists (no 404)
                    if "404" in self.driver.title or "Not Found" in self.driver.page_source:
                        # Navigate back to first page after hitting 404
                        self.driver.get("https://capripizzeria.hu/product-category/pizza/page/1/?count=36")
                        break

                    # Find pizza elements
                    pizza_elements = self.driver.find_elements(By.CSS_SELECTOR, ".product_cat-pizza h3.porto-heading a")

                    if not pizza_elements:
                        break

                    # Process pizzas with nested progress
                    for element in tqdm(pizza_elements, desc=f"Processing pizzas on page {page}", leave=False):
                        name = element.text.strip()
                        link = element.get_attribute("href")
                        if name and link:
                            pizzas.append({"name": name, "link": link})

                    page += 1
                    pbar.update(1)

                except Exception as e:
                    tqdm.write(f"Error on page {page}: {e}")
                    break
        finally:
            pbar.close()

        self.pizzas = pizzas
        print(f"✅ Found {len(pizzas)} pizzas across {page - 1} pages!")
        return pizzas

    def select_pizza(self) -> Optional[Dict[str, str]]:
        """Let user select a pizza with fuzzy matching"""
        if not self.pizzas:
            print("❌ No pizzas available!")
            return None

        print("\n🍕 Available pizzas:")
        for i, pizza in enumerate(self.pizzas[:10], 1):  # Show first 10
            print(f"{i}. {pizza['name']}")

        if len(self.pizzas) > 10:
            print(f"... and {len(self.pizzas) - 10} more pizzas")

        while True:
            pizza_name = input("\nWhich pizza would you like to order? ").strip()

            # Try exact match first
            for pizza in self.pizzas:
                if pizza_name.lower() == pizza['name'].lower():
                    return pizza

            # Use fuzzy matching
            pizza_names = [pizza['name'] for pizza in self.pizzas]
            best_match = process.extractOne(pizza_name, pizza_names, scorer=fuzz.ratio)

            if best_match and best_match[1] > 60:  # 60% similarity threshold
                matched_name = best_match[0]
                confirm = input(f"Did you mean '{matched_name}'? (Y/n): ").lower().strip()
                if confirm in ['y', 'yes', '']:
                    for pizza in self.pizzas:
                        if pizza['name'] == matched_name:
                            return pizza

            print("❌ Pizza not found. Please try again or be more specific.")

    def configure_pizza(self, pizza: Dict[str, str]) -> bool:
        """Configure pizza size and quantity"""
        print(f"\n🍕 Configuring: {pizza['name']}")

        try:
            # Loading pizza page with progress
            with tqdm(total=3, desc="Loading pizza page") as pbar:
                self.driver.get(pizza['link'])
                pbar.update(1)
                time.sleep(2)
                pbar.update(1)
                pbar.set_description("Page loaded")
                pbar.update(1)

            # Get size options
            try:
                size_select = Select(self.driver.find_element(By.ID, "yith-wapo-1"))
                all_options = size_select.options

                # Filter out "Select an option" entries
                valid_options = []
                for option in all_options:
                    option_text = option.text.strip()
                    if option_text and not option_text.lower().startswith("select"):
                        valid_options.append(option)

                if len(valid_options) > 1:
                    print("\n📏 Available sizes:")
                    for i, option in enumerate(valid_options):
                        selected_text = " (default)" if option.get_attribute("selected") else ""
                        print(f"{i + 1}. {option.text}{selected_text}")

                    while True:
                        try:
                            choice = input("Select size (press Enter for default): ").strip()
                            if not choice:
                                # Use default (find the selected option)
                                for option in valid_options:
                                    if option.get_attribute("selected"):
                                        break
                                break
                            else:
                                size_index = int(choice) - 1
                                if 0 <= size_index < len(valid_options):
                                    # Select by value instead of index to avoid "Select an option" issues
                                    selected_option = valid_options[size_index]
                                    size_select.select_by_value(selected_option.get_attribute("value"))
                                    break
                                else:
                                    print("Invalid choice. Please try again.")
                        except ValueError:
                            print("Please enter a valid number.")

            except NoSuchElementException:
                print("ℹ️  No size options available for this pizza.")

            # Get quantity
            while True:
                try:
                    qty_input = input("How many pizzas? (default: 1): ").strip()
                    quantity = 1 if not qty_input else int(qty_input)
                    if quantity > 0:
                        break
                    else:
                        print("Quantity must be positive.")
                except ValueError:
                    print("Please enter a valid number.")

            # Configure and add to cart with progress
            with tqdm(total=4, desc="Adding to cart") as pbar:
                # Set quantity only if it's not 1
                pbar.set_description("Setting quantity")

                if quantity != 1:
                    try:
                        # Find the quantity input
                        qty_element = None
                        selectors = [
                            "input[name='quantity'][type='number']",
                            "input.qty[name='quantity']",
                            "input[name='quantity']"
                        ]

                        for selector in selectors:
                            try:
                                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                if elements:
                                    # Take the first visible and enabled element
                                    for elem in elements:
                                        if elem.is_displayed() and elem.is_enabled():
                                            qty_element = elem
                                            break
                                    if qty_element:
                                        break
                            except Exception:
                                continue

                        if qty_element:
                            # Scroll to element and ensure it's visible
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", qty_element)
                            time.sleep(0.5)

                            # Simulate user interaction: click, select all, and type
                            try:
                                qty_element.click()
                                time.sleep(0.2)
                                qty_element.send_keys("\u0001")  # Ctrl+A to select all
                                time.sleep(0.1)
                                qty_element.send_keys(str(quantity))
                                time.sleep(0.3)

                                # Verify the value was set
                                current_value = qty_element.get_attribute('value')
                                if current_value != str(quantity):
                                    # Fallback: use JavaScript to force set the value
                                    self.driver.execute_script("""
                                        var element = arguments[0];
                                        var value = arguments[1];
                                        element.value = value;
                                        element.dispatchEvent(new Event('input', {bubbles: true, cancelable: true}));
                                        element.dispatchEvent(new Event('change', {bubbles: true, cancelable: true}));
                                        element.dispatchEvent(new Event('keyup', {bubbles: true, cancelable: true}));
                                        element.dispatchEvent(new Event('blur', {bubbles: true, cancelable: true}));
                                    """, qty_element, str(quantity))
                                    time.sleep(0.5)

                                # Final verification
                                final_value = qty_element.get_attribute('value')
                                if final_value == str(quantity):
                                    print(f"✅ Set quantity to {quantity}")
                                else:
                                    print(
                                        f"⚠️  Quantity may not have been set correctly (expected: {quantity}, actual: {final_value})")

                            except Exception as e:
                                print(f"⚠️  Could not set quantity: {str(e)[:50]}")

                        else:
                            print(f"⚠️  Quantity input not found, using default (1)")

                    except Exception as e:
                        print(f"⚠️  Could not set quantity: {str(e)[:50]}")
                else:
                    print(f"✅ Using default quantity (1)")

                pbar.update(1)

                # Wait for page to be ready and scroll to button
                pbar.set_description("Preparing to add to cart")
                add_to_cart_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "single_add_to_cart_button"))
                )
                pbar.update(1)

                # Scroll to button to ensure it's visible
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_to_cart_btn)
                time.sleep(0.5)  # Small delay after scrolling
                pbar.update(1)

                # Click the button
                pbar.set_description("Clicking add to cart")
                add_to_cart_btn.click()
                pbar.update(1)
                pbar.set_description("Added to cart")

            print(f"✅ Added {quantity}x {pizza['name']} to cart!")
            time.sleep(2)
            return True

        except Exception as e:
            print(f"❌ Error configuring pizza: {e}")
            return False

    def load_shipping_details(self) -> Optional[Dict]:
        """Load shipping details from JSON file"""
        if os.path.exists(self.shipping_details_file):
            try:
                with open(self.shipping_details_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading shipping details: {e}")
        return None

    def save_shipping_details(self, details: Dict):
        """Save shipping details to JSON file"""
        try:
            with open(self.shipping_details_file, 'w', encoding='utf-8') as f:
                json.dump(details, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving shipping details: {e}")

    def get_shipping_details(self) -> Dict:
        """Get shipping details from user or saved file"""
        saved_details = self.load_shipping_details()

        if saved_details:
            use_saved = input("Use previously saved shipping details? (Y/n): ").lower().strip()
            if use_saved in ['y', 'yes', '']:
                return saved_details

        print("\n📋 Please enter your shipping details:")
        details = {}

        details['billing_last_name'] = input("Vezetéknév (Last name): ").strip()
        details['billing_first_name'] = input("Keresztnév (First name): ").strip()

        # Ask about zip code
        use_same_zip = input(f"Use the same zip code ({self.user_zip})? (Y/n): ").lower().strip()
        if use_same_zip in ['y', 'yes', '']:
            details['billing_postcode'] = self.user_zip
        else:
            new_zip = input("Irányítószám (Zip code): ").strip()
            # Warn if the new zip code is not supported
            if new_zip not in self.supported_zip_codes:
                print(f"⚠️  Warning: Zip code {new_zip} is not in our supported delivery list.")
                print("Supported zip codes:", ", ".join(self.supported_zip_codes))
                print("This may affect delivery availability.")
            details['billing_postcode'] = new_zip

        details['billing_city'] = input("Város (City): ").strip()
        details['billing_address_1'] = input("Utca, házszám (Street, house number): ").strip()
        details['billing_address_2'] = input("Emelet, lépcsőház, lakás, stb. (Floor, door, flat - optional): ").strip()
        details['billing_phone'] = input("Telefonszám (Phone number): ").strip()
        details['billing_email'] = input("Email: ").strip()

        # Save details
        save_details = input("Save these details for future orders? (Y/n): ").lower().strip()
        if save_details in ['y', 'yes', '']:
            self.save_shipping_details(details)

        return details

    def fill_checkout_form(self, details: Dict) -> bool:
        """Fill the checkout form with shipping details"""
        try:
            print("\n📝 Filling checkout form...")

            # Navigate to checkout
            self.driver.get("https://capripizzeria.hu/checkout/")
            time.sleep(3)

            # Fill form fields with progress bar
            field_mapping = {
                'billing_last_name': details['billing_last_name'],
                'billing_first_name': details['billing_first_name'],
                'billing_postcode': details['billing_postcode'],
                'billing_city': details['billing_city'],
                'billing_address_1': details['billing_address_1'],
                'billing_address_2': details['billing_address_2'],
                'billing_phone': details['billing_phone'],
                'billing_email': details['billing_email']
            }

            # Filter out empty values for progress tracking
            filled_fields = {k: v for k, v in field_mapping.items() if v}

            with tqdm(filled_fields.items(), desc="Filling form fields", unit="field") as pbar:
                for field_id, value in pbar:
                    pbar.set_description(f"Filling {field_id}")
                    try:
                        element = self.driver.find_element(By.ID, field_id)
                        element.clear()
                        element.send_keys(value)
                        time.sleep(0.2)  # Small delay for stability
                    except NoSuchElementException:
                        tqdm.write(f"⚠️  Field {field_id} not found")

            # Tick terms checkbox
            try:
                terms_checkbox = self.driver.find_element(By.ID, "terms")
                if not terms_checkbox.is_selected():
                    terms_checkbox.click()
                print("✅ Terms and conditions accepted")
            except NoSuchElementException:
                print("⚠️  Terms checkbox not found")

            # Scroll to the place order button
            try:
                place_order_btn = self.driver.find_element(By.ID, "place_order")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", place_order_btn)
                time.sleep(0.5)
                print("✅ Scrolled to place order button")
            except NoSuchElementException:
                print("⚠️  Place order button not found")

            return True

        except Exception as e:
            print(f"❌ Error filling checkout form: {e}")
            return False

    def get_order_total(self) -> Tuple[str, str]:
        """Get order total and currency symbol"""
        try:
            total_row = self.driver.find_element(By.CSS_SELECTOR, "tr.order-total")
            amount_element = total_row.find_element(By.CSS_SELECTOR, ".woocommerce-Price-amount bdi")

            # Extract amount and currency
            full_text = amount_element.text
            currency_element = total_row.find_element(By.CSS_SELECTOR, ".woocommerce-Price-currencySymbol")
            currency = currency_element.text

            # Remove currency symbol to get amount
            amount = full_text.replace(currency, "").strip()

            return amount, currency

        except Exception as e:
            print(f"Error getting order total: {e}")
            return "Unknown", "Unknown"

    def run(self):
        """Main execution flow"""
        try:
            # Step 1: Greet and validate zip code
            if not self.greet_and_get_zip():
                return

            # Step 2: Setup browser
            print("\n🌐 Starting browser...")
            self.setup_driver()

            # Step 3: Scrape pizzas
            self.scrape_pizzas()

            # Step 4: Order pizzas
            while True:
                pizza = self.select_pizza()
                if not pizza:
                    break

                if not self.configure_pizza(pizza):
                    continue

                # Ask if they want to order more
                while True:
                    more_pizza = input("\nWould you like to order more pizzas? (y/N): ").lower().strip()
                    if more_pizza in ['y', 'yes', 'n', 'no', '']:
                        break
                    else:
                        print("Please enter 'y' for yes, 'n' for no, or press Enter for default (no).")

                if more_pizza not in ['y', 'yes']:
                    break

            # Step 5: Checkout
            print("\n🛒 Proceeding to checkout...")
            details = self.get_shipping_details()

            if self.fill_checkout_form(details):
                # Get order total
                amount, currency = self.get_order_total()

                print("\n" + "=" * 50)
                print(f"💰 Order Total: {amount} {currency}")
                print("=" * 50)
                print("✅ Your order is ready to be placed!")
                print("You can now click the button to complete your purchase.")

                input("\nPress Enter to close the browser...")

        except KeyboardInterrupt:
            print("\n\n👋 Order cancelled by user.")
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
        finally:
            if self.driver:
                self.driver.quit()


def main():
    """Entry point"""
    bot = PizzaOrderingBot()
    bot.run()


if __name__ == "__main__":
    main()
