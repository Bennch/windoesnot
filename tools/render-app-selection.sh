#!/usr/bin/env bash
# Render the installer's app selection (Qt widget only, no Calamares) to PNG files on the host.
# Usage: tools/render-app-selection.sh [outdir]   -> outdir/{dark,light}-{all,ai}.png
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out=${1:-$(mktemp -d)}; mkdir -p "$out"
src="$project/iso/modules/windoesnotapps"
work=$(mktemp -d); trap 'rm -rf -- "$work"' EXIT
cat > "$work/main.cpp" <<'CPP'
#include <QApplication>
#include <QPushButton>
#include <QTimer>
#include "AppSelectionWidget.h"
int main(int argc, char** argv) {
    QApplication app(argc, argv);   // argv: catalog dark|light category(or "") output.png
    AppSelectionWidget w(argv[1]);
    w.setGerman(true); w.setDarkMode(QString(argv[2]) == "dark"); w.resize(900, 560); w.show();
    const QString category = argv[3];
    if (!category.isEmpty()) for (auto* b : w.findChildren<QPushButton*>("navEntry")) if (b->property("catId").toString() == category) b->click();
    QTimer::singleShot(300, [&] { w.grab().save(argv[4]); QApplication::quit(); });
    return app.exec();
}
CPP
g++ -std=c++17 -fPIC -I"$src" $(pkg-config --cflags Qt6Widgets) "$work/main.cpp" "$src/AppSelectionWidget.cpp" -o "$work/render" $(pkg-config --libs Qt6Widgets)
for theme in dark light; do for category in "" ai; do
    QT_QPA_PLATFORM=offscreen "$work/render" "$project/iso/software/catalog.json" $theme "$category" "$out/$theme-${category:-all}.png"
done; done
echo "$out"
