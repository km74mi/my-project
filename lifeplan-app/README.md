# みずきのライフプラン(Mizuki's Life Plan)

キャバ嬢さん(キャスト)向けのライフプランシミュレーター。7つの質問に答えると、「今月貯めたいお金」から90歳までのお金の流れまでを、グラフと表で見られる。講座の受講生に、自分のお金の状況に気づいてもらうためのアプリ。

- 公開中のページ(Claude のアーティファクト):https://claude.ai/artifact/N7AAnk8pfmapNPQ2foiw2d
  - 非公開の設定。受講生に見せるときは、ページの共有メニューから公開する。
- 形式:HTML 1枚で動く React アプリ(React 18 と htm を CDN から読み込み。ビルド作業は不要)
- 入力した内容は、見ている人の端末(ブラウザの localStorage)の中だけに保存される。サーバーには送らない。

## フォルダの中身

| パス | 中身 |
| --- | --- |
| `src/lifeplan.src.html` | アプリ本体のソース。写真の部分だけ `__MZ_IMG__` という目印になっている |
| `build.py` | ソースから `dist/index.html` を作る。手元に写真があれば埋め込む |
| `dist/index.html` | 書き出したアプリ(写真なし版。写真の所はグラデーションで代用) |
| `scripts/check.js` | スマホ幅で開いて、各画面のスクリーンショットを撮る確認用スクリプト |
| `docs/` | 作るまでの経緯・設計・計算方法・仮の数字など(下の一覧) |
| `../.claude/skills/lifeplan-simulator/SKILL.md` | このアプリを直すとき・作り直すときに Claude が使う手順書(スキル) |

### docs の一覧

1. [01_要件と経緯.md](docs/01_要件と経緯.md) — 何のために作ったか、アンケート結果、ペルソナ、やりとりの流れ
2. [02_画面構成.md](docs/02_画面構成.md) — 質問7つと結果画面の中身
3. [03_計算ロジック.md](docs/03_計算ロジック.md) — シミュレーション・診断・「今月の目標」などの計算方法
4. [04_デザイン.md](docs/04_デザイン.md) — みずき相談ルームに合わせたデザイン、配色、グラフの色の検証
5. [05_仮の数字と確認事項.md](docs/05_仮の数字と確認事項.md) — 講座側で確認・差し替えが必要な数字
6. [06_参考資料とフィードバック.md](docs/06_参考資料とフィードバック.md) — 参考にしたサイト・画像、受講生管理シートの確認メモ

## 写真について(大事)

このリポジトリは**公開**なので、みずきさんの写真は入れていない。写真入りで書き出すときは、手元で次のようにする。

```bash
# assets/mizuki.jpg に写真を置く(.gitignore 済みなのでコミットされない)
mkdir -p assets && cp <写真のパス> assets/mizuki.jpg
python build.py            # → dist/index.html に写真が埋め込まれる
```

写真入りの `dist/index.html` はコミットしないこと(`git checkout dist/index.html` で写真なし版に戻す)。

## 書き出しと確認

```bash
python build.py                                   # dist/index.html を作る
npm install playwright react@18.3.1 react-dom@18.3.1 htm@3.1.1   # 確認スクリプト用(初回のみ)
node scripts/check.js                             # screenshots/ に各画面の画像ができる
```

確認するときに見るところ:ページのエラーが出ていないか、`scrollWidth=390`(スマホで横にはみ出していない)か、ライト・ダーク両方で文字が読めるか。

## アーティファクトを更新するとき

Claude に「ライフプランアプリを直して」と頼むと、`.claude/skills/lifeplan-simulator/SKILL.md` の手順で作業する。アーティファクトの URL を変えずに更新するには、上の URL を伝える。
