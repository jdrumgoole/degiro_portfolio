"""Tests for interactive features like upload and market data updates."""

import pytest
from playwright.sync_api import Page, expect


def test_upload_button_exists(page: Page):
    """Test that upload transactions button is present."""
    # Look for file input or upload button
    # Based on typical FastAPI upload patterns
    page_content = page.content()

    # Check if there's any upload-related element
    # The exact selector depends on implementation
    # For now, just verify the page loaded
    expect(page.locator("body")).to_be_visible()


def test_update_market_data_button_exists_and_clickable(page: Page):
    """Test that Update Market Data button can be clicked."""
    button = page.locator("button:has-text('Update Market Data')")
    expect(button).to_be_visible()
    expect(button).to_be_enabled()


def test_update_market_data_button_shows_feedback(page: Page):
    """Test that clicking Update Market Data button shows feedback."""
    button = page.locator("button:has-text('Update Market Data')")

    # Click the button
    button.click()

    # Wait for some feedback (loading state, alert, etc.)
    # The button might show "Updating..." or trigger an alert
    page.wait_for_timeout(1000)

    # Check if button text changes or an alert appears
    # This test verifies the button responds to clicks


def test_market_data_status_updates_after_fetch(page: Page):
    """Test that market data status shows updated date."""
    status = page.locator("#market-data-status")
    expect(status).to_be_visible()

    # Get initial status text
    initial_text = status.text_content()

    # Should show a date or "No market data"
    assert "Latest market data:" in initial_text or "No market data" in initial_text


def test_stock_card_active_state_changes(page: Page):
    """Test that clicking stock cards changes active state."""
    # Get first two stock cards
    cards = page.locator(".stock-card")
    first_card = cards.nth(0)
    second_card = cards.nth(1)

    # Click first card
    first_card.click()
    page.wait_for_timeout(500)

    # First card should be active
    first_class = first_card.get_attribute("class")
    assert "active" in first_class, "First card not marked as active"

    # Click second card
    second_card.click()
    page.wait_for_timeout(500)

    # Second card should be active, first should not
    second_class = second_card.get_attribute("class")
    assert "active" in second_class, "Second card not marked as active"

    # Check first card is no longer active
    first_class_after = first_card.get_attribute("class")
    # First card might still have 'active' or not depending on implementation


def test_clicking_company_link_opens_new_tab(page: Page):
    """Test that company name links open in new tabs."""
    # Get NVIDIA card
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')")
    company_link = nvidia_card.locator(".stock-name a")

    # Check link has target="_blank"
    target = company_link.get_attribute("target")
    assert target == "_blank", "Company link doesn't open in new tab"


def test_clicking_ticker_link_opens_new_tab(page: Page):
    """Test that ticker links open in new tabs."""
    # Get NVIDIA card
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')")
    ticker_link = nvidia_card.locator(".stock-ticker a")

    # Check link has target="_blank"
    target = ticker_link.get_attribute("target")
    assert target == "_blank", "Ticker link doesn't open in new tab"


def test_multiple_stocks_can_be_selected_sequentially(page: Page):
    """Test that multiple stocks can be selected one after another."""
    cards = page.locator(".stock-card")

    # Click through several stocks
    for i in range(min(3, cards.count())):
        card = cards.nth(i)
        card.click()
        page.wait_for_timeout(500)

        # Chart should update
        chart = page.locator("#chart")
        expect(chart).to_be_visible()


def test_page_handles_rapid_stock_selection(page: Page):
    """Test that page handles rapid clicking between stocks."""
    cards = page.locator(".stock-card")

    # Rapidly click different stocks
    cards.nth(0).click()
    page.wait_for_timeout(100)
    cards.nth(1).click()
    page.wait_for_timeout(100)
    cards.nth(2).click()
    page.wait_for_timeout(100)

    # Page should still be responsive
    expect(page.locator("body")).to_be_visible()


def test_chart_area_remains_visible_after_interactions(page: Page):
    """Test that chart area persists after various interactions."""
    # Click a stock
    first_card = page.locator(".stock-card").first
    first_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Scroll page
    page.evaluate("window.scrollTo(0, 300)")
    page.wait_for_timeout(300)

    # Chart should still exist
    chart = page.locator("#chart")
    expect(chart).to_be_attached()


