from __future__ import annotations

import argparse
import re
from pathlib import Path


SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
SKIP_FILES = {Path("scripts/security_scan.py"), Path("tests/test_security_scan.py")}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "generic_api_key": re.compile(r"(?:sk|key|token)-[A-Za-z0-9_-]{20,}"),
    "non_example_email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?![A-Za-z0-9.-]*\.example\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
}
FORBIDDEN_TERMS = {
    "client_dnc": "production-only client control",
    "buyer_reference.json": "production buyer database",
    "outreach_token_auth": "production credential surface",
    "attio_api_key": "production credential surface",
}


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.relative_to(root) in SKIP_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"binary file not allowed: {path.relative_to(root)}")
            continue
        relative = path.relative_to(root)
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{relative}: matched {name}")
        lowered = text.casefold()
        for term, reason in FORBIDDEN_TERMS.items():
            if term in lowered:
                findings.append(f"{relative}: contains {reason} term {term!r}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan the demo for production data markers.")
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    findings = scan(args.root.resolve())
    if findings:
        print("security scan failed")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("security scan passed: no credential or production-data markers found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
