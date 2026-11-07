# SPDX-License-Identifier: GPL-3.0-or-later
calamares_add_plugin(windoesnotmigrate
    TYPE viewmodule
    EXPORT_MACRO PLUGINDLLEXPORT_PRO
    SOURCES MigrateViewStep.cpp
    LINK_PRIVATE_LIBRARIES calamaresui ${qtname}::Widgets ${qtname}::QuickWidgets ${qtname}::Qml
    SHARED_LIB
)
