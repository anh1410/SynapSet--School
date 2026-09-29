"""Renders Devanagari/Kannada text to a correctly-shaped PNG for embedding
into exported PDFs.

ReportLab's text drawing has no OpenType shaping engine: it maps each
Unicode codepoint straight to a glyph in logical order, which is fine for
Latin script but wrong for Devanagari/Kannada - vowel signs that must
visually reorder before their consonant, and consonants that must merge
into a conjunct ligature, come out as separate/misplaced/garbled glyphs
instead (confirmed by direct rendering test before writing this module).
HarfBuzz (via uharfbuzz) does real OpenType shaping; FreeType (via
freetype-py) rasterizes the shaped glyphs; the result is composited into
one transparent PNG here, then embedded as an inline image in the PDF -
the same pattern paper_export.py already uses for LaTeX math
(_rasterize_mathtext), and for the same underlying reason: reportlab
can't draw this directly as text.

python-docx's DOCX path is NOT affected by any of this - Word performs
its own text shaping at open-time on the reader's machine, so this
module is PDF-export-only.
"""

import io
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT_PATHS = {
    "devanagari": _FONT_DIR / "NotoSansDevanagari-Regular.ttf",
    "kannada": _FONT_DIR / "NotoSansKannada-Regular.ttf",
}

# Unicode blocks covering base letters, digits, and combining marks (matras,
# virama) for each script - enough to *detect* which font a string needs.
_SCRIPT_RANGES = {
    "devanagari": (0x0900, 0x097F),
    "kannada": (0x0C80, 0x0CFF),
}

_HB_SCRIPT_TAG = {"devanagari": "Deva", "kannada": "Knda"}
_HB_LANGUAGE = {"devanagari": "hi", "kannada": "kn"}

_font_bytes_cache: dict[str, bytes] = {}


def detect_script(text: str) -> str | None:
    """Returns 'devanagari' or 'kannada' if `text` contains any character
    from that script's Unicode block, else None (plain Latin/ASCII - the
    caller should use normal Paragraph rendering). A string mixing both
    scripts (rare) renders entirely in whichever is found first - not
    worth per-run font-switching for a case this unlikely in one field."""
    for ch in text:
        cp = ord(ch)
        for script, (lo, hi) in _SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                return script
    return None


def _font_bytes(script: str) -> bytes:
    if script not in _font_bytes_cache:
        _font_bytes_cache[script] = _FONT_PATHS[script].read_bytes()
    return _font_bytes_cache[script]


def _glyph_to_image(bitmap) -> Image.Image | None:
    """FreeType bitmap rows are padded to `pitch` bytes, not `width` -
    reading the raw buffer without accounting for that shears the glyph
    into visual garbage (this was the actual bug the first time through)."""
    if bitmap.width == 0 or bitmap.rows == 0:
        return None
    raw = bytes(bitmap.buffer)
    rows = [raw[r * bitmap.pitch : r * bitmap.pitch + bitmap.width] for r in range(bitmap.rows)]
    return Image.frombytes("L", (bitmap.width, bitmap.rows), b"".join(rows))


def _segment_runs(text: str, primary_script: str) -> list[tuple[str, str]]:
    """Splits `text` into (run_text, hb_script_tag) runs: characters inside
    `primary_script`'s Unicode block stay tagged with that script; every
    other character (Latin, digits, punctuation, whitespace) is grouped
    into a "Latn" run.

    This matters because shaping a whole mixed string as ONE HarfBuzz
    buffer - relying on guess_segment_properties() to figure out the
    script - was empirically found to corrupt glyphs specifically for
    Kannada whenever a Latin prefix preceded Kannada text (e.g. an MCQ
    option like "(a) ಬೆಂಗಳೂರು"); pure Kannada shaped correctly, and
    Devanagari tolerated the same mixed-buffer pattern fine. Rather than
    rely on that asymmetry not reappearing elsewhere, every run gets its
    own buffer with an explicit script (never guessed)."""
    lo, hi = _SCRIPT_RANGES[primary_script]
    primary_tag = _HB_SCRIPT_TAG[primary_script]
    runs: list[tuple[str, str]] = []
    current_tag: str | None = None
    current_chars: list[str] = []
    for ch in text:
        tag = primary_tag if lo <= ord(ch) <= hi else "Latn"
        if tag != current_tag and current_chars:
            runs.append(("".join(current_chars), current_tag))
            current_chars = []
        current_tag = tag
        current_chars.append(ch)
    if current_chars:
        runs.append(("".join(current_chars), current_tag))
    return runs


def _shape_run(hb_font: "hb.Font", run_text: str, script_tag: str, primary_script: str) -> "hb.Buffer":
    buf = hb.Buffer()
    buf.add_str(run_text)
    buf.direction = "ltr"
    buf.script = script_tag
    buf.language = _HB_LANGUAGE[primary_script] if script_tag != "Latn" else "en"
    hb.shape(hb_font, buf)
    return buf


def render_shaped_text_png(text: str, script: str, pixel_size: int = 48) -> bytes:
    """Shapes `text` with HarfBuzz (correct Devanagari/Kannada glyph
    reordering and conjunct formation) and rasterizes it with FreeType into
    one transparent-background PNG, ready to embed as an inline image."""
    font_path = str(_FONT_PATHS[script])

    hb_font = hb.Font(hb.Face(_font_bytes(script)))
    hb_font.scale = (pixel_size * 64, pixel_size * 64)

    ft_face = freetype.Face(font_path)
    ft_face.set_char_size(pixel_size * 64)

    pen_x = 0.0
    placed: list[tuple[Image.Image | None, int, int, float, float]] = []
    max_top = 0
    max_below = 0
    for run_text, script_tag in _segment_runs(text, script):
        buf = _shape_run(hb_font, run_text, script_tag, script)
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
            g = ft_face.glyph
            bmp = g.bitmap
            gx = pen_x + pos.x_offset / 64.0
            gy = pos.y_offset / 64.0
            placed.append((_glyph_to_image(bmp), g.bitmap_left, g.bitmap_top, gx, gy))
            max_top = max(max_top, g.bitmap_top)
            max_below = max(max_below, bmp.rows - g.bitmap_top)
            pen_x += pos.x_advance / 64.0

    width = max(int(pen_x) + 8, 1)
    height = max(int(max_top + max_below) + 8, 1)
    canvas = Image.new("L", (width, height), color=255)  # white bg, black ink
    for glyph_img, left, top, gx, gy in placed:
        if glyph_img is None:
            continue
        px = int(round(gx)) + left + 4
        py = int(max_top - top - gy) + 4
        canvas.paste(0, (px, py), mask=glyph_img)

    # Convert to transparent RGBA (alpha = ink coverage) so the page's own
    # background shows through, matching _rasterize_mathtext's convention.
    alpha = Image.eval(canvas, lambda p: 255 - p)
    rgba = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    black = Image.new("RGBA", canvas.size, (0, 0, 0, 255))
    rgba.paste(black, (0, 0), mask=alpha)

    out = io.BytesIO()
    rgba.save(out, format="PNG")
    return out.getvalue()
