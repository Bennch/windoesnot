#!/usr/bin/env python3
"""Validate local release inputs and prepare files without publishing anything."""

import argparse
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://7a6c4099b8258fbf6e1938332649c529.r2.cloudflarestorage.com"
BASE_URL = "https://download.windoesnot.me"
ISO_NAME = re.compile(r"windoesnot-(\d{4}\.\d{2}\.\d{2})-(en|de)-x86_64\.iso")


def fail(message):
    raise SystemExit(message)


def digest(path, algorithm):
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def checksum_text(value, name):
    return f"{value}  {name}\n"


def check_iso(path, language):
    match = ISO_NAME.fullmatch(path.name)
    if not match or match.group(2) != language:
        fail(f"Wrong {language} ISO name: {path.name}")
    if not path.is_file() or not path.stat().st_size:
        fail(f"Missing or empty ISO: {path}")
    checksum = Path(str(path) + ".sha256")
    if not checksum.is_file():
        fail(f"Missing checksum: {checksum}")
    expected = checksum.read_text().strip().split()
    if len(expected) != 2 or expected[1].lstrip("*") != path.name or not re.fullmatch(r"[0-9a-fA-F]{64}", expected[0]):
        fail(f"Invalid checksum file: {checksum}")
    actual = digest(path, "sha256")
    if actual != expected[0].lower():
        fail(f"SHA256 mismatch: {path}")
    return {"source": path, "build_date": match.group(1), "bytes": path.stat().st_size, "sha256": actual}


def replace_once(text, pattern, replacement):
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        fail(f"README template does not contain expected field: {pattern}")
    return updated


def make_readme(template, old_version, version, release_date, commit, iso, dot):
    text = template.replace(old_version, version)
    text = replace_once(text, r"^Release date: .*?\. Desktop source: [0-9a-fA-F]+\.$",
                        f"Release date: {release_date.day} {release_date.strftime('%B %Y')}. Desktop source: {commit}.")
    # The previous release retained a legacy ISO for old links. Do not carry it forward.
    text = re.sub(r"^- `windoesnot-\d{4}\.\d{2}\.\d{2}-x86_64\.iso`:.*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"^ISO SHA256 \(first German-only ISO\):.*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"^ISO SHA256 \(first .* ISO\):.*\n", "", text, flags=re.MULTILINE)
    for lang in ("en", "de"):
        text = re.sub(rf"windoesnot-\d{{4}}\.\d{{2}}\.\d{{2}}-{lang}-x86_64\.iso",
                      iso[lang]["name"], text)
    text = re.sub(r"windoesnot-dotfiles-[0-9]+(?:\.[0-9]+)+-[0-9]+\.tar\.gz", dot["name"], text)
    text = replace_once(text, r"^ISO size: .*\.$",
                        f"ISO size: {iso['en']['bytes']} bytes (English), {iso['de']['bytes']} bytes (German).")
    text = re.sub(r"^Dotfiles size:.*\n", "", text, flags=re.MULTILINE)
    size_line = f"Dotfiles size: {dot['bytes']} bytes.\n"
    text = text.replace("ISO SHA256 (English):", size_line + "ISO SHA256 (English):", 1)
    for lang, label in (("en", "English"), ("de", "German")):
        text = replace_once(text, rf"^ISO SHA256 \({label}\):.*\.$",
                            f"ISO SHA256 ({label}): `{iso[lang]['sha256']}`.")
    text = replace_once(text, r"^Dotfiles SHA256:.*\.$", f"Dotfiles SHA256: `{dot['sha256']}`.")
    start = text.find("## What is verified\n")
    end = text.find("\nProject code is ", start)
    if start < 0 or end < 0:
        fail("README template lacks the verification section or license footer")
    text = text[:start] + "## What is verified\n\nTODO: Benni must record the tests and untested paths for this release.\n" + text[end:]
    return text


