#!/usr/bin/env bash
# Sync skill metadata to AGENTS.md Auto-invoke sections
# Usage: ./sync.sh [--dry-run] [--scope <scope>]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
SKILLS_DIR="$REPO_ROOT/skills"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Options
DRY_RUN=false
FILTER_SCOPE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --scope) FILTER_SCOPE="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--scope <scope>]"
            echo "Scopes: root, providers, services, web"
            exit 0 ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

# Map scope to AGENTS.md path — octotrace layout
get_agents_path() {
    local scope="$1"
    case "$scope" in
        root)      echo "$REPO_ROOT/AGENTS.md" ;;
        providers) echo "$REPO_ROOT/src/cryptotrace/providers/AGENTS.md" ;;
        services)  echo "$REPO_ROOT/src/cryptotrace/services/AGENTS.md" ;;
        web)       echo "$REPO_ROOT/src/cryptotrace/web/AGENTS.md" ;;
        *)         echo "" ;;
    esac
}

extract_field() {
    local file="$1"
    local field="$2"
    awk -v field="$field" '
        /^---$/ { in_frontmatter = !in_frontmatter; next }
        in_frontmatter && $1 == field":" {
            sub(/^[^:]+:[[:space:]]*/, "")
            if ($0 != "" && $0 != ">") {
                gsub(/^["'"'"']|["'"'"']$/, "")
                print; exit
            }
            getline
            while (/^[[:space:]]/ && !/^---$/) {
                sub(/^[[:space:]]+/, "")
                printf "%s ", $0
                if (!getline) break
            }
            print ""; exit
        }
    ' "$file" | sed 's/[[:space:]]*$//'
}

extract_metadata() {
    local file="$1"
    local field="$2"
    awk -v field="$field" '
        function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
        /^---$/ { in_frontmatter = !in_frontmatter; next }
        in_frontmatter && /^metadata:/ { in_metadata = 1; next }
        in_frontmatter && in_metadata && /^[a-z]/ && !/^[[:space:]]/ { in_metadata = 0 }
        in_frontmatter && in_metadata && $1 == field":" {
            sub(/^[^:]+:[[:space:]]*/, "")
            if ($0 != "") {
                v = $0; gsub(/^["'"'"']|["'"'"']$/, "", v)
                gsub(/^\[|\]$/, "", v); print trim(v); exit
            }
            out = ""
            while (getline) {
                if (!in_frontmatter || !in_metadata) break
                if ($0 ~ /^[a-z]/ && $0 !~ /^[[:space:]]/) break
                line = $0
                if (line ~ /^---$/) break
                if (line ~ /^[[:space:]]*-[[:space:]]*/) {
                    sub(/^[[:space:]]*-[[:space:]]*/, "", line)
                    line = trim(line)
                    gsub(/^["'"'"']|["'"'"']$/, "", line)
                    if (line != "") { out = (out == "") ? line : out "|" line }
                } else { break }
            }
            if (out != "") print out; exit
        }
    ' "$file"
}

echo -e "${BLUE}Skill Sync — Octotrace${NC}"
echo "================================"
echo ""

SCOPE_TMPDIR=$(mktemp -d)
trap 'rm -rf "$SCOPE_TMPDIR"' EXIT

while IFS= read -r skill_file; do
    [ -f "$skill_file" ] || continue
    skill_name=$(extract_field "$skill_file" "name")
    scope_raw=$(extract_metadata "$skill_file" "scope")
    auto_invoke_raw=$(extract_metadata "$skill_file" "auto_invoke")
    auto_invoke=$(echo "$auto_invoke_raw" | sed 's/|/;;/g')
    [ -z "$scope_raw" ] || [ -z "$auto_invoke" ] && continue

    echo "$scope_raw" | tr ', ' '\n' | while read -r scope; do
        scope=$(echo "$scope" | tr -d '[:space:]')
        [ -z "$scope" ] && continue
        [ -n "$FILTER_SCOPE" ] && [ "$scope" != "$FILTER_SCOPE" ] && continue
        echo "$skill_name:$auto_invoke" >> "$SCOPE_TMPDIR/$scope"
    done
