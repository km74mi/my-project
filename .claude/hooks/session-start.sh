#!/bin/bash
# Runs at the start of every Claude Code session.
# stdout is added to Claude's context, so saved knowledge is always loaded.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}"

# Install Python dependencies on Claude Code on the web (keep stdout clean).
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  pip install -q -r requirements.txt >&2 || echo "pip install に失敗しました" >&2
fi

echo "## このリポジトリに保存されたスキルと知識(自動読み込み)"
echo
echo "### スキル (.claude/skills/) — 依頼に合うものは言われなくても使う"
found=0
for f in .claude/skills/*/SKILL.md; do
  [ -f "$f" ] || continue
  found=1
  name=$(sed -n 's/^name:[[:space:]]*//p' "$f" | head -1)
  desc=$(sed -n 's/^description:[[:space:]]*//p' "$f" | head -1)
  echo "- ${name:-$(basename "$(dirname "$f")")}: ${desc} (${f})"
done
[ "$found" = 1 ] || echo "- (まだありません)"
echo
echo "### 知識メモ (.claude/knowledge/)"
found=0
for f in .claude/knowledge/*.md; do
  [ -f "$f" ] || continue
  [ "$(basename "$f")" = "README.md" ] && continue
  found=1
  echo
  echo "#### ${f}"
  head -c 4000 "$f"
  echo
done
[ "$found" = 1 ] || echo "- (まだありません)"
echo
echo "作業中に次も使える手順や覚えておくべきことが出てきたら、CLAUDE.md の「スキルと知識の自動蓄積」に従って保存する。"
