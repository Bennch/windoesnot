#!/usr/bin/env python3
"""Apply reviewed text-only translations to a disposable bootloader source copy.

Global writable text arrays keep C constant-address initializers and native menu
width calculations valid. One early locale-file read selects the catalog, before
menus are created. No paths, entry identifiers or boot protocols are translated.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
STRING = r'(?:u8|[LuU])?"(?:\\.|[^"\\])*"'
TOKENS = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|(?P<group>" + STRING + r'(?:\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*)?' + STRING + r')*)')
LITERALS = re.compile(STRING)


def decode(token):
    token = re.sub(r'^(?:u8|[LuU])', '', token)
    token = re.sub(r'(\\+)e', lambda m: m[1][:-1] + r'\033' if len(m[1]) % 2 else m[0], token)
    return ast.literal_eval(token)


def formats(text):
    return re.findall(r'%(?:[0-9]+\$)?[-+#0 \']*(?:[0-9]+|\*)?(?:\.(?:[0-9]+|\*))?(?:hh|ll|[hljztL])?[diouxXfFeEgGaAcCsSpnmrDUVS%]|%#|%$', text)


def patch(kind, source, catalog):
    source = source.resolve()
    if (source / '.git').exists() or source.is_relative_to(ROOT / 'upstream'):
        raise ValueError('Use a disposable source copy; upstream checkouts stay unchanged')
    if kind == 'refind':
        # Match the distribution package's GNU-EFI 4 fixes, including CompareGuid
        # semantics; successful linking alone does not establish compatibility.
        for name in ('gnu-efi-4-compat', 'fix-target-option'):
            subprocess.run(['patch', '--batch', '--forward', '-p1', '-d', str(source), '-i', str(ROOT / f'iso/boot-language/refind-{name}.patch')], check=True, stdout=subprocess.DEVNULL)
    if kind == 'systemd-boot':
        directory = source / 'src/boot'; main = directory / 'boot.c'
    elif kind == 'refind':
        directory = source / 'refind'; main = directory / 'main.c'
    else:
        directory = source / 'common'; main = directory / 'menu.c'
    if (directory / 'windoesnot-language.h').exists():
        raise ValueError('Source is already patched; use a fresh build copy')
    for en, de in catalog.items():
        if formats(en) != formats(de):
            raise ValueError('Format argument mismatch: ' + en)
        if not isinstance(de, str) or not de or '\0' in de:
            raise ValueError('Invalid translation: ' + en)
    declarations, definitions, assignments, used = [], [], [], set()
    count = 0
    for path in sorted(directory.rglob('*.c')):
        if path.name.startswith(('test-', 'fuzz-')) or path.name.endswith('.s2.c'):
            continue
        text = path.read_text()
        def replace(match):
            nonlocal count
            group = match.group('group')
            if group is None:
                return match.group()
            # Preprocessor directives, build identifiers and inline asm are not UI.
            line = text[text.rfind('\n', 0, match.start()) + 1:match.start()]
            context = text[max(0, match.start()-1000):match.start()].split(';')[-1].split('{')[-1]
            if line.lstrip().startswith('#') or re.search(r'\b(?:_Static_assert|static_assert|asm|__asm__|sizeof)\s*\(', context):
                return group
            selected = []
            def translate(literal):
                token = literal.group(); value = decode(token)
                if value not in catalog:
                    return token
                # Short keywords used by native parsers must retain their exact
                # spelling even when the same word is displayed elsewhere.
                if ' ' not in value.strip() and re.search(r'\b(?:MyStriCmp|MyStrCmp|StriCmp|StrCmp|strcmp|strncmp|strcasecmp|strncasecmp|streq8|strcaseeq8|streq16|strcaseeq16|streq|strcaseeq)\s*\([^;{}]*$', context):
                    return token
                selected.append(value)
                prefix = token[:token.index('"')]
                # ASCII transliteration works with native bitmap console fonts.
                return prefix + json.dumps(catalog[value], ensure_ascii=True)
            joined = ''.join(decode(m.group()) for m in LITERALS.finditer(group))
            if not LITERALS.sub('', group).strip() and joined in catalog and (len(list(LITERALS.finditer(group))) > 1 or ' ' in joined.strip()):
                selected.append(joined)
                first = LITERALS.search(group).group()
                translated = first[:first.index('"')] + json.dumps(catalog[joined], ensure_ascii=True)
            else:
                translated = LITERALS.sub(translate, group)
            if not selected:
                return group
            # An array initialized by a literal must remain an array. These rare
            # cases are explicitly rejected instead of changing its C semantics.
            if re.search(r'\b(?:char|char16_t|CHAR16)\s+\w+\s*\[[^]]*\]\s*=\s*$', line):
                raise ValueError(f'Array initializer needs review: {path}:{selected[0]}')
            symbol = f'wdn_text_{count}'; count += 1
            first = LITERALS.search(group).group()
            prefix = first[:first.index('"')]
            size = sum(len(decode(m.group())) for m in LITERALS.finditer(group)) + sum(len(catalog[s]) for s in selected) + 128
            ctype = '__CHAR16_TYPE__' if prefix == 'u' else '__WCHAR_TYPE__' if prefix == 'L' else 'char'
            declarations.append(f'extern {ctype} {symbol}[{size}];')
            definitions.append(f'{ctype} {symbol}[{size}] = {group};')
            # Source arrays are copied, with the NUL terminator, once at startup.
            assignments.append(f'    {{ const {ctype} value[] = {translated}; for (unsigned n = 0; n < sizeof(value)/sizeof(value[0]); n++) {symbol}[n] = value[n]; }}')
            used.update(selected)
            return symbol
        updated = TOKENS.sub(replace, text)
        if updated != text:
            # Place declarations after includes: native headers define format
            # types and attributes used by these translation units.
            updated = '#include "' + str(Path(__import__('os').path.relpath(directory / 'windoesnot-language.h', path.parent))) + '"\n' + updated
            path.write_text(updated)
    header = '#pragma once\n#pragma GCC diagnostic ignored "-Wformat-nonliteral"\n#pragma GCC diagnostic ignored "-Wformat-security"\nvoid windoesnot_language_init(const char *language);\n' + '\n'.join(declarations) + '\n'
    (directory / 'windoesnot-language.h').write_text(header)
    # Define in an existing main unit; upstream build lists remain untouched.
    main_text = main.read_text()
    if kind == 'systemd-boot':
        main_text = re.sub(r'\byes_no\(', 'windoesnot_yes_no(', main_text)
    includes = list(re.finditer(r'^\s*#include[^\n]*\n', main_text, re.M))
    offset = includes[-1].end()
    while re.match(r'\s*#endif[^\n]*\n', main_text[offset:]):
        offset += re.match(r'\s*#endif[^\n]*\n', main_text[offset:]).end()
    body = '\n#include "windoesnot-language.h"\n' + '\n'.join(definitions) + '\nvoid windoesnot_language_init(const char *language) {\n    if (!language || language[0] != \'d\' || language[1] != \'e\') return;\n' + '\n'.join(assignments) + '\n}\n'
    if kind == 'systemd-boot':
        body = body.replace('void windoesnot_language_init(const char *language) {',
                            'static bool windoesnot_german;\nvoid windoesnot_language_init(const char *language) {')
        body = body.replace("language[1] != 'e') return;", "language[1] != 'e') return;\n    windoesnot_german = true;")
        body += 'static const char16_t *windoesnot_yes_no(bool b) { return b ? (windoesnot_german ? u"ja" : u"yes") : (windoesnot_german ? u"nein" : u"no"); }\n'
    elif kind == 'limine':
        body = body.replace('void windoesnot_language_init(const char *language) {',
                            'static int windoesnot_german;\nvoid windoesnot_language_init(const char *language) {')
        body = body.replace("language[1] != 'e') return;", "language[1] != 'e') return;\n    windoesnot_german = 1;")
        body += ('static const char *windoesnot_display_name(const char *name) {\n'
                 '    if (strcmp(name, "Snapshots") == 0)\n'
                 '        return windoesnot_german ? "Wiederherstellungspunkte" : "Restore points";\n'
                 '    return name;\n}\n')
    main_text = main_text[:offset] + body + main_text[offset:]
    if kind == 'limine':
        needle = '    char *quiet_str = config_get_value(NULL, 0, "QUIET");'
        insertion = '    windoesnot_language_init(config_get_value(NULL, 0, "windoesnot_language"));\n\n'
    elif kind == 'systemd-boot':
        needle = '        config_load_defaults(config, root_dir);'
        insertion = ('        {\n'
                     '                _cleanup_free_ char *language = NULL;\n'
                     '                if (file_read(root_dir, u"\\\\loader\\\\windoesnot-language", 0, 8, &language, NULL) == EFI_SUCCESS)\n'
                     '                        windoesnot_language_init(language);\n'
                     '        }\n')
    else:
        # Volume descriptions are composed by ScanVolumes, before ReadConfig.
        # Translate first so cached labels use the same language as the menu.
        needle = '    ScanVolumes();'
        insertion = ('    {\n'
                     '        UINT8 *language = NULL; UINTN language_size = 0;\n'
                     '        if (!EFI_ERROR(egLoadFile(SelfDir, L"windoesnot-language", &language, &language_size)) && language_size >= 2)\n'
                     '            windoesnot_language_init((const char *)language);\n'
                     '        if (language) FreePool(language);\n'
                     '    }\n')
    if needle not in main_text:
        raise ValueError('Pinned source integration point is missing')
    # rEFInd rescans must not change language mid-session; initialization is
    # idempotent and may run before its configuration reader on a rescan too.
    main.write_text(main_text.replace(needle, insertion + needle))
    if kind == 'limine':
        text = main.read_text()
        needle = 'size_t name_len = strlen(current_entry->name);'
        if needle not in text:
            raise ValueError('Pinned Limine display-name integration point is missing')
        text = text.replace(needle, 'const char *display_name = windoesnot_display_name(current_entry->name);\n            size_t name_len = strlen(display_name);')
        text = text.replace(r'current_entry->name, (size_t)(max_name - 3)', r'display_name, (size_t)(max_name - 3)')
        text = text.replace(r'" %s \e[27m\n", current_entry->name', r'" %s \e[27m\n", display_name')
        text = text.replace('config_entry_editor(selected_menu_entry->name,', 'config_entry_editor(windoesnot_display_name(selected_menu_entry->name),')
        main.write_text(text)
        uri = directory / 'lib/uri.c'
        text = uri.read_text().replace('print(FMT "\\n", ##__VA_ARGS__);', 'print(FMT, ##__VA_ARGS__); print("\\n");')
        uri.write_text(text)
    if kind == 'systemd-boot':
        header = directory / 'efi-log.h'
        text = header.read_text()
        text = text.replace('_gnu_printf_(3, 4) EFI_STATUS log_internal(EFI_STATUS status, LogLevel log_level, const char *format, ...);',
            '_gnu_printf_(6, 7) EFI_STATUS log_internal(EFI_STATUS status, LogLevel log_level, const char *file, int line, const char *function, const char *format, ...);')
        text = text.replace('log_internal(status, log_level, "%s:%i@%s: " format, __FILE__, __LINE__, __func__, ##__VA_ARGS__)',
            'log_internal(status, log_level, __FILE__, __LINE__, __func__, format, ##__VA_ARGS__)')
        header.write_text(text)
        impl = directory / 'efi-log.c'
        text = impl.read_text().replace('EFI_STATUS log_internal(EFI_STATUS status, LogLevel log_level, const char *format, ...)',
            'EFI_STATUS log_internal(EFI_STATUS status, LogLevel log_level, const char *file, int line, const char *function, const char *format, ...)')
        text = text.replace('        vprintf_status(status, format, ap);',
            '        printf("%s:%i@%s: ", file, line, function);\n        vprintf_status(status, format, ap);')
        impl.write_text(text)

    report = {'schema_version': 1, 'bootloader': kind, 'arrays': count, 'messages': len(used),
              'catalog_sha256': hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest(),
              'unmatched_catalog': sorted(set(catalog) - used)}
    (source / 'WINDOESNOT-LANGUAGE.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bootloader', choices=['limine', 'refind', 'systemd-boot'])
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    catalog = json.loads((ROOT / f'iso/boot-language/{args.bootloader}-de.json').read_text())
    print(json.dumps(patch(args.bootloader, args.source, catalog), indent=2))

if __name__ == '__main__':
    main()
