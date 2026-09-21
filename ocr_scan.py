"""Scan a folder of photos and extract all visible text using OpenAI's vision model.

Usage:
    python ocr_scan.py <folder_path> [--output output]

Requires OPENAI_API_KEY to be set (in the environment or a .env file).
"""

import argparse
import base64
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

PROMPT = (
    "この画像に写っている文字を、レイアウトの順序を保ったまま全て書き起こしてください。"
    "文字が写っていない場合は「文字なし」とだけ答えてください。"
)


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def extract_text(client: OpenAI, path: Path) -> str:
    image_b64 = encode_image(path)
    mime = f"image/{path.suffix.lstrip('.').lower().replace('jpg', 'jpeg')}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="写真が入っているフォルダのパス")
    parser.add_argument(
        "--output", type=Path, default=Path("output"), help="結果の出力先フォルダ (default: output)"
    )
    args = parser.parse_args()

    if not args.folder.is_dir():
        sys.exit(f"フォルダが見つかりません: {args.folder}")

    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY が設定されていません (.env またはenv変数を確認してください)")

    client = OpenAI(api_key=api_key)

    images = sorted(
        p for p in args.folder.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not images:
        sys.exit(f"対応する画像ファイルが見つかりません: {args.folder}")

    args.output.mkdir(parents=True, exist_ok=True)
    csv_path = args.output / "ocr_results.csv"
    txt_path = args.output / "ocr_results.txt"

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file, txt_path.open(
        "w", encoding="utf-8"
    ) as txt_file:
        writer = csv.writer(csv_file)
        writer.writerow(["filename", "extracted_text"])

        for i, image_path in enumerate(images, 1):
            print(f"[{i}/{len(images)}] 解析中: {image_path.name}")
            try:
                text = extract_text(client, image_path)
            except Exception as exc:  # noqa: BLE001
                text = f"[エラー] {exc}"

            writer.writerow([image_path.name, text])
            txt_file.write(f"=== {image_path.name} ===\n{text}\n\n")

    print(f"\n完了しました。結果は {csv_path} と {txt_path} に保存されました。")


if __name__ == "__main__":
    main()
