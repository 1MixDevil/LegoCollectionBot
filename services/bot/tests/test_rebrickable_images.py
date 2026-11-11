from app.services.rebrickable_images import candidate_image_urls, is_image_payload


def test_rejects_maintenance_html_even_if_status_would_be_200():
    html = b"<!DOCTYPE html><html><body>maintenance</body></html>" + b" " * 300
    assert is_image_payload(html, "text/html") is False
    assert is_image_payload(html, "image/jpeg") is False


def test_accepts_jpeg_and_png_magic():
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 250
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 250
    assert is_image_payload(jpeg, "image/jpeg")
    assert is_image_payload(png, "image/png")
    assert is_image_payload(b"\xff\xd8\xff", "image/jpeg") is False


def test_bob016_candidates_try_rebrickable_then_brickset_then_bricklink():
    mapped = {"bob016": "https://cdn.rebrickable.com/media/sets/fig-003272.jpg"}
    urls = candidate_image_urls("bob016", mapped)
    assert urls[0].endswith("fig-003272.jpg")
    assert urls[1] == "https://images.brickset.com/minifigs/large/bob016.jpg"
    assert any(u.endswith("/bob016.png") and "bricklink.com" in u for u in urls)
    assert any(u.endswith("/bob016.jpg") and "bricklink.com" in u for u in urls)
