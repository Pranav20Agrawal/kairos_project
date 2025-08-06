# src/automations/whatsapp_automation.py

import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time

logger = logging.getLogger(__name__)

def send_whatsapp_message(recipient: str, message: str) -> bool:
    """
    Automates sending a WhatsApp message using Playwright.

    Args:
        recipient: The name of the contact or group to send the message to.
        message: The content of the message.

    Returns:
        True if the message was likely sent, False otherwise.
    """
    try:
        with sync_playwright() as p:
            # We use launch_persistent_context to utilize the user's default browser profile.
            # This is CRITICAL for using the existing WhatsApp login session.
            # Provide a user_data_dir path where browser data can be stored.
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            logger.info("Navigating to WhatsApp Web...")
            page.goto("https://web.whatsapp.com/", timeout=90000) # 90 sec timeout for QR scan if needed

            try:
                # Wait for the main search bar to appear, indicating the page is loaded.
                logger.info("Waiting for WhatsApp Web to load...")
                page.wait_for_selector("div[title='Search input textbox']", timeout=60000)
                logger.info("WhatsApp Web loaded successfully.")
            except PlaywrightTimeoutError:
                logger.error("Failed to load WhatsApp Web main page. Is the user logged in?")
                browser.close()
                return False

            # 1. Search for the recipient
            search_box_selector = "div[title='Search input textbox']"
            page.click(search_box_selector)
            page.fill(search_box_selector, recipient)
            logger.info(f"Searching for recipient: '{recipient}'")

            # 2. Click on the correct chat from the search results
            # We'll use an XPath selector to find the chat by its title attribute.
            chat_selector = f'//span[@title="{recipient}"]'
            try:
                page.wait_for_selector(chat_selector, timeout=10000) # 10s timeout to find the chat
                page.click(chat_selector)
                logger.info(f"Found and clicked on chat for '{recipient}'.")
            except PlaywrightTimeoutError:
                logger.error(f"Could not find a chat for '{recipient}'.")
                browser.close()
                return False
            
            # 3. Type and send the message
            message_box_selector = "div[title='Type a message']"
            page.wait_for_selector(message_box_selector, timeout=5000)
            page.click(message_box_selector)
            page.fill(message_box_selector, message)
            page.press(message_box_selector, "Enter")
            logger.info(f"Message sent to '{recipient}'.")
            
            # Give a moment for the message to send before closing
            time.sleep(2)
            browser.close()
            return True

    except Exception as e:
        logger.error(f"An unexpected error occurred during WhatsApp automation: {e}", exc_info=True)
        return False