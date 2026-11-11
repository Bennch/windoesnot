# SPDX-License-Identifier: GPL-3.0-or-later
calamares_add_plugin(windoesnotapps
    TYPE viewmodule
    EXPORT_MACRO PLUGINDLLEXPORT_PRO
    SOURCES AppSelectionViewStep.cpp AppSelectionWidget.cpp LiveDesktopBridge.cpp
    LINK_PRIVATE_LIBRARIES calamaresui ${qtname}::Widgets
    SHARED_LIB
)
