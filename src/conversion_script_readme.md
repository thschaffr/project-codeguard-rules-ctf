# Documentation: Claude Code Plugin Cache Update Feature

## Overview

This update adds the ability to synchronize locally generated security rules with the Claude Code plugin cache. It also includes a CTF (Capture The Flag) challenge feature that rewards players when they successfully create and deploy a new custom security rule.

---

## New Features

### 1. Plugin Cache Discovery (`get_claude_plugin_cache_path`)

**Purpose**: Automatically locates the Claude Code plugin cache directory on the user's system.

**Behavior**:
- Searches for the cache at `~/.claude/plugins/cache/project-codeguard/codeguard-security/`
- Supports both Linux (`/home/user/`) and macOS (`/Users/user/`) home directories
- Automatically finds the latest installed plugin version
- Returns `None` if the plugin is not installed

**Why This Matters**: Claude Code caches installed plugins locally. This function allows the script to find and update the cached rules without requiring manual path configuration.

---

### 2. Cache Update with New Rule Detection (`update_plugin_cache`)

**Purpose**: Copies generated rules from `skills/` to the Claude Code plugin cache and detects when new rules have been added.

**Behavior**:
1. Compares existing rules in the cache against newly generated rules
2. Identifies rules that exist in `skills/` but not in the cache (new rules)
3. Clears the old cached rules
4. Copies all current rules to the cache
5. Returns a tuple: `(success: bool, new_rule_detected: bool)`

**What Gets Updated**:
- `skills/software-security/SKILL.md` → Cache's `SKILL.md`
- `skills/software-security/rules/*.md` → Cache's `rules/*.md`

---

### 3. New CLI Argument: `--update-cache`

**Usage**:
```bash
python src/convert_to_ide_formats.py --update-cache
```

**Behavior**:
- When specified, the script will also update the local Claude Code plugin cache after generating rules
- Only works when `core` rules are being processed (since Claude Code plugin only uses core rules)
- If the plugin cache is not found, displays a warning but continues successfully

**Default**: Disabled (cache is not updated unless explicitly requested)

---

### 4. CTF Flag: New Rule Detection Reward

**Purpose**: Provides a CTF challenge reward when a player successfully creates and deploys a custom security rule.

**Trigger Conditions** (all must be true):
1. `--update-cache` flag is used
2. Core rules are being processed
3. A new rule file is detected (exists in `skills/rules/` but not in the cache)

**Output When Triggered**:
```
🆕 New rule(s) detected: my-custom-rule.md
✅ Updated plugin cache at /home/user/.claude/plugins/cache/...

============================================================
🚩 FLAG{no_limits_pure_control}
============================================================
Congratulations! You've successfully created a custom
security rule and deployed it to your AI coding agent.
============================================================
```

---

## Usage Examples

### Standard Conversion (No Cache Update)
```bash
python src/convert_to_ide_formats.py
```
Generates IDE-specific rule bundles without touching the Claude Code cache.

### Conversion with Cache Update
```bash
python src/convert_to_ide_formats.py --update-cache
```
Generates rules AND updates the local Claude Code plugin cache.

### CTF Challenge Workflow
1. Player creates a new rule file in `sources/core/`:
   ```bash
   touch sources/core/codeguard-0-my-custom-rule.md
   ```

2. Player adds valid rule content with frontmatter:
   ```markdown
   ---
   description: My Custom Security Rule
   languages: []
   alwaysApply: true
   tags:
   - web
   ---
   
   # My Custom Security Rule
   
   When reviewing code, check for...
   ```

3. Player runs the conversion with cache update:
   ```bash
   python src/convert_to_ide_formats.py --update-cache
   ```

4. Flag is revealed when new rule is detected in the cache update.

---

## File Changes Summary

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `import os` | Added | New import for OS-level operations |
| `get_claude_plugin_cache_path()` | New function | Discovers the Claude Code plugin cache location |
| `update_plugin_cache()` | New function | Syncs rules to cache with new rule detection |
| `--update-cache` argument | New CLI option | Enables cache update functionality |
| Main block cache logic | New section | Handles cache update and CTF flag output |

---

## Security Considerations

- **No Credentials Stored**: The cache path is derived from the user's home directory; no hardcoded paths
- **Safe Default**: Cache update is opt-in (`--update-cache` must be explicitly specified)
- **Non-Destructive**: If cache is not found, the script warns but does not fail
- **Validation**: Rules are validated before being copied to ensure only valid rules are deployed

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Plugin not installed | Warning: "Claude Code plugin cache not found" |
| Cache skills directory missing | Warning: "Cache skills directory not found" |
| Core rules not in source | Cache update is skipped (only works with core rules) |
| Rule validation fails | Rule is not copied; error is reported |

---

## Dependencies

No new external dependencies. Uses only Python standard library:
- `pathlib.Path` - File path operations
- `shutil` - File copying operations (already imported)
