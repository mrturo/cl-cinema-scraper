"""
Build wheel files from uv's archive cache for offline installation.
Reads ~/.cache/uv/archive-v0/ and creates .whl files in packages/ directory.
"""
import hashlib
import base64
import zipfile
import os
import sys
from pathlib import Path

ARCHIVE_DIR = Path.home() / ".cache" / "uv" / "archive-v0"
OUTPUT_DIR = Path(__file__).parent.parent / "packages"

# Packages we need (name normalized, as they appear in METADATA)
NEEDED = {
    "annotated-types", "anyio", "beautifulsoup4", "certifi", "click",
    "coverage", "email-validator", "eval-type-backport", "exceptiongroup",
    "fastapi", "h11", "httpcore", "httptools", "httpx", "idna",
    "packaging", "playwright", "pydantic", "pydantic-core", "pydantic-settings",
    "pytest", "pytest-cov", "python-dotenv", "ruff", "setuptools",
    "sniffio", "soupsieve", "starlette", "typing-extensions", "typing-inspection",
    "uvicorn", "uvloop", "watchfiles", "websockets",
}


def normalize(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def sha256_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def get_wheel_tags(dist_info: Path) -> str:
    """Read the WHEEL file and return the tag string."""
    wheel_file = dist_info / "WHEEL"
    if not wheel_file.exists():
        return "py3-none-any"
    python_tag = "py3"
    abi_tag = "none"
    plat_tag = "any"
    for line in wheel_file.read_text().splitlines():
        if line.startswith("Tag:"):
            tag = line[4:].strip()
            parts = tag.split("-")
            if len(parts) == 3:
                python_tag, abi_tag, plat_tag = parts
                break
    return f"{python_tag}-{abi_tag}-{plat_tag}"


def build_wheel(archive_path: Path, output_dir: Path) -> Path | None:
    """Build a .whl from an extracted archive directory."""
    # Find the .dist-info directory
    dist_infos = [p for p in archive_path.iterdir()
                  if p.is_dir() and p.name.endswith(".dist-info")]
    if not dist_infos:
        return None
    dist_info = dist_infos[0]

    # Read name and version from METADATA
    meta = (dist_info / "METADATA")
    if not meta.exists():
        return None
    name = version = None
    for line in meta.read_text(errors="replace").splitlines():
        if line.startswith("Name: "):
            name = line[6:].strip()
        elif line.startswith("Version: "):
            version = line[9:].strip()
        if name and version:
            break
    if not name or not version:
        return None

    tags = get_wheel_tags(dist_info)
    safe_name = name.replace("-", "_")
    wheel_name = f"{safe_name}-{version}-{tags}.whl"
    wheel_path = output_dir / wheel_name

    if wheel_path.exists():
        return wheel_path  # already built

    # Collect all files (excluding RECORD, we'll regenerate it)
    entries: list[tuple[str, bytes, int]] = []
    record_path_str = f"{dist_info.name}/RECORD"

    for fp in sorted(archive_path.rglob("*")):
        if not fp.is_file():
            continue
        if fp.name == "RECORD" and fp.parent.name.endswith(".dist-info"):
            continue  # regenerate
        rel = str(fp.relative_to(archive_path))
        mode = fp.stat().st_mode
        entries.append((rel, fp.read_bytes(), mode))

    # Build RECORD content
    record_lines = []
    for rel, data, _ in entries:
        record_lines.append(f"{rel},{sha256_hash(data)},{len(data)}")
    record_lines.append(f"{record_path_str},,")
    record_bytes = "\n".join(record_lines).encode()

    # Write wheel (preserving Unix file permissions in external_attr)
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, data, mode in entries:
            info = zipfile.ZipInfo(rel)
            info.external_attr = (mode & 0xFFFF) << 16  # preserve Unix perms
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
        zf.writestr(record_path_str, record_bytes)

    print(f"  ✓ {wheel_name}")
    return wheel_path


def main():
    output_dir = OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)

    built = 0
    skipped = 0
    for archive in ARCHIVE_DIR.iterdir():
        if not archive.is_dir():
            continue
        result = build_wheel(archive, output_dir)
        if result:
            built += 1
        else:
            skipped += 1

    print(f"\nBuilt {built} wheels → {output_dir}")
    print(f"Skipped {skipped} (not needed or no dist-info)")


if __name__ == "__main__":
    main()