done < <(find "$SKILLS_DIR" -mindepth 2 -maxdepth 2 -name SKILL.md -print | sort)

for scope_file in "$SCOPE_TMPDIR"/*; do
    [ -f "$scope_file" ] || continue
    scope=$(basename "$scope_file")
    agents_path=$(get_agents_path "$scope")

    if [ -z "$agents_path" ] || [ ! -f "$agents_path" ]; then
        echo -e "${YELLOW}Warning: No AGENTS.md found for scope '$scope' at $agents_path${NC}"
        continue
    fi

    echo -e "${BLUE}Processing: $scope → $agents_path${NC}"

    auto_invoke_section="### Auto-invoke Skills

When performing these actions, ALWAYS invoke the corresponding skill FIRST:

| Action | Skill |
|--------|-------|"

    rows_file=$(mktemp)
    while IFS= read -r entry; do
        [ -z "$entry" ] && continue
        skill_name="${entry%%:*}"
        actions_raw=$(echo "${entry#*:}" | sed 's/;;/|/g')
        echo "$actions_raw" | tr '|' '\n' | while read -r action; do
            action=$(echo "$action" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
            [ -z "$action" ] && continue
            printf "%s\t%s\n" "$action" "$skill_name" >> "$rows_file"
        done
    done < "$scope_file"

    while IFS=$'\t' read -r action skill_name; do
        [ -z "$action" ] && continue
        auto_invoke_section="$auto_invoke_section
| $action | \`$skill_name\` |"
    done < <(LC_ALL=C sort -t $'\t' -k1,1 -k2,2 "$rows_file")
    rm -f "$rows_file"

    if $DRY_RUN; then
        echo -e "${YELLOW}[DRY RUN] Would update $agents_path with:${NC}"
        echo "$auto_invoke_section"
        echo ""
    else
        section_file=$(mktemp)
        echo "$auto_invoke_section" > "$section_file"

        if grep -q "### Auto-invoke Skills" "$agents_path"; then
            awk '
                /^### Auto-invoke Skills/ {
                    while ((getline line < "'"$section_file"'") > 0) print line
                    close("'"$section_file"'")
                    skip = 1; next
                }
                skip && /^(---|## )/ { skip = 0; print "" }
                !skip { print }
            ' "$agents_path" > "$agents_path.tmp"
            mv "$agents_path.tmp" "$agents_path"
            echo -e "${GREEN}  ✓ Updated Auto-invoke section${NC}"
        else
            awk '
                /^>.*SKILL\.md\)$/ && !inserted {
                    print; getline
                    if (/^$/) {
                        print ""
                        while ((getline line < "'"$section_file"'") > 0) print line
                        close("'"$section_file"'")
                        print ""; inserted = 1; next
                    }
                }
                { print }
            ' "$agents_path" > "$agents_path.tmp"
            mv "$agents_path.tmp" "$agents_path"
            echo -e "${GREEN}  ✓ Inserted Auto-invoke section${NC}"
        fi
        rm -f "$section_file"
    fi
done

echo ""
echo -e "${GREEN}Done!${NC}"
echo ""
echo -e "${BLUE}Skills missing sync metadata:${NC}"
missing=0
while IFS= read -r skill_file; do
    [ -f "$skill_file" ] || continue
    skill_name=$(extract_field "$skill_file" "name")
    scope_raw=$(extract_metadata "$skill_file" "scope")
    auto_invoke_raw=$(extract_metadata "$skill_file" "auto_invoke")
    auto_invoke=$(echo "$auto_invoke_raw" | sed 's/|/;;/g')
    if [ -z "$scope_raw" ] || [ -z "$auto_invoke" ]; then
        echo -e "  ${YELLOW}$skill_name${NC} — missing: ${scope_raw:-scope} ${auto_invoke:-auto_invoke}"
        missing=$((missing + 1))
    fi
done < <(find "$SKILLS_DIR" -mindepth 2 -maxdepth 2 -name SKILL.md -print | sort)

[ $missing -eq 0 ] && echo -e "  ${GREEN}All skills have sync metadata${NC}"
