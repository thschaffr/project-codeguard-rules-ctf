# Copyright 2025 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""
Convert Unified Rules to IDE Formats

Transforms the unified markdown sources into IDE-specific bundles (Cursor,
Windsurf, Copilot, Claude Code). This script is the main entry point for producing
distributable rule packs from the sources/ directory.
"""

import os
import re
import shutil
from pathlib import Path
from collections import defaultdict

from converter import RuleConverter
from formats import CursorFormat, WindsurfFormat, CopilotFormat, ClaudeCodeFormat
from utils import get_version_from_pyproject
from validate_versions import set_plugin_version, set_marketplace_version

# Project root is always one level up from src/
PROJECT_ROOT = Path(__file__).parent.parent


def sync_plugin_metadata(version: str) -> None:
    """
    Sync version from pyproject.toml to Claude Code plugin metadata files.

    Args:
        version: Version string from pyproject.toml
    """
    set_plugin_version(version, PROJECT_ROOT)
    set_marketplace_version(version, PROJECT_ROOT)
    print(f"✅ Synced plugin metadata to {version}")


def get_claude_plugin_cache_path() -> Path | None:
    """
    Find the Claude Code plugin cache directory for codeguard-security.
    
    Returns:
        Path to the plugin cache directory, or None if not found
    """
    home = Path.home()
    
    # Standard location: ~/.claude/plugins/cache/project-codeguard/codeguard-security/
    cache_base = home / ".claude" / "plugins" / "cache" / "project-codeguard" / "codeguard-security"
    
    if not cache_base.exists():
        return None
    
    # Find the latest version directory
    version_dirs = [d for d in cache_base.iterdir() if d.is_dir()]
    if not version_dirs:
        return None
    
    # Sort by version (assuming semantic versioning) and get latest
    latest_version = sorted(version_dirs, key=lambda x: x.name, reverse=True)[0]
    
    return latest_version


def update_plugin_cache(skills_source: Path, cache_path: Path) -> tuple[bool, bool]:
    """
    Update the Claude Code plugin cache with generated rules.
    
    Args:
        skills_source: Path to the generated skills/ directory
        cache_path: Path to the plugin cache version directory
    
    Returns:
        Tuple of (success: bool, new_rule_detected: bool)
    """
    cache_skills = cache_path / "skills" / "software-security"
    
    if not cache_skills.exists():
        print(f"⚠️  Cache skills directory not found: {cache_skills}")
        return False, False
    
    new_rule_detected = False
    
    # Copy SKILL.md
    skill_md_src = skills_source / "SKILL.md"
    skill_md_dst = cache_skills / "SKILL.md"
    if skill_md_src.exists():
        shutil.copy2(skill_md_src, skill_md_dst)
    
    # Copy all rule files and detect new ones
    rules_src = skills_source / "rules"
    rules_dst = cache_skills / "rules"
    
    if rules_src.exists() and rules_dst.exists():
        # Get existing rules in cache before update
        existing_rules = {f.name for f in rules_dst.glob("*.md")}
        
        # Get new rules from source
        source_rules = {f.name for f in rules_src.glob("*.md")}
        
        # Detect new rules (in source but not in cache)
        new_rules = source_rules - existing_rules
        if new_rules:
            new_rule_detected = True
            print(f"🆕 New rule(s) detected: {', '.join(sorted(new_rules))}")
        
        # Clear existing rules in cache
        for f in rules_dst.glob("*.md"):
            f.unlink()
        
        # Copy new rules
        for rule_file in rules_src.glob("*.md"):
            shutil.copy2(rule_file, rules_dst / rule_file.name)
    
    return True, new_rule_detected


def matches_tag_filter(rule_tags: list[str], filter_tags: list[str]) -> bool:
    """
    Check if rule has all required tags (AND logic).
    
    Args:
        rule_tags: List of tags from the rule (already normalized to lowercase)
        filter_tags: List of tags to filter by (already normalized to lowercase)
    
    Returns:
        True if rule has all filter tags (or no filter), False otherwise
    """
    if not filter_tags:
        return True  # No filter means all pass
    
    return all(tag in rule_tags for tag in filter_tags)


def update_skill_md(language_to_rules: dict[str, list[str]], skill_path: str) -> None:
    """
    Update SKILL.md with language-to-rules mapping table including file extensions.

    Args:
        language_to_rules: Dictionary mapping languages to rule files
        skill_path: Path to SKILL.md file
    """
    from language_mappings import LANGUAGE_TO_EXTENSIONS

    # Generate markdown table with Extensions column
    table_lines = [
        "| Language | File Extensions | Rule Files to Apply |",
        "|----------|-----------------|---------------------|",
    ]

    for language in sorted(language_to_rules.keys()):
        rules = sorted(language_to_rules[language])
        rules_str = ", ".join(rules)
        
        # Get extensions for this language
        extensions = LANGUAGE_TO_EXTENSIONS.get(language, [])
        # Escape asterisks for markdown table
        ext_str = ", ".join(extensions).replace("*", "\\*") if extensions else "N/A"
        
        table_lines.append(f"| {language} | {ext_str} | {rules_str} |")

    table = "\n".join(table_lines)

    # Markers for the language mappings section
    start_marker = "<!-- LANGUAGE_MAPPINGS_START -->"
    end_marker = "<!-- LANGUAGE_MAPPINGS_END -->"

    # Read SKILL.md
    skill_file = Path(skill_path)
    content = skill_file.read_text(encoding="utf-8")

    if start_marker not in content or end_marker not in content:
        raise RuntimeError(
            "Invalid template: Language mappings section not found in codeguard-SKILLS.md.template"
        )

    # Replace entire section including markers with just the table
    start_idx = content.index(start_marker)
    end_idx = content.index(end_marker) + len(end_marker)
    new_section = f"\n\n{table}\n\n"
    updated_content = content[:start_idx] + new_section + content[end_idx:]

    # Write back to SKILL.md
    skill_file.write_text(updated_content, encoding="utf-8")
    print(f"Updated SKILL.md with language mappings and extensions")


def convert_rules(input_path: str, output_dir: str = "dist", include_claudecode: bool = True, version: str = None, filter_tags: list[str] = None) -> dict[str, list[str]]:
    """
    Convert rule file(s) to all supported IDE formats using RuleConverter.

    Args:
        input_path: Path to a single .md file or folder containing .md files
        output_dir: Output directory (default: 'dist/')
        include_claudecode: Whether to generate Claude Code plugin (default: True, only for core rules)
        version: Version string to use (default: read from pyproject.toml)
        filter_tags: Optional list of tags to filter by (AND logic, case-insensitive)

    Returns:
        Dictionary with 'success' and 'errors' lists:
        {
            "success": ["rule1.md", "rule2.md"],
            "errors": ["rule3.md: error message"]
        }

    Example:
        results = convert_rules("sources/core", "dist", include_claudecode=True)
        print(f"Converted {len(results['success'])} rules")
    """
    if version is None:
        version = get_version_from_pyproject()

    # Specify formats to generate
    all_formats = [
        CursorFormat(version),
        WindsurfFormat(version),
        CopilotFormat(version),
    ]
    
    # Only include Claude Code for core rules (committed plugin)
    if include_claudecode:
        all_formats.append(ClaudeCodeFormat(version))

    converter = RuleConverter(formats=all_formats)
    path = Path(input_path)

    if not path.exists():
        raise FileNotFoundError(f"{input_path} does not exist")

    # Determine files to process
    if path.is_file():
        if path.suffix != ".md":
            raise ValueError(f"{input_path} is not a .md file")
        md_files = [path]
    else:
        # Use rglob to recursively find all .md files in subdirectories
        md_files = sorted(list(path.rglob("*.md")))
        if not md_files:
            raise ValueError(f"No .md files found in {input_path}")
    
    print(f"Converting {len(md_files)} files from: {path}")

    # Setup output directory
    output_base = Path(output_dir)

    results = {"success": [], "errors": [], "skipped": []}
    language_to_rules = defaultdict(list)

    # Process each file
    for md_file in md_files:
        try:
            # Convert the file (raises exceptions on error)
            result = converter.convert(md_file)
            
            # Apply tag filter if specified
            if filter_tags and not matches_tag_filter(result.tags, filter_tags):
                results["skipped"].append(result.filename)
                continue

            # Write each format
            output_files = []
            for format_name, output in result.outputs.items():
                # Construct output path
                # Claude Code goes to project root ./skills/
                # Other formats go to dist/ (or specified output_dir)
                if format_name == "claudecode":
                    base_dir = PROJECT_ROOT
                else:
                    base_dir = output_base
                
                output_file = (
                    base_dir
                    / output.subpath
                    / f"{result.basename}{output.extension}"
                )

                # Create directory if it doesn't exist and write file
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(output.content, encoding="utf-8")
                output_files.append(output_file.name)

            print(f"Success: {result.filename} → {', '.join(output_files)}")
            results["success"].append(result.filename)

            # Update language mappings for SKILL.md
            for language in result.languages:
                language_to_rules[language].append(result.filename)

        except FileNotFoundError as e:
            error_msg = f"{md_file.name}: File not found - {e}"
            print(f"Error: {error_msg}")
            results["errors"].append(error_msg)

        except ValueError as e:
            error_msg = f"{md_file.name}: Validation error - {e}"
            print(f"Error: {error_msg}")
            results["errors"].append(error_msg)

        except Exception as e:
            error_msg = f"{md_file.name}: Unexpected error - {e}"
            print(f"Error: {error_msg}")
            results["errors"].append(error_msg)

    # Summary
    if filter_tags:
        print(
            f"\nResults: {len(results['success'])} success, {len(results['skipped'])} skipped (tag filter), {len(results['errors'])} errors"
        )
    else:
        print(
            f"\nResults: {len(results['success'])} success, {len(results['errors'])} errors"
        )

    # Generate SKILL.md with language mappings (only if Claude Code is included)
    if include_claudecode and language_to_rules:
        template_path = PROJECT_ROOT / "sources" / "core" / "codeguard-SKILLS.md.template"
        
        if not template_path.exists():
            raise FileNotFoundError(
                f"SKILL.md template not found at {template_path}. "
                "This file is required for Claude Code plugin generation."
            )
        
        output_skill_dir = PROJECT_ROOT / "skills" / "software-security"
        output_skill_dir.mkdir(parents=True, exist_ok=True)
        output_skill_path = output_skill_dir / "SKILL.md"
        
        # Read template and inject current version from pyproject.toml
        template_content = template_path.read_text(encoding="utf-8")
        # Replace the hardcoded version with actual version
        template_content = re.sub(
            r'codeguard-version:\s*"[^"]*"',
            f'codeguard-version: "{version}"',
            template_content
        )
        output_skill_path.write_text(template_content, encoding="utf-8")
        
        update_skill_md(language_to_rules, str(output_skill_path))

    return results


def _resolve_source_paths(args) -> list[Path]:
    """
    Resolve source paths from CLI arguments.
    Priority: --source flags > default (core)
    """
    # If --source flags provided, resolve under sources/
    if args.source:
        return [Path("sources") / src for src in args.source]
    
    # Default: core rules only
    return [Path("sources/core")]


if __name__ == "__main__":
    import sys
    from argparse import ArgumentParser
    
    parser = ArgumentParser(
        description="Convert unified rule markdown into IDE-specific bundles."
    )
    parser.add_argument(
        "--source",
        nargs="+",
        help="Named sources under ./sources to convert (e.g., --source core owasp). Default: core",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="dist",
        help="Output directory for generated bundles (default: dist).",
    )
    parser.add_argument(
        "--tag",
        "--tags",
        dest="tags",
        help="Filter rules by tags (comma-separated, case-insensitive, AND logic). Example: --tag api,web-security",
    )
    parser.add_argument(
        "--update-cache",
        action="store_true",
        help="Also update the Claude Code plugin cache (~/.claude/plugins/cache/...)",
    )
    
    cli_args = parser.parse_args()
    source_paths = _resolve_source_paths(cli_args)

    # Validate all source paths exist
    missing = [p for p in source_paths if not p.exists()]
    if missing:
        print(f"❌ Source path(s) not found: {', '.join(str(p) for p in missing)}")
        sys.exit(1)

    # Check for duplicate filenames across sources if multiple sources
    if len(source_paths) > 1:
        filename_to_sources = defaultdict(list)
        for source_path in source_paths:
            for md_file in source_path.rglob("*.md"):
                filename_to_sources[md_file.name].append(source_path.name)
        
        duplicates = {name: srcs for name, srcs in filename_to_sources.items() if len(srcs) > 1}
        if duplicates:
            print(f"❌ Found {len(duplicates)} duplicate filename(s) across sources:")
            for filename, sources in duplicates.items():
                print(f"   - {filename} in: {', '.join(sources)}")
            print("\nPlease rename files to have unique names across all sources.")
            sys.exit(1)
    
    # Get version once and sync to metadata files
    version = get_version_from_pyproject()
    sync_plugin_metadata(version)

    # Check if core is in the sources for Claude Code plugin generation
    has_core = Path("sources/core") in source_paths
    if has_core:
        # Validate template exists early
        template_path = PROJECT_ROOT / "sources" / "core" / "codeguard-SKILLS.md.template"
        if not template_path.exists():
            print(f"❌ SKILL.md template not found at {template_path}")
            print("This file is required for Claude Code plugin generation.")
            sys.exit(1)

    # Clean output directories once before processing
    output_path = Path(cli_args.output_dir)
    if output_path.exists():
        shutil.rmtree(output_path)
        print(f"✅ Cleaned {cli_args.output_dir}/ directory")

    if has_core:
        skills_rules_dir = PROJECT_ROOT / "skills" / "software-security" / "rules"
        if skills_rules_dir.exists():
            shutil.rmtree(skills_rules_dir)
            print(f"✅ Cleaned skills/ directory")
    
    # Print processing summary
    if len(source_paths) > 1:
        sources_list = ', '.join(p.name for p in source_paths)
        print(f"\nConverting {len(source_paths)} sources: {sources_list}")
        if has_core:
            print("(Claude Code plugin will include only core rules)")
        print()
    
    # Convert all sources
    aggregated = {"success": [], "errors": [], "skipped": []}
    # Parse comma-separated tags and normalize to lowercase
    filter_tags = None
    if cli_args.tags:
        filter_tags = [tag.strip().lower() for tag in cli_args.tags.split(",") if tag.strip()]
    
    # Print tag filter info if active
    if filter_tags:
        print(f"Tag filter active: {', '.join(filter_tags)} (AND logic - rules must have all tags)\n")
    
    for source_path in source_paths:
        is_core = source_path == Path("sources/core")
        
        print(f"Processing: {source_path}")
        results = convert_rules(
            str(source_path), 
            cli_args.output_dir, 
            include_claudecode=is_core,
            version=version,
            filter_tags=filter_tags
        )
        
        aggregated["success"].extend(results["success"])
        aggregated["errors"].extend(results["errors"])
        if "skipped" in results:
            aggregated["skipped"].extend(results["skipped"])
        print("")
    
    if aggregated["errors"]:
        print("❌ Some conversions failed")
        sys.exit(1)
    
    # Update Claude Code plugin cache if requested
    if cli_args.update_cache and has_core:
        cache_path = get_claude_plugin_cache_path()
        if cache_path:
            print(f"Updating Claude Code plugin cache: {cache_path}")
            skills_dir = PROJECT_ROOT / "skills" / "software-security"
            success, new_rule_detected = update_plugin_cache(skills_dir, cache_path)
            
            if success:
                print(f"✅ Updated plugin cache at {cache_path}")
                
                # CTF Flag: Reward for creating a new custom rule
                if new_rule_detected:
                    print("\n" + "="*60)
                    print("🚩 FLAG{no_limits_pure_control}")
                    print("="*60)
                    print("Congratulations! You've successfully created a custom")
                    print("security rule and deployed it to your AI coding agent.")
                    print("="*60 + "\n")
            else:
                print(f"⚠️  Failed to update plugin cache")
        else:
            print("⚠️  Claude Code plugin cache not found (plugin may not be installed)")
    
    print("✅ All conversions successful")
