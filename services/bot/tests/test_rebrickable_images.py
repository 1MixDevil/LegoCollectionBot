from app.services.rebrickable_images import candidate_image_urls, is_image_payload


def test_rejects_maintenance_html_even_if_status_would_be_200():
    html = b"<!DOCTYPE html><html><body>maintenance</body></html>" + b" " * 300
    assert is_image_payload(html, "text/html") is False
    assert is_image_payload(html, "image/jpeg") is False


def test_http_404_placeholder_is_not_a_photo():
    """bricker.info отдаёт 404 и маленький PNG «нет картинки» — его нельзя брать."""
    from app.services.rebrickable_images import response_is_figure_image

    placeholder = b"\x89PNG\r\n\x1a\n" + b"\x00" * 250
    assert response_is_figure_image(404, placeholder, "image/png") is False
    assert response_is_figure_image(200, placeholder, "image/png") is True


def test_accepts_jpeg_and_png_magic():
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 250
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 250
    assert is_image_payload(jpeg, "image/jpeg")
    assert is_image_payload(png, "image/png")
    assert is_image_payload(b"\xff\xd8\xff", "image/jpeg") is False


def test_candidates_use_id_templates_for_every_minifig():
    mapped = {
        "bob016": "https://cdn.rebrickable.com/media/sets/fig-003272.jpg",
        "bob040": "https://cdn.rebrickable.com/media/sets/fig-018130.jpg",
    }
    bob016 = candidate_image_urls("bob016", mapped)
    bob040 = candidate_image_urls("bob040", mapped)
    assert bob016[0].endswith("fig-003272.jpg")
    assert bob040[0].endswith("fig-018130.jpg")
    for bid, urls in (("bob016", bob016), ("bob040", bob040)):
        assert f"https://bricker.info/images/minifigs/{bid}.png" in urls
        assert f"https://images.brickset.com/minifigs/large/{bid}.jpg" in urls
        assert (
            f"https://www.brickeconomy.com/resources/images/minifigs/{bid}_large.jpg"
            in urls
        )
        assert any(u.endswith(f"/{bid}.png") and "bricklink.com" in u for u in urls)
        assert any(u.endswith(f"/{bid}.jpg") and "bricklink.com" in u for u in urls)