def metadata(name, info, version):
    url = f"{BASE_URL}/{version}/{name}"
    return {"url": url, "sha256": info["sha256"], "bytes": info["bytes"],
            "sha256_url": url + ".sha256", "md5_url": url + ".md5"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--iso-en", required=True, type=Path)
    parser.add_argument("--iso-de", required=True, type=Path)
    parser.add_argument("--date", default=date.today().strftime("%Y.%m.%d"))
    parser.add_argument("--desktop-commit")
    parser.add_argument("--apply", action="store_true", help="write local release files")
    args = parser.parse_args()
    match = re.fullmatch(r"(\d+(?:\.\d+)+)-(\d+)", args.version)
    if not match or int(match.group(2)) < 2:
        parser.error("Use a version with a positive release number above 1")
    try:
        release_date = datetime.strptime(args.date, "%Y.%m.%d").date()
    except ValueError:
        parser.error("Date must be YYYY.MM.DD")
    old_version = f"{match.group(1)}-{int(match.group(2)) - 1}"
    previous = ROOT / "out" / f"release-{old_version}"
    output = ROOT / "out" / f"release-{args.version}"
    if output.exists():
        fail(f"Release directory already exists: {output}")
    template_path = previous / "README.md"
    license_path = previous / "LICENSE-NOTES.txt"
    if not template_path.is_file() or not license_path.is_file():
        fail(f"Previous release lacks README or license notes: {previous}")

    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    commit = args.desktop_commit or head
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
        parser.error("Desktop commit must be a Git commit hash")
    if not head.startswith(commit) and not commit.startswith(head):
        fail(f"Desktop commit {commit} differs from current HEAD {head}; verify the build source")
    status = subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip()
    if status:
        print("WARNING: git status is not clean. Confirm the supplied desktop commit matches the build HEAD.", file=sys.stderr)
    version_info = json.loads((ROOT / "packaging/version.json").read_text())
    if args.apply and f"{version_info['version']}-{version_info['release']}" != args.version:
        fail("Requested version differs from packaging/version.json")

    iso = {lang: check_iso(getattr(args, f"iso_{lang}"), lang) for lang in ("en", "de")}
    for lang in ("en", "de"):
        item = iso[lang]
        item["name"] = f"windoesnot-{args.date}-{lang}-x86_64.iso"
        if item["build_date"] != args.date:
            print(f"Rename for release: {item['source'].name} -> {item['name']} (ISO content unchanged)")
        else:
            print(f"Release name: {item['name']}")
        print(f"{lang}: {item['bytes']} bytes, SHA256 {item['sha256']}")

    dot_name = f"windoesnot-dotfiles-{args.version}.tar.gz"
    dot = {"name": dot_name, "bytes": "TODO_AFTER_EXPORT", "sha256": "TODO_AFTER_EXPORT"}
    changes = json.loads((ROOT / "packaging/changelog.json").read_text())["releases"]
    entry = next((entry for entry in changes if entry["version"] == args.version), None)
    if not entry:
        fail(f"No changelog entry for {args.version}")
    make_readme(template_path.read_text(), old_version, args.version, release_date, commit, iso, dot)
    if args.apply:
        # export-dotfiles.py insists on a new directory and writes its own checksums.
        subprocess.run([sys.executable, str(ROOT / "tools/export-dotfiles.py"),
                        "--output", str(output), "--version", match.group(1),
                        "--release", match.group(2)], check=True)
        archive = output / dot_name
        dot["bytes"] = archive.stat().st_size
        dot["sha256"] = digest(archive, "sha256")

    readme = make_readme(template_path.read_text(), old_version, args.version, release_date, commit, iso, dot)
    release_json = {"updated": release_date.isoformat(), "version": args.version,
                    "iso": {lang: metadata(iso[lang]["name"], iso[lang], args.version) for lang in ("en", "de")},
                    "dotfiles": metadata(dot_name, dot, args.version)}
    notes = [f"# WinDoesNot {args.version}", "", "## Changes (English)", ""]
    notes += [f"- {line}" for line in entry["en"]]
    notes += ["", "## Änderungen (Deutsch)", ""]
    notes += [f"- {line}" for line in entry["de"]]
    notes += ["", "## Downloads", "", "| File | Link |", "| --- | --- |"]
    for item in (iso["en"], iso["de"], dot):
        notes.append(f"| {item['name']} | [Download]({BASE_URL}/{args.version}/{item['name']}) |")
    notes += ["", f"ISO SHA256 (English): `{iso['en']['sha256']}`",
              f"ISO SHA256 (German): `{iso['de']['sha256']}`",
              f"Desktop commit: `{commit}`", "",
              "This is a pre-release. Real-hardware coverage is still being collected; back up your data.", ""]

    names = ["LICENSE-NOTES.txt", "README.md"]
    names += [dot_name + suffix for suffix in (".md5", ".sha256", "")]
    names += [iso[lang]["name"] + suffix for suffix in (".md5", ".sha256") for lang in ("en", "de")]
    names += [iso[lang]["name"] for lang in ("en", "de")]
    aws = ["aws", "--profile", "windoesnot-r2", "--region", "auto", "--endpoint-url", ENDPOINT]
    plan = ["# Check that the destination prefix does not exist. Stop if any object is listed.",
            shlex.join(aws + ["s3", "ls", f"s3://windoesnot/{args.version}/"]),
            "# Run the following commands only after the prefix is confirmed empty:"]
    for name in names:
        plan.append(shlex.join(aws + ["s3", "cp", str(output / name),
                                      f"s3://windoesnot/{args.version}/{name}", "--only-show-errors"]))
    checklist = ["Manual release steps:",
                 "[ ] Review README TODO and actual VM tests from section 5, including the install matrix where required.",
                 "[ ] Review release notes, licenses, checksums and releases.json snippet.",
                 "[ ] Repackage image packages: podman unshare python3 tools/repackage-from-image.py --image build/<id>/work/x86_64/airootfs --output build/release-packages-N <packages>.",
                 "[ ] Benni signs the update channel in his own terminal. Plan and publish the repository only after review.",
                 "[ ] Obtain approval, check the R2 prefix is empty, then upload small files before ISOs.",
                 "[ ] Update, build and check the website, then publish it after approval.",
                 "[ ] Push the desktop commit and create the GitHub pre-release after approval. Attach checksums.",
                 "[ ] Check public URLs and update channel in a VM. Clean superseded builds, out and vm scratch files per section 12.", ""]
    if args.apply:
        for lang in ("en", "de"):
            item = iso[lang]
            target = output / item["name"]
            try:
                os.link(item["source"], target)
            except OSError:
                shutil.copyfile(item["source"], target)
            (output / (item["name"] + ".sha256")).write_text(checksum_text(item["sha256"], item["name"]))
            (output / (item["name"] + ".md5")).write_text(checksum_text(digest(target, "md5"), item["name"]))
        shutil.copyfile(license_path, output / "LICENSE-NOTES.txt")
        (output / "README.md").write_text(readme)
        (output / "RELEASE-NOTES.md").write_text("\n".join(notes))
        (output / "R2-UPLOAD-PLAN.txt").write_text("\n".join(plan) + "\n")
        (output / "releases-json-snippet.json").write_text(json.dumps(release_json, indent=2) + "\n")
        (output / "RELEASE-CHECKLIST.txt").write_text("\n".join(checklist))
        print(f"Prepared local release: {output}")
    else:
        print("DRY RUN: no files written. Dotfiles bytes and SHA256 are available after --apply.")
        print(f"Would export dotfiles and write {output} with README, licenses, checksums, upload plan, JSON snippet and notes.")
        print("R2 upload plan:\n" + "\n".join(plan))
        print("Manual checklist:\n" + "\n".join(checklist))


if __name__ == "__main__":
    main()
