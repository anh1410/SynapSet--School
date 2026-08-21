from app.services.image_generation import generate_image


def test_generate_image_returns_valid_png():
    png = generate_image("minimalist black line art of a frog on a lily pad")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 100


def test_generate_image_is_deterministic_for_same_prompt():
    a = generate_image("a cartoon sun")
    b = generate_image("a cartoon sun")
    assert a == b


def test_generate_image_differs_for_different_prompts():
    a = generate_image("a cartoon sun")
    b = generate_image("a cartoon frog")
    assert a != b
