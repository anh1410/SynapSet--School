"""Generates the actual image bytes for a VisualPrompt.

No Imagen/DALL-E API key exists yet, so `generate_image` currently renders
a local placeholder card instead of calling a real image model. The
signature (str -> PNG bytes) is the whole contract: swap the function body
for a real API call once a key exists, and nothing upstream changes.
"""

import hashlib
import io
import textwrap

_PALETTE = [
    "#FFD166",  # yellow
    "#06D6A0",  # green
    "#118AB2",  # blue
    "#EF476F",  # red
    "#8338EC",  # purple
    "#FB8500",  # orange
]


def _color_for(prompt: str) -> str:
    """Deterministic (not random) so re-generating the same prompt string
    always gets the same placeholder color — useful for debugging/tests."""
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return _PALETTE[int(digest, 16) % len(_PALETTE)]


def generate_image(prompt: str) -> bytes:
    """Swappable image-generation interface. Currently a local placeholder
    renderer via Matplotlib (already a hard dependency for diagram
    rendering, so no second image library is needed); swap the body for a
    real Imagen/DALL-E call once an API key exists."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(3, 3))
    ax.add_patch(
        FancyBboxPatch(
            (0.05, 0.05), 0.9, 0.9, boxstyle="round,pad=0.02,rounding_size=0.05",
            linewidth=0, facecolor=_color_for(prompt), transform=ax.transAxes,
        )
    )
    wrapped = textwrap.fill(prompt, width=20)
    ax.text(0.5, 0.5, wrapped, ha="center", va="center", fontsize=11, color="white", transform=ax.transAxes)
    ax.axis("off")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
