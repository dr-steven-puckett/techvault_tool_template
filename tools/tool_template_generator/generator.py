#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import keyword
import re
import shutil
import sys
from pathlib import Path

# Allow importing tool_common (sibling package under tools/)
_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from tool_common.stamp import compute_manifest_sha256, write_stamp  # type: ignore  # noqa: E402


REQUIRED_TEMPLATE_FILES = [
    "STANDARD_REPO_SKELETON.md",
    "TEMPLATE_MANIFEST.json",
    "TOOL_TEMPLATE_SOT.md",
    "TOOL_TEMPLATE_EXECUTION_PLAN.md",
    "TOOL_TEMPLATE_ROADMAP.md",
]

REQUIRED_PROMPTS = [
    "00_scaffold_repo.md",
    "01_contracts_and_determinism.md",
    "02_catalog_loader.md",
    "03_service_layer_ordering.md",
    "04_api_interface.md",
    "05_openapi_snapshot.md",
    "06_determinism_and_hash_tests.md",
    "07_final_gate.md",
    "08_cli_interface.md",
    "09_release_readiness.md",
    "10_sot_invariant_check.md",
    "README.md",
]


def validate_tool_id(tool_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tool_id):
        raise ValueError(
            "Invalid tool_id. Must be a valid Python package name using letters, numbers, and underscores, "
            "and must not start with a number."
        )
    if keyword.iskeyword(tool_id):
        raise ValueError(f"Invalid tool_id '{tool_id}': Python keyword is not allowed.")


def verify_template_source(template_root: Path) -> None:
    if not template_root.is_dir():
        raise FileNotFoundError(f"Template directory not found: {template_root}")

    for file_name in REQUIRED_TEMPLATE_FILES:
        file_path = template_root / file_name
        if not file_path.is_file():
            raise FileNotFoundError(f"Missing template file: {file_path}")

    prompts_dir = template_root / "prompts"
    if not prompts_dir.is_dir():
        raise FileNotFoundError(f"Missing template prompts directory: {prompts_dir}")

    for prompt_name in REQUIRED_PROMPTS:
        prompt_path = prompts_dir / prompt_name
        if not prompt_path.is_file():
            raise FileNotFoundError(f"Missing template prompt: {prompt_path}")


def render_tool_toml(tool_id: str) -> str:
    return (
        f'tool_id = "{tool_id}"\n'
        f'name = "{tool_id}"\n'
        'version = "0.1.0"\n'
        f'entrypoint = "{tool_id}.api.router:router"\n'
        'enabled_by_default = false\n\n'
        '[api]\n'
        'mount_prefix = ""\n'
        f'tags = ["tools:{tool_id}"]\n\n'
        '[capabilities]\n'
        'actions = ["search"]\n'
    )


def render_readme(tool_id: str) -> str:
    return f"""# {tool_id}

## Tool Overview

Deterministic TechVault tool scaffold generated from the standard template.

## API Usage

Router entrypoint:

- `{tool_id}.api.router:router`

## CLI Usage

Run CLI commands using module invocation:

- `python -m {tool_id}.cli <command>`

## Standalone Mode (--catalog-file)

Example:

- `python -m {tool_id}.cli search --catalog-file catalog.json`

## Determinism Guarantees

- explicit sorting
- stable pagination
- canonical JSON serialization
- byte-identical outputs for identical inputs
- input-order independence

## Testing

Run tests with:

- `pytest -q`
"""


def transform_template_doc(content: str, tool_id: str) -> str:
    replacements = {
        "tool_id_here": tool_id,
        "<tool_id>": tool_id,
        "<tool_package>": tool_id,
        "TOOL_<NAME>": f"TOOL_{tool_id.upper()}",
        "tools:<tool_id>": f"tools:{tool_id}",
    }

    for old, new in replacements.items():
        content = content.replace(old, new)
    return content


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_placeholder_modules(target_root: Path, tool_id: str) -> None:
    pkg_root = target_root / tool_id

    write_file(pkg_root / "__init__.py", '"""Tool package root."""\n')
    write_file(pkg_root / "api" / "__init__.py", '"""API package."""\n')
    write_file(pkg_root / "api" / "router.py", '"""API router placeholder."""\n')
    write_file(pkg_root / "api" / "schemas.py", '"""API schemas placeholder."""\n')
    write_file(pkg_root / "api" / "deps.py", '"""API dependency placeholders."""\n')
    write_file(pkg_root / "api" / "openapi_snapshot.py", '"""OpenAPI snapshot placeholder."""\n')

    write_file(pkg_root / "core" / "__init__.py", '"""Core package."""\n')
    write_file(pkg_root / "core" / "service.py", '"""Service layer placeholder."""\n')
    write_file(pkg_root / "core" / "determinism.py", '"""Determinism helpers placeholder."""\n')
    write_file(pkg_root / "core" / "catalog_loader.py", '"""Catalog loader placeholder."""\n')

    write_file(pkg_root / "cli" / "__init__.py", '"""CLI package."""\n')
    write_file(pkg_root / "cli" / "main.py", '"""CLI entrypoint placeholder."""\n')


