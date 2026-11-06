// SPDX-License-Identifier: GPL-3.0-or-later
#include "WindoesnotIntroViewStep.h"

#include <QLocale>

WindoesnotIntroViewStep::WindoesnotIntroViewStep( QObject* parent )
    : Calamares::QmlViewStep( parent )
{
}

WindoesnotIntroViewStep::~WindoesnotIntroViewStep() {}

QString
WindoesnotIntroViewStep::prettyName() const
{
    // Shown in the sidebar; follows the language chosen on the welcome page.
    return QLocale().language() == QLocale::German ? QStringLiteral( "Über WinDoesNot" ) : QStringLiteral( "About WinDoesNot" );
}

CALAMARES_PLUGIN_FACTORY_DEFINITION( WindoesnotIntroViewStepFactory, registerPlugin< WindoesnotIntroViewStep >(); )
