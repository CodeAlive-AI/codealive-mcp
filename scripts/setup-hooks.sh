#!/usr/bin/env sh
# Install the tracked pre-push hook without replacing a user-wide hooksPath.
# A user-wide dispatcher may invoke .git/hooks/pre-push; with the default Git
# configuration, Git invokes the same file directly.
set -eu

repo_root=$(git rev-parse --show-toplevel)
git_common_dir=$(git rev-parse --git-common-dir)

case "$git_common_dir" in
    /*) ;;
    *) git_common_dir="$repo_root/$git_common_dir" ;;
esac

hooks_dir="$git_common_dir/hooks"
target="$hooks_dir/pre-push"
source="$repo_root/.githooks/pre-push"

mkdir -p "$hooks_dir"

if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "Refusing to replace existing hook: $target" >&2
    echo "Move or merge that hook manually, then rerun this script." >&2
    exit 1
fi

ln -sfn "$source" "$target"
printf 'Installed pre-push hook: %s -> %s\n' "$target" "$source"

configured_hooks_path=$(git config --get core.hooksPath || true)
if [ -n "$configured_hooks_path" ]; then
    printf 'Note: core.hooksPath is %s; it must dispatch .git/hooks/pre-push.\n' "$configured_hooks_path"
fi
