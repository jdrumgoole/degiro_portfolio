"""Tests for portfolio overview page."""

import re
from playwright.sync_api import Page, expect


def test_page_loads(page: Page):
    """Test that the main page loads successfully."""
    expect(page).to_have_title(re.compile("DEGIRO Portfolio"))


def test_portfolio_summary_displays(page: Page):
    """Test that portfolio summary section is visible."""
    summary = page.locator(".portfolio-summary")
    expect(summary).to_be_visible()

    # Check for portfolio summary elements
    expect(page.locator("text=Portfolio Summary")).to_be_visible()


def test_all_stock_cards_display(page: Page, expected_stocks):
    """Test that all stock cards are displayed."""
    # Wait for stock cards to load
    page.wait_for_selector(".stock-card", timeout=10000)

    # Get all stock cards
    stock_cards = page.locator(".stock-card")
    count = stock_cards.count()

    # Should have 11 stocks (5 US + 6 European)
    assert count == 11, f"Expected 11 stock cards, found {count}"


def test_stock_card_shows_correct_information(page: Page, expected_stocks):
    """Test that stock cards show correct company names and share counts."""
    for stock_name, stock_data in expected_stocks.items():
        # Find the card with this company name
        card = page.locator(f".stock-card:has-text('{stock_name}')")
        expect(card).to_be_visible()

        # Check share count
        shares_text = card.locator(".stock-shares").text_content()
        expected_shares = f"{stock_data['shares']} shares"
        assert expected_shares in shares_text, f"Expected '{expected_shares}' in '{shares_text}'"

        # Check transaction count
        transactions_text = card.locator(".stock-meta").text_content()
        expected_trans = f"{stock_data['transactions']} transaction"
        assert expected_trans in transactions_text, f"Expected '{expected_trans}' in '{transactions_text}'"


def test_stock_card_shows_ticker_symbols(page: Page, expected_stocks):
    """Test that stock cards display Yahoo Finance ticker symbols."""
    # Check a few specific tickers
    test_cases = [
        ("NVIDIA CORP", "NVDA"),
        ("ASML HOLDING NV", "ASML.AS"),
        ("SAP SE", "SAP.DE"),
        ("TELEFONAKTIEBOLAGET LM ERICSSON-B", "ERIC-B.ST"),
    ]

    for stock_name, expected_ticker in test_cases:
        card = page.locator(f".stock-card:has-text('{stock_name}')")
        ticker = card.locator(".stock-ticker")
        expect(ticker).to_be_visible()
        expect(ticker).to_contain_text(expected_ticker)


def test_stock_card_shows_exchange(page: Page):
    """Test that stock cards display exchange information."""
    # Check for exchange labels
    cards_with_exchange = page.locator(".stock-card .stock-exchange")
    count = cards_with_exchange.count()

    # All stocks should have exchange info
    assert count > 0, "No exchange information found on stock cards"


def test_stock_card_shows_latest_price(page: Page):
    """Test that stock cards show latest price information."""
    # Wait for prices to load
    page.wait_for_selector(".stock-price", timeout=10000)

    # Check that at least one stock has price information
    price_elements = page.locator(".stock-price")
    count = price_elements.count()

    assert count > 0, "No price information displayed on stock cards"

    # Check the first price element has proper format
    first_price = price_elements.first.text_content()
    # Should contain a currency symbol and number
    assert any(symbol in first_price for symbol in ["$", "€"]), f"No currency symbol in price: {first_price}"


def test_stock_card_shows_price_change(page: Page):
    """Test that stock cards show daily price change percentage."""
    # Wait for price changes to load
    page.wait_for_selector(".stock-price", timeout=10000)

    # Look for price change indicators (▲ or ▼)
    positive_changes = page.locator(".positive")
    negative_changes = page.locator(".negative")

    # Should have at least some price changes
    total_changes = positive_changes.count() + negative_changes.count()
    assert total_changes > 0, "No price changes displayed"


def test_market_data_status_displays(page: Page):
    """Test that market data status is shown."""
    status = page.locator("#market-data-status")
    expect(status).to_be_visible()

    # Should contain date information
    status_text = status.text_content()
    assert "Latest market data:" in status_text or "No market data" in status_text


def test_update_market_data_button_exists(page: Page):
    """Test that Update Market Data button is present."""
    button = page.locator("button:has-text('Update Market Data')")
    expect(button).to_be_visible()
    expect(button).to_be_enabled()


def test_company_name_is_clickable(page: Page):
    """Test that company names have clickable links."""
    # Check NVIDIA card
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')")
    company_link = nvidia_card.locator(".stock-name a")
    expect(company_link).to_be_visible()

    # Check that it has a valid href
    href = company_link.get_attribute("href")
    assert href is not None
    assert "google.com/search" in href
    assert "investor" in href.lower()


def test_ticker_symbol_is_clickable(page: Page):
    """Test that ticker symbols have clickable links to Google Finance."""
    # Check NVIDIA ticker
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')")
    ticker_link = nvidia_card.locator(".stock-ticker a")
    expect(ticker_link).to_be_visible()

    # Check that it has a valid Google Finance href
    href = ticker_link.get_attribute("href")
    assert href is not None
    assert "google.com/finance" in href
    assert "NVDA" in href


def test_stock_card_click_loads_chart(page: Page):
    """Test that clicking a stock card loads its chart."""
    # Click on NVIDIA card
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')").first
    nvidia_card.click()

    # Wait for chart to load
    page.wait_for_selector("#chart", timeout=10000)

    # Check that chart container is visible
    chart = page.locator("#chart")
    expect(chart).to_be_visible()

    # Check that the card becomes active
    expect(nvidia_card).to_have_class(re.compile("active"))


def test_portfolio_summary_shows_values(page: Page):
    """Test that portfolio summary displays value information."""
    summary = page.locator(".portfolio-summary")

    # Should contain value elements
    values = summary.locator(".summary-value")
    count = values.count()

    assert count > 0, "No summary values displayed"


def test_compact_design_font_sizes(page: Page):
    """Test that the UI uses compact font sizes."""
    # Check body font size
    body = page.locator("body")
    font_size = body.evaluate("el => window.getComputedStyle(el).fontSize")

    # Should be 14px or smaller (converted from em)
    assert "14px" in font_size or "13px" in font_size or "12px" in font_size, \
        f"Body font size not compact: {font_size}"


def test_stock_cards_grid_layout(page: Page):
    """Test that stock cards are arranged in a grid."""
    grid = page.locator("#holdings-grid")
    expect(grid).to_be_visible()

    # Check CSS display property
    display = grid.evaluate("el => window.getComputedStyle(el).display")
    assert display == "grid", f"Holdings grid not using grid layout: {display}"


def test_responsive_layout(page: Page):
    """Test that the page has responsive styling."""
    # Check that the page has a minimum height
    body = page.locator("body")
    min_height = body.evaluate("el => window.getComputedStyle(el).minHeight")

    # Should have viewport-based height
    assert "vh" in min_height, f"Body doesn't use viewport height: {min_height}"
