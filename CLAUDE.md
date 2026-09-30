# CLAUDE.md

## 言語
- 回答・コミットメッセージの説明は日本語で書く。コード中のコメント・docstring は既存に合わせる（docstring は英語、ユーザー向けメッセージは日本語）。

## プロジェクト概要
このリポジトリには2つのものが入っている。

1. 写真 OCR スクリプト:写真フォルダ内の画像を OpenAI GPT-4o (Vision) で OCR し、結果を CSV / TXT にまとめる単一スクリプト。
2. `lifeplan-app/` — キャスト向けライフプランシミュレーター「みずきのライフプラン」(講座で使う React の単一 HTML アプリ)。作業するときは `.claude/skills/lifeplan-simulator/SKILL.md` と `lifeplan-app/README.md` を読む。

以下のファイル一覧と「実行」は OCR スクリプトの説明。

- `ocr_scan.py` — 本体（CLI・画像探索・API 呼び出し・出力をすべて含む）
- `requirements.txt` — 依存（`openai`, `python-dotenv`）
- `.env.example` — `OPENAI_API_KEY` のテンプレート（`.env` はコミットしない）
- 出力先 `output/` は `.gitignore` 済み

## 実行
```bash
pip install -r requirements.txt
python ocr_scan.py <写真フォルダ> [--output <出力先>]
```
- 実行には `OPENAI_API_KEY` が必要で、API 利用料金が発生する。キーが無い環境では実際の OCR 実行はせず、`python -m py_compile ocr_scan.py` と `python ocr_scan.py --help` で確認する。

## 方針
- 小さなリポジトリなので、変更は最小限・既存のスタイル（型ヒント、pathlib、日本語のユーザー向けメッセージ）に合わせる。
- API キーや個人情報を含む画像・出力をコミットしない。
- このリポジトリは公開。`lifeplan-app` のみずきさんの写真(`lifeplan-app/assets/`)や、写真入りで書き出した HTML はコミットしない。
