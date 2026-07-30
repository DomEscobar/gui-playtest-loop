#!/usr/bin/env bash
# Copy this skill's essential files into a destination skill directory, e.g.
# a personal Cursor skills folder or a project's .cursor/skills/ directory.
#
# Usage:
#   ./install/install.sh <destination-directory>
#
# Example:
#   ./install/install.sh "$HOME/.cursor/skills/gui-playtest-loop"

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <destination-directory>" >&2
  exit 1
fi

destination="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

mkdir -p "$destination"

for item in SKILL.md AGENTS.md reference prompts templates scripts docs LICENSE README.md; do
  cp -R "$repo_root/$item" "$destination/"
done

echo "Installed gui-playtest-loop into: $destination"
echo "Point your agent at $destination/SKILL.md to start."
