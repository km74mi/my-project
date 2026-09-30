"""Build the single-file Life Plan app from src/lifeplan.src.html.

The source keeps the portrait as a placeholder (__MZ_IMG__) so the photo is
never committed. If assets/mizuki.jpg exists locally (gitignored), it is
embedded as a data URI; otherwise a soft gradient is used instead.
"""

import argparse
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "lifeplan.src.html"
PHOTO = ROOT / "assets" / "mizuki.jpg"
FALLBACK = "linear-gradient(160deg, #EEDCD6, #D8C29C)"


def portrait_css() -> str:
    """Return the CSS value for --mz-img."""
    if PHOTO.exists():
        data = base64.b64encode(PHOTO.read_bytes()).decode("ascii")
        return f'url("data:image/jpeg;base64,{data}")'
    return FALLBACK


def main() -> None:
    parser = argparse.ArgumentParser(description="ライフプランアプリを1枚のHTMLにまとめます")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "index.html", help="出力先 (既定: dist/index.html)")
    args = parser.parse_args()

    html = SRC.read_text(encoding="utf-8").replace("__MZ_IMG__", portrait_css())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    photo = "写真あり" if PHOTO.exists() else "写真なし(グラデーションで代用)"
    print(f"書き出しました: {args.output} ({photo})")


if __name__ == "__main__":
    main()
