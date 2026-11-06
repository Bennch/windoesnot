// SPDX-License-Identifier: GPL-3.0-or-later
// Information page after the language choice. Based on Calamares' notesqml module (GPL-3.0-or-later).
#ifndef WINDOESNOTINTROVIEWSTEP_H
#define WINDOESNOTINTROVIEWSTEP_H

#include "DllMacro.h"
#include "utils/PluginFactory.h"
#include "viewpages/QmlViewStep.h"

class PLUGINDLLEXPORT WindoesnotIntroViewStep : public Calamares::QmlViewStep
{
    Q_OBJECT

public:
    explicit WindoesnotIntroViewStep( QObject* parent = nullptr );
    ~WindoesnotIntroViewStep() override;

    QString prettyName() const override;
};

CALAMARES_PLUGIN_FACTORY_DECLARATION( WindoesnotIntroViewStepFactory )

#endif
