# Photo OCR Scanner

指定したフォルダ内の写真を自動でスキャンし、写っている文字を OpenAI の GPT-4o (Vision) で読み取ってまとめるスクリプトです。

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env
# .env を開いて OPENAI_API_KEY に自分の OpenAI API キーを設定
```

## 使い方

```bash
python ocr_scan.py <写真フォルダのパス>
```

例:

```bash
python ocr_scan.py ~/Pictures/family_photos
```

デフォルトでは `output/` フォルダに以下が保存されます。

- `ocr_results.csv` — ファイル名と抽出したテキストの一覧表
- `ocr_results.txt` — 全結果を読みやすくまとめたテキストファイル

出力先を変えたい場合:

```bash
python ocr_scan.py ~/Pictures/family_photos --output ~/Desktop/results
```

## 対応フォーマット

`.jpg` `.jpeg` `.png` `.webp` `.gif` `.bmp` `.tiff`（サブフォルダも再帰的に検索します）

## 注意事項

- 写真の枚数が多いほど OpenAI API の利用料金がかかります。
- 個人情報や機微な内容が写った写真を扱う場合は取り扱いに注意してください。
