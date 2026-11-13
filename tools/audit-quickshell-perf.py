#!/usr/bin/env python3
"""Static, repeatable performance inventory for the portable desktop sources.

This reports source patterns, not runtime measurements. Run from any directory:
  tools/audit-quickshell-perf.py
  tools/audit-quickshell-perf.py --root /path/to/checkout
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str
    severity: str
    reason: str


SOURCE_SUFFIXES = {".qml", ".js", ".py", ".sh", ".lua", ".conf"}
SKIP_PARTS = {".git", "img", "images", "icons", "__pycache__"}
PROCESS_TOOLS = re.compile(
    r"(?:bash\s+-c|hyprctl|windoesnot-hyprctl|jq|grep|date|upower|nmcli|"
    r"bluetoothctl|pactl|wpctl|awk|sed|cut|head|python3?|systemctl)\b",
    re.I,
)
TIMER_START = re.compile(r"\bTimer\s*\{")
INTERVAL = re.compile(r"\binterval\s*:\s*(\d+)")
RUN_ASSIGNMENT = re.compile(r"\b([A-Za-z_$][\w$]*)\.running\s*=\s*true\b")


def source_files(root: Path):
    """Yield relevant, text-like sources from the requested audit scope."""
    roots = [
        root / "desktop",
        root / "extras",
    ]
    for base in roots:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            yield path


def _block_end(lines: list[str], start: int) -> int:
    depth = 0
    opened = False
    for index in range(start, min(len(lines), start + 100)):
        # Basic brace counting is deterministic and sufficient for local QML blocks.
        depth += lines[index].count("{") - lines[index].count("}")
        opened |= "{" in lines[index]
        if opened and depth <= 0:
            return index + 1
    return min(len(lines), start + 100)


def _severity(category: str, source: str) -> tuple[str, str]:
    if category == "short-running-timer":
        interval = INTERVAL.search(source)
        severity = "hoch" if interval and int(interval.group(1)) <= 250 else "mittel"
        return severity, "Kurzes Timerintervall; laufend erzeugt regelmäßige CPU/IPC-Arbeit. Sichtbarkeit und Eingabeabhängigkeit prüfen."
    if category == "process-per-tick":
        return "hoch", "Ein Prozessstart pro Poll-Tick; Shell/Pipeline und IPC vervielfachen den festen Startaufwand."
    if category == "daemon-or-loop":
        return "mittel", "Dauerprozess oder Schleife; Grundlast hängt von Wartezeit und Aktivität ab."
    if category == "polling-event-candidate":
        return "mittel", "Polling kann Änderungen wiederholt abfragen; Hyprland IPC, D-Bus oder Dateiwächter als Ereignisquelle prüfen."
    if category == "large-image-candidate":
        return "niedrig", "Rasterbild ohne erkennbares sourceSize/asynchronous/cache; Dekodiergröße und Ladezeit zur Laufzeit prüfen."
    if category == "visual-effect":
        return "mittel", "Effekt/Animation kann GPU-Compositing und Frame-Arbeit erhöhen, besonders bei großen Flächen."
    if category == "eager-repeater":
        return "niedrig", "Repeater erzeugt alle Delegates sofort; bei großen Modellen ListView/GridView erwägen."
    if category == "eager-popup":
        return "mittel", "Versteckter Popup-Inhalt wird beim Shell-Start geladen; Loader/LazyLoader kann Arbeit auf Öffnen verschieben."
    if category == "json-reparse":
        return "niedrig", "JSON.parse/json.loads im wiederholten Pfad kann dieselben Daten mehrfach dekodieren."
    return "niedrig", "Statischer Kandidat; tatsächliche Laufzeitwirkung messen."


def analyze_file(path: Path, root: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    rel = path.relative_to(root).as_posix()
    findings: list[Finding] = []

    # Timer block analysis: attach timing/command patterns to the timer's line.
    process_commands = {}
    for process_index, process_line in enumerate(lines):
        if re.search(r"\bProcess\s*\{", process_line):
            process_end = _block_end(lines, process_index)
            process_block = "\n".join(lines[process_index:process_end])
            process_id = re.search(r"\bid\s*:\s*([\w$]+)", process_block)
            command = re.search(r"\bcommand\s*:\s*(.+)", process_block)
            if process_id:
                process_commands[process_id.group(1)] = command.group(1).strip() if command else "(dynamischer Befehl)"
    for index, line in enumerate(lines):
        if TIMER_START.search(line):
            end = _block_end(lines, index)
            block = "\n".join(lines[index:end])
            interval = INTERVAL.search(block)
            repeating = bool(re.search(r"\brepeat\s*:\s*true", block))
            if interval and int(interval.group(1)) <= 1000 and repeating and re.search(r"running\s*:\s*true", block):
                findings.append(Finding(rel, index + 1, "short-running-timer", *_severity("short-running-timer", block)))
            assignments = RUN_ASSIGNMENT.findall(block)
            if interval and repeating and assignments:
                commands = [f"{name}: {process_commands.get(name, '(dynamischer Befehl)')}" for name in assignments]
                severity = "hoch" if int(interval.group(1)) <= 250 else "mittel"
                findings.append(Finding(rel, index + 1, "process-per-tick", severity,
                    f"{len(assignments)} Prozessstart(s) je Tick ({'; '.join(commands)})."))
            if interval and repeating and re.search(r"hyprctl|windoesnot-hyprctl|nmcli|upower|pactl|wpctl", block, re.I):
                findings.append(Finding(rel, index + 1, "polling-event-candidate", *_severity("polling-event-candidate", block)))

    patterns = [
        ("daemon-or-loop", re.compile(r"--watch\b|\bserve\b|while\s*(?:true|:|\[|\()", re.I)),
        ("visual-effect", re.compile(r"MultiEffect|DropShadow|StyledRectangularShadow|\bBlur\b|\bBehavior\s+on\b|\b(?:Number|Color|Opacity)Animation\b")),
        ("eager-repeater", re.compile(r"\bRepeater\s*\{")),
        ("eager-popup", re.compile(r"\b(?:FloatingWindow|Popup)\s*\{")),
        ("json-reparse", re.compile(r"JSON\.parse\s*\(|json\.loads\s*\(")),
    ]
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "#", "*")):
            continue
        for category, pattern in patterns:
            if pattern.search(line):
                severity, reason = _severity(category, line)
                findings.append(Finding(rel, lineno, category, severity, reason))
        if re.search(r"\bImage\s*\{", line):
            block = "\n".join(lines[lineno - 1:_block_end(lines, lineno - 1)])
            if re.search(r"source\s*:\s*[^\n]+\.(?:png|jpe?g|webp)", block, re.I) and not re.search(r"sourceSize(?:\s*\.|\s*:)", block):
                category = "large-image-candidate"
                severity, reason = _severity(category, block)
                findings.append(Finding(rel, lineno, category, severity, reason))

    # Count and report process launches that occur in timer blocks, not just tool mentions.
    return findings


def analyze(root: Path) -> list[Finding]:
    findings = []
    for path in source_files(root):
        findings.extend(analyze_file(path, root))
    # Reference.lua serializes defaults as a Lua table on one line in this repository.
    reference = root / "desktop/config/hypr/lua/reference.lua"
    if reference.exists():
        text = reference.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"\[\"autostart\"\]\s*=\s*\{([^}]*)\}", text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            for entry in re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1)):
                findings.append(Finding(reference.relative_to(root).as_posix(), line,
                    "autostart", "mittel", f"Autostart-Kommando: `{entry}`; Startkosten/Dauerprozess prüfen."))
    # Stable output: path, line, category regardless of filesystem traversal details.
    return sorted(findings, key=lambda item: (item.path, item.line, item.category, item.reason))


def markdown(findings: list[Finding]) -> str:
    rows = ["# Quickshell/Desktop Performance-Audit", "",
            "> Statische Heuristiken, keine Laufzeitmessung. Lastklasse ist eine begründete qualitative Einschätzung.", "",
            "| Datei | Zeile | Befund | Last | Begründung |", "|---|---:|---|---|---|"]
    for f in findings:
        reason = f.reason.replace("|", "\\|")
        rows.append(f"| `{f.path}` | {f.line} | {f.category} | {f.severity} | {reason} |")
    if not findings:
        rows.append("| — | — | Keine Treffer | niedrig | Keine passenden Muster gefunden. |")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(markdown(analyze(args.root.resolve())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
