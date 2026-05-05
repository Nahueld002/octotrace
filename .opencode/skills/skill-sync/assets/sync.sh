#!/usr/bin/env bash
# Generic skill sync: syncs skill metadata to AGENTS.md files
# Usage: sync.sh [--dry-run] [--scope <scope>] [--config <file>]
#
# Config file (.skill-sync.yaml or .skill-sync.conf in repo root):
#   skills_dir: ".opencode/skills"  # optional, detects .opencode/skills and skills/
#   scopes:
#     root: "AGENTS.md"
#     providers: "src/providers/AGENTS.md"
#     services: "src/services/AGENTS.md"
#     web: "src/web/AGENTS.md"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Defaults
DRY_RUN=false
FILTER_SCOPE=""
CONFIG_FILE=""
SKILLS_DIRS=""

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --dry-run         Show what would change without updating
  --scope SCOPE    Only process specific scope (root, providers, etc.)
  --config FILE    Use custom config file (default: .skill-sync.yaml/.conf)
  --skills DIR    Additional skills directory (can pass multiple)
  --help, -h      Show this help

Config file format (YAML or shell variables):
  # YAML
  skills_dir: ".opencode/skills"
  scopes:
    root: "AGENTS.md"
    providers: "src/providers/AGENTS.md"

  # Or shell
  SKILLS_DIRS=".opencode/skills"
  SCOPE_ROOT="AGENTS.md"
  SCOPE_PROVIDERS="src/providers/AGENTS.md"

EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --scope) FILTER_SCOPE="$2"; shift 2 ;;
        --config) CONFIG_FILE="$2"; shift 2 ;;
        --skills) SKILLS_DIRS="$SKILLS_DIRS $2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

# Find config file
find_config() {
    local dir="$1"
    for f in ".skill-sync.yaml" ".skill-sync.yml" ".skill-sync.conf"; do
        [ -f "$dir/$f" ] && echo "$dir/$f" && return 0
    done
    echo ""
}

# Load config
load_config() {
    local config="$1"
    local ext="${config##*.}"
    
    if [[ "$ext" == "yaml" || "$ext" == "yml" ]]; then
        # Simple YAML parse (only key: value pairs)
        while IFS= read -r line; do
            [[ "$line" =~ ^[[:space:]]*([a-z_]+):[[:space:]]*(.+)$ ]] || continue
            key="${BASH_REMATCH[1]}"
            val="${BASH_REMATCH[2]}"
            val="${val//[\"']/}"
            case "$key" in
                skills_dir) SKILLS_DIRS="$val" ;;
            esac
        done < "$config"
        
        # Parse scopes section (after "scopes:")
        local in_scopes=false
        while IFS= read -r line; do
            if [[ "$line" =~ ^[[:space:]]*scopes:[[:space:]]*$ ]]; then
                in_scopes=true
                continue
            fi
            $in_scopes || continue
            [[ "$line" =~ ^[[:space:]]+([a-z_]+):[[:space:]]*(.+)$ ]] || continue
            scope="${BASH_REMATCH[1]}"
            path="${BASH_REMATCH[2]}"
            path="${path//[\"']/}"
            eval "SCOPE_${scope^^}=\"$path\""
        done < "$config"
    else
        # Shell variables
        source "$config"
    fi
}

# Try to load config from repo root
CONFIG=$(find_config "$REPO_ROOT")
[ -n "$CONFIG" ] && load_config "$CONFIG"

# Default skills directories if not specified
if [ -z "$SKILLS_DIRS" ]; then
    if [ -d "$REPO_ROOT/.opencode/skills" ]; then
        SKILLS_DIRS="$REPO_ROOT/.opencode/skills"
    fi
    if [ -d "$REPO_ROOT/skills" ]; then
        SKILLS_DIRS="$SKILLS_DIRS $REPO_ROOT/skills"
    fi
    SKILLS_DIRS="${SKILLS_DIRS# }"
fi

# Default scopes if not set
SCOPE_ROOT="${SCOPE_ROOT:-AGENTS.md}"
SCOPE_PROVIDERS="${SCOPE_PROVIDERS:-src/providers/AGENTS.md}"
SCOPE_SERVICES="${SCOPE_SERVICES:-src/services/AGENTS.md}"
SCOPE_WEB="${SCOPE_WEB:-src/web/AGENTS.md}"

get_agents_path() {
    local scope="$1"
    local var="SCOPE_${scope^^}"
    local path="${!var}"
    [ -n "$path" ] && echo "$REPO_ROOT/$path" || echo ""
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

echo -e "${CYAN}Skill Sync — Generic${NC}"
echo "================================"
echo "Repo: $REPO_ROOT"
echo "Skills: $SKILLS_DIRS"
echo ""

SCOPE_TMPDIR=$(mktemp -d)
trap 'rm -rf "$SCOPE_TMPDIR"' EXIT

# Collect skills from all directories
for SKILLS_DIR in $SKILLS_DIRS; do
    [ -d "$SKILLS_DIR" ] || continue
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
    done < <(find "$SKILLS_DIR" -mindepth 2 -maxdepth 2 -name SKILL.md -print 2>/dev/null | sort)
done

# Deduplicate per scope
for f in "$SCOPE_TMPDIR"/*; do
    [ -f "$f" ] || continue
    sort -u "$f" -o "$f"
done

for scope_file in "$SCOPE_TMPDIR"/*; do
    [ -f "$scope_file" ] || continue
    scope=$(basename "$scope_file")
    agents_path=$(get_agents_path "$scope")

    if [ -z "$agents_path" ] || [ ! -f "$agents_path" ]; then
        echo -e "${YELLOW}Warning: No AGENTS.md for scope '$scope' at $agents_path${NC}"
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