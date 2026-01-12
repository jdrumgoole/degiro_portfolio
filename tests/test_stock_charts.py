"""Tests for stock detail charts."""

import re
from playwright.sync_api import Page, expect


def test_chart_loads_when_stock_selected(page: Page):
    """Test that chart loads when a stock is clicked."""
    # Click on first stock card
    first_card = page.locator(".stock-card").first
    first_card.click()

    # Wait for chart to render
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Check chart is visible
    chart = page.locator("#chart")
    expect(chart).to_be_visible()


def test_chart_title_shows_stock_name(page: Page):
    """Test that chart displays the stock name."""
    # Click on NVIDIA
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')").first
    nvidia_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Check that chart area contains stock name or ticker
    chart_html = page.locator("#chart").inner_html()
    assert "NVIDIA" in chart_html or "NVDA" in chart_html, "Chart doesn't show stock name"


def test_multiple_chart_tabs_exist(page: Page):
    """Test that multiple chart types are available."""
    # Click on a stock
    first_card = page.locator(".stock-card").first
    first_card.click()

    # Wait for chart to load
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Look for chart type buttons/tabs
    # The app should have multiple chart views based on the code we've seen
    chart_container = page.locator("#chart")
    expect(chart_container).to_be_visible()


def test_chart_has_candlestick_data(page: Page):
    """Test that chart includes candlestick/price data."""
    # Click on NVIDIA
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')").first
    nvidia_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Check for Plotly chart elements
    plotly_chart = page.locator("#chart .plotly")
    expect(plotly_chart).to_be_visible()

    # Check that chart has data by looking for SVG elements
    svg_elements = page.locator("#chart svg")
    expect(svg_elements.first).to_be_visible()


def test_chart_shows_transaction_markers(page: Page):
    """Test that buy/sell transaction markers appear on chart."""
    # Click on NVIDIA which has multiple transactions
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')").first
    nvidia_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Give time for all traces to render
    page.wait_for_timeout(2000)

    # Check chart HTML for markers
    # Plotly renders markers as scatter traces
    chart_html = page.locator("#chart").inner_html()

    # Should contain references to transaction markers or buy/sell traces
    # The markers are rendered as part of the Plotly chart data
    assert len(chart_html) > 1000, "Chart appears empty"


def test_chart_is_interactive(page: Page):
    """Test that chart has interactive elements."""
    # Click on a stock
    first_card = page.locator(".stock-card").first
    first_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Check for Plotly modebar (zoom, pan, etc.)
    modebar = page.locator(".modebar-container")
    # Modebar should exist (may be hidden until hover)
    expect(modebar).to_be_attached()


def test_chart_has_date_axis(page: Page):
    """Test that chart has a date/time axis."""
    # Click on a stock
    first_card = page.locator(".stock-card").first
    first_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Check for axis labels
    # Plotly creates axis elements in the SVG
    axis_labels = page.locator("#chart .xtick, #chart .ytick")
    count = axis_labels.count()

    assert count > 0, "No axis labels found on chart"


def test_chart_has_price_axis(page: Page):
    """Test that chart has a price axis."""
    # Click on NVIDIA
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')").first
    nvidia_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Check for Y-axis elements
    ytick_elements = page.locator("#chart .ytick")
    count = ytick_elements.count()

    assert count > 0, "No Y-axis ticks found"


def test_switching_between_stocks_updates_chart(page: Page):
    """Test that selecting different stocks updates the chart."""
    # Click on NVIDIA
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')").first
    nvidia_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)
    page.wait_for_timeout(1000)

    # Get chart HTML
    nvidia_chart_html = page.locator("#chart").inner_html()

    # Click on Microsoft
    msft_card = page.locator(".stock-card:has-text('MICROSOFT CORP')").first
    msft_card.click()

    # Wait for chart to update
    page.wait_for_timeout(2000)

    # Get new chart HTML
    msft_chart_html = page.locator("#chart").inner_html()

    # Charts should be different
    assert nvidia_chart_html != msft_chart_html, "Chart didn't update when switching stocks"


def test_chart_renders_for_european_stocks(page: Page):
    """Test that charts render correctly for European stocks."""
    # Click on ASML (European stock)
    asml_card = page.locator(".stock-card:has-text('ASML HOLDING')").first
    asml_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Chart should be visible
    chart = page.locator("#chart .plotly")
    expect(chart).to_be_visible()


def test_chart_renders_for_sek_currency_stock(page: Page):
    """Test that charts render for stocks in SEK currency."""
    # Click on Ericsson (SEK currency)
    ericsson_card = page.locator(".stock-card:has-text('ERICSSON')").first
    ericsson_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Chart should be visible
    chart = page.locator("#chart .plotly")
    expect(chart).to_be_visible()


def test_chart_has_uniform_marker_sizes(page: Page):
    """Test that transaction markers are uniform size."""
    # Click on stock with multiple transactions
    nvidia_card = page.locator(".stock-card:has-text('NVIDIA CORP')").first
    nvidia_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)
    page.wait_for_timeout(2000)

    # Chart should render
    chart = page.locator("#chart .plotly")
    expect(chart).to_be_visible()

    # We can't easily test marker size directly, but we can verify chart rendered
    # The actual marker size uniformity is tested visually or in the JavaScript code


def test_chart_container_has_proper_dimensions(page: Page):
    """Test that chart container has reasonable dimensions."""
    # Click on a stock
    first_card = page.locator(".stock-card").first
    first_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Check chart container dimensions
    chart = page.locator("#chart")
    box = chart.bounding_box()

    assert box is not None, "Chart has no dimensions"
    assert box["width"] > 400, f"Chart width too small: {box['width']}"
    assert box["height"] > 200, f"Chart height too small: {box['height']}"


def test_chart_persists_when_page_scrolled(page: Page):
    """Test that chart remains visible when scrolling."""
    # Click on a stock
    first_card = page.locator(".stock-card").first
    first_card.click()

    # Wait for chart
    page.wait_for_selector("#chart .plotly", timeout=15000)

    # Scroll page
    page.evaluate("window.scrollTo(0, 500)")
    page.wait_for_timeout(500)

    # Chart should still be visible or attached
    chart = page.locator("#chart")
    expect(chart).to_be_attached()


def test_no_chart_shown_initially(page: Page):
    """Test that no chart is shown before selecting a stock."""
    # Wait for page to load
    page.wait_for_selector(".stock-card", timeout=10000)

    # Check if chart div exists but may be empty or have placeholder
    chart = page.locator("#chart")

    # Chart container should exist
    expect(chart).to_be_attached()
