# SPDX-License-Identifier: GPL-3.0-or-later
calamares_add_plugin(windoesnotboot
    TYPE viewmodule
    EXPORT_MACRO PLUGINDLLEXPORT_PRO
    SOURCES BootSelectionViewStep.cpp BootSelectionWidget.cpp
    LINK_PRIVATE_LIBRARIES calamaresui ${qtname}::Widgets
    SHARED_LIB
)