def create_placeholder_tests(target_root: Path) -> None:
    tests_dir = target_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    test_stub = "def test_placeholder():\n    assert True\n"
    for test_name in (
        "test_contract_schemas.py",
        "test_ordering_pagination.py",
        "test_determinism_json.py",
        "test_cli_smoke.py",
        "test_api_smoke.py",
        "test_openapi_snapshot.py",
    ):
        write_file(tests_dir / test_name, test_stub)


def copy_prompt_pack(template_root: Path, target_root: Path) -> None:
    src_prompts = template_root / "prompts"
    dst_prompts = target_root / "docs" / "prompts"
    dst_prompts.mkdir(parents=True, exist_ok=True)

    for prompt_name in REQUIRED_PROMPTS:
        shutil.copy2(src_prompts / prompt_name, dst_prompts / prompt_name)


def copy_template_docs(template_root: Path, target_root: Path, tool_id: str) -> None:
    docs_dir = target_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    mappings = {
        "TOOL_TEMPLATE_SOT.md": f"TOOL_{tool_id.upper()}_SOT.md",
        "TOOL_TEMPLATE_EXECUTION_PLAN.md": f"TOOL_{tool_id.upper()}_EXECUTION_PLAN.md",
        "TOOL_TEMPLATE_ROADMAP.md": f"TOOL_{tool_id.upper()}_ROADMAP.md",
    }

    for src_name, dst_name in mappings.items():
        source = template_root / src_name
        content = source.read_text(encoding="utf-8")
        write_file(docs_dir / dst_name, transform_template_doc(content, tool_id))


def create_scaffold(base_tools_dir: Path, template_root: Path, tool_id: str) -> Path:
    target_root = base_tools_dir / tool_id

    if target_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing directory: {target_root}")

    target_root.mkdir(parents=True, exist_ok=False)

    write_file(target_root / "tool.toml", render_tool_toml(tool_id))

    # Stamp the new tool.toml with the current template version and manifest hash
    manifest_path = template_root / "TEMPLATE_MANIFEST.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    template_version = manifest_data.get("template_version", "unknown")
    manifest_hash = compute_manifest_sha256(manifest_path)
    write_stamp(
        target_root / "tool.toml",
        template_version=template_version,
        template_manifest_hash=manifest_hash,
        stamp_source="create",
    )

    write_file(target_root / "README.md", render_readme(tool_id))
    write_file(target_root / "openapi.snapshot.json", "{}\n")

    # Copy the manifest into the tool repo root so template-check can use it
    # without requiring access to the tv_tool_template workspace.
    shutil.copy2(manifest_path, target_root / "TEMPLATE_MANIFEST.json")

    copy_template_docs(template_root, target_root, tool_id)
    copy_prompt_pack(template_root, target_root)
    create_placeholder_modules(target_root, tool_id)
    create_placeholder_tests(target_root)

    return target_root


def render_tree(root: Path) -> list[str]:
    lines = [f"{root.name}/"]

    for path in sorted(root.rglob("*"), key=lambda item: (len(item.relative_to(root).parts), str(item.relative_to(root)))):
        rel = path.relative_to(root)
        indent = "  " * (len(rel.parts) - 1)
        suffix = "/" if path.is_dir() else ""
        lines.append(f"{indent}{rel.name}{suffix}")

    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="techvault-tool-create",
        description="Generate a deterministic TechVault tool repository scaffold.",
    )
    parser.add_argument("tool_id", help="Tool identifier and package name (e.g., library_catalog_search)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        this_file = Path(__file__).resolve()
        generator_root = this_file.parent
        project_root = generator_root.parent.parent
        base_tools_dir = project_root / "tools"
        template_root = project_root / "tools" / "tool_template"

        validate_tool_id(args.tool_id)
        verify_template_source(template_root)

        print(f"Creating tool repository: {args.tool_id}")
        target_root = create_scaffold(base_tools_dir, template_root, args.tool_id)

        print("\nScaffold complete.\n")
        print("Created directory tree:")
        for line in render_tree(target_root):
            print(line)

        print("\nNext steps:\n")
        print(f"cd tools/{args.tool_id}")
        print("run prompt pipeline starting with:")
        print("docs/prompts/10_sot_invariant_check.md")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
