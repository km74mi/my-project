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
- 講座本編(コンテンツ01-1〜09)の要点メモは、有料講座の内容なので別の非公開リポジトリに置いている(名前はユーザーに聞く)。講座の中身が必要な作業ではそちらを読む。このリポジトリには講座本編の中身を書かない(LP に載っている範囲は `.claude/knowledge/course-overview.md`)。

## スキルと知識の自動蓄積
言われなくても毎回やる。
- セッション開始時に `.claude/skills/` と `.claude/knowledge/` の一覧が自動で読み込まれる。依頼に関係するスキル・メモがあれば、指示がなくても読んで使う。
- 作業の中で「次も使えそうな手順」ができたら `.claude/skills/<名前>/SKILL.md` にスキルとして保存する(既存スキルに近ければそちらを更新)。作り方は skill-creator スキルがあれば使う。
- ユーザーの好み・決めたこと・覚えておくべき事実がわかったら `.claude/knowledge/` のメモに追記する(書き方は `.claude/knowledge/README.md`)。
- 保存したものは他の変更と一緒にコミット・プッシュする。デフォルトブランチにマージされると、次のセッションから使える。
- 公開リポジトリなので、個人情報・API キー・写真はスキルにもメモにも書かない。
