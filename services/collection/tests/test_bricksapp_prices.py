from app.business.bricksapp_prices import (
    extract_prices_bl,
    parse_bricksapp_price_guide,
)

# Как в RSC-странице BricksAPP: кавычки экранированы.
_PAGE = r"""
initialPriceGuide\":{\"pricesBA\":{},\"pricesBL\":{\"UsedLast6mSales\":18,\"UsedLast6mQty\":18,\"UsedLast6mMinPrice\":4.6169,\"UsedLast6mQtyAvgPrice\":6.4656,\"UsedLast6mMaxPrice\":8.898,\"UsedCurrentSales\":24,\"UsedCurrentQty\":30,\"UsedCurrentMinPrice\":5.6625,\"UsedCurrentQtyAvgPrice\":9.3469,\"UsedCurrentMaxPrice\":23.13,\"NewLast6mSales\":14,\"NewLast6mQty\":41,\"NewLast6mMinPrice\":6.1948,\"NewLast6mQtyAvgPrice\":8.4518,\"NewLast6mMaxPrice\":17.01,\"NewCurrentSales\":0,\"NewCurrentQty\":0,\"NewCurrentMinPrice\":0,\"NewCurrentQtyAvgPrice\":0,\"NewCurrentMaxPrice\":0}}
"""


def test_extracts_escaped_prices_bl():
    data = extract_prices_bl(_PAGE)
    assert data["UsedLast6mSales"] == 18
    assert data["NewLast6mQtyAvgPrice"] == 8.4518


def test_maps_sales_and_skips_zero_blocks():
    parsed = parse_bricksapp_price_guide(_PAGE, "bob016")
    assert parsed.error is None
    assert parsed.currency == "USD"
    assert parsed.used.avg_6m == 6.4656
    assert parsed.used.times_sold_6m == 18
    assert parsed.used.total_lots == 24
    assert parsed.used.avg_listed == 9.3469
    assert parsed.new.avg_6m == 8.4518
    assert parsed.new.times_sold_6m == 14
    assert parsed.new.total_lots is None


def test_page_without_guide_is_not_found():
    parsed = parse_bricksapp_price_guide("<html>no such minifig</html>", "bob999zzz")
    assert parsed.error == "not_found"
