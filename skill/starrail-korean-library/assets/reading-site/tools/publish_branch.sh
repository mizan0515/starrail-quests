#!/usr/bin/env bash
set -euo pipefail
# The workflow owns this generated branch. Push normally, preserving its history.
test -f dist/index.html
test -f dist/pagefind/pagefind.js
touch dist/.nojekyll
printf '{"sourceCommit":"%s","repository":"%s"}\n' "$GITHUB_SHA" "$GITHUB_REPOSITORY" > dist/site-version.json
git fetch origin gh-pages
git worktree add --detach "$RUNNER_TEMP/starrail-pages" FETCH_HEAD
rsync -a --delete --exclude='.git' dist/ "$RUNNER_TEMP/starrail-pages/"
git -C "$RUNNER_TEMP/starrail-pages" config user.name 'github-actions[bot]'
git -C "$RUNNER_TEMP/starrail-pages" config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git -C "$RUNNER_TEMP/starrail-pages" add --all
if ! git -C "$RUNNER_TEMP/starrail-pages" diff --cached --quiet; then
  git -C "$RUNNER_TEMP/starrail-pages" commit -m "Publish verified Korean library from $GITHUB_SHA"
  taskRevision=$(git -C "$RUNNER_TEMP/starrail-pages" rev-parse HEAD)
  git push origin "$taskRevision:gh-pages"
fi
