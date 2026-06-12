"""Generate the PWA icons (run once; output is committed)."""
from pathlib import Path

from PIL import Image, ImageDraw

WEB = Path(__file__).resolve().parent.parent / "whisprompt" / "web"


def make_icon(size: int, dest: Path) -> None:
    img = Image.new("RGB", (size, size), "#101418")
    d = ImageDraw.Draw(img)
    cx, s = size / 2, size / 1024  # design space: 1024

    # microphone capsule
    d.rounded_rectangle(
        [cx - 130 * s, 220 * s, cx + 130 * s, 560 * s],
        radius=130 * s, fill="#4d7cc7",
    )
    # pickup arc
    d.arc([cx - 220 * s, 320 * s, cx + 220 * s, 700 * s],
          start=20, end=160, fill="#e8eaed", width=int(44 * s))
    # stem + base
    d.rectangle([cx - 22 * s, 690 * s, cx + 22 * s, 790 * s], fill="#e8eaed")
    d.rounded_rectangle([cx - 120 * s, 780 * s, cx + 120 * s, 824 * s],
                        radius=22 * s, fill="#e8eaed")
    # recording dot
    d.ellipse([cx + 150 * s, 150 * s, cx + 270 * s, 270 * s], fill="#e35d5d")

    img.save(dest)
    print(f"wrote {dest}")


if __name__ == "__main__":
    make_icon(180, WEB / "icon-180.png")
    make_icon(512, WEB / "icon-512.png")