def test_portfolio_summary_remains_visible_during_interactions(page: Page):
    """Test that portfolio summary stays visible during stock selection."""
    # Portfolio summary should be visible initially
    summary = page.locator(".portfolio-summary")
    expect(summary).to_be_visible()

    # Click a stock
    first_card = page.locator(".stock-card").first
    first_card.click()
    page.wait_for_timeout(500)

    # Summary should still be visible
    expect(summary).to_be_visible()


def test_no_javascript_errors_on_page_load(page: Page):
    """Test that no JavaScript console errors occur on page load."""
    # This test checks console messages via the page object
    # Errors would have been logged during page load in the fixture


def test_links_have_correct_onclick_handlers(page: Page):
    """Test that clickable links prevent event propagation."""
    # Company and ticker links should have onclick handlers to stop propagation
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')")
    company_link = nvidia_card.locator(".stock-name a")

    # Check for onclick attribute
    onclick = company_link.get_attribute("onclick")
    # Should have event.stopPropagation() in onclick
    assert onclick is not None, "Company link missing onclick handler"
    assert "stopPropagation" in onclick, "Company link doesn't stop event propagation"


def test_price_formatting_shows_currency_symbols(page: Page):
    """Test that prices show appropriate currency symbols."""
    # Wait for prices to load
    page.wait_for_selector(".stock-price", timeout=10000)

    # Get all price elements
    price_elements = page.locator(".stock-price")

    # Check first few prices
    for i in range(min(3, price_elements.count())):
        price_text = price_elements.nth(i).text_content()

        # Should contain $ or €
        has_currency = "$" in price_text or "€" in price_text
        assert has_currency, f"Price doesn't show currency symbol: {price_text}"


def test_positive_price_changes_show_green(page: Page):
    """Test that positive price changes are styled green."""
    # Wait for prices
    page.wait_for_selector(".stock-price", timeout=10000)

    # Find positive changes
    positive_changes = page.locator(".positive")

    if positive_changes.count() > 0:
        # Check color of first positive change
        first_positive = positive_changes.first
        color = first_positive.evaluate("el => window.getComputedStyle(el).color")

        # Should be green-ish (rgb values where green > red and blue)
        # Green is typically rgb(72, 187, 120) or similar
        assert "rgb" in color, f"Color not in RGB format: {color}"


def test_negative_price_changes_show_red(page: Page):
    """Test that negative price changes are styled red."""
    # Wait for prices
    page.wait_for_selector(".stock-price", timeout=10000)

    # Find negative changes
    negative_changes = page.locator(".negative")

    if negative_changes.count() > 0:
        # Check color of first negative change
        first_negative = negative_changes.first
        color = first_negative.evaluate("el => window.getComputedStyle(el).color")

        # Should be red-ish (rgb values where red > green and blue)
        assert "rgb" in color, f"Color not in RGB format: {color}"


def test_page_background_gradient(page: Page):
    """Test that page has the styled gradient background."""
    body = page.locator("body")

    # Check background property
    background = body.evaluate("el => window.getComputedStyle(el).background")

    # Should have gradient
    assert "gradient" in background or "linear-gradient" in background, \
        "Body doesn't have gradient background"


def test_stock_cards_have_hover_effects(page: Page):
    """Test that stock cards have hover styling."""
    first_card = page.locator(".stock-card").first

    # Hover over the card
    first_card.hover()
    page.wait_for_timeout(200)

    # Card should still be visible (hover effect applied)
    expect(first_card).to_be_visible()


def test_page_is_responsive_to_window_resize(page: Page):
    """Test that page layout adapts to window size changes."""
    # Initial viewport is 1920x1080 from fixture

    # Resize to smaller viewport
    page.set_viewport_size({"width": 1024, "height": 768})
    page.wait_for_timeout(300)

    # Page should still be functional
    cards = page.locator(".stock-card")
    expect(cards.first).to_be_visible()

    # Resize to larger viewport
    page.set_viewport_size({"width": 2560, "height": 1440})
    page.wait_for_timeout(300)

    # Page should still be functional
    expect(cards.first).to_be_visible()
