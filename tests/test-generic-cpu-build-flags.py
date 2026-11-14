#!/usr/bin/env python3
"""Reject compiler flags that require newer x86-64 ISA levels."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCOPES = ("tools", "iso", "packaging", "desktop/plugins", "desktop/vendor", "sources.json")
SUFFIXES = {".sh", ".py", ".in", ".mk", ".toml", ".json", ".conf", ".yaml", ".yml", ".cmake"}
RECIPE_NAMES = {"Makefile", "PKGBUILD", "CMakeLists.txt"}
FORBIDDEN = re.compile(
    r"(?<![\w-])(?:-march\s*=\s*(?:native|x86-64-v[234])|"
    r"-mtune\s*=\s*native|target-cpu\s*=\s*native|"
    r"-m(?:avx(?:\w*)?|sse4(?:\.\d)?|sse4[._]?[12]))\b",
    re.IGNORECASE,
)
# These occurrences are data used to remove upstream flags, or assertions
# that reject them; neither passes the flag to a compiler.
SAFE_MATCHES = {
    "tools/build-image-boot-language.sh": "s/-march=native/-march=x86-64 -mtune=generic/g",
    "tools/build-image-connectivity.sh": "s/-march=native/-march=x86-64 -mtune=generic/g",
    "tools/build-image-device-manager.sh": "s/-march=native/-march=x86-64 -mtune=generic/g",
    "tools/build-image-packages.sh": "s/-march=native/-march=x86-64 -mtune=generic/g",
    "tools/check-packages.py": "'-march=native' not in flags",
}


class GenericCpuFlags(unittest.TestCase):
    def test_build_recipes_have_no_non_generic_cpu_flags(self):
        findings = []
        for scope in SCOPES:
            for path in (ROOT / scope).rglob("*"):
                if not path.is_file() or (path.suffix not in SUFFIXES and path.name not in RECIPE_NAMES):
                    continue
                if any(part in {".git", "__pycache__"} for part in path.parts):
                    continue
                for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                    source = line.split("#", 1)[0]
                    relative = path.relative_to(ROOT).as_posix()
                    if FORBIDDEN.search(source) and SAFE_MATCHES.get(relative) not in source:
                        findings.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
        self.assertEqual(findings, [], "Non-generic CPU flags found:\n" + "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
