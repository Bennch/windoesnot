# SPDX-License-Identifier: GPL-3.0-or-later
if(NOT WITH_QML)
    calamares_skip_module( "windoesnotintro (QML is not supported in this build)" )
    return()
endif()

calamares_add_plugin(windoesnotintro
    TYPE viewmodule
    EXPORT_MACRO PLUGINDLLEXPORT_PRO
    SOURCES
        WindoesnotIntroViewStep.cpp
    RESOURCES
        windoesnotintro.qrc
    SHARED_LIB
)
