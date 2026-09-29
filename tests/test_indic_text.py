from PIL import Image
import io

from app.services.indic_text import detect_script, render_shaped_text_png


def test_detect_script_devanagari():
    assert detect_script("प्रकाश संश्लेषण") == "devanagari"


def test_detect_script_kannada():
    assert detect_script("ಕರ್ನಾಟಕ") == "kannada"


def test_detect_script_latin_is_none():
    assert detect_script("Photosynthesis") is None
    assert detect_script("CO2 + H2O = 123") is None


def test_detect_script_mixed_finds_the_non_latin_part():
    assert detect_script("CO2 is कार्बन डाइऑक्साइड") == "devanagari"


def test_render_devanagari_returns_valid_png():
    png = render_shaped_text_png("प्रकाश संश्लेषण किसे कहते हैं?", "devanagari")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.mode == "RGBA"
    assert img.width > 50
    assert img.height > 10


def test_render_kannada_returns_valid_png():
    png = render_shaped_text_png("ಕರ್ನಾಟಕ ರಾಜ್ಯದ ರಾಜಧಾನಿ ಯಾವುದು?", "kannada")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.width > 50


def test_render_width_grows_with_more_text():
    """Basic regression guard against the pitch bug (garbled/near-empty
    glyphs): a longer string must render meaningfully wider than a shorter
    prefix of the same string."""
    short_png = render_shaped_text_png("ಕರ್ನಾಟಕ", "kannada")
    long_png = render_shaped_text_png("ಕರ್ನಾಟಕ ರಾಜ್ಯದ ರಾಜಧಾನಿ ಯಾವುದು?", "kannada")
    short_w = Image.open(io.BytesIO(short_png)).width
    long_w = Image.open(io.BytesIO(long_png)).width
    assert long_w > short_w * 2
