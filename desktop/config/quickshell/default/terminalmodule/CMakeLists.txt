cmake_minimum_required(VERSION 3.21)
project(LocalTerminal LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# Use $ORIGIN-relative RPATH so LocalTerminal/ is self-contained
set(CMAKE_BUILD_RPATH_USE_ORIGIN ON)
set(CMAKE_INSTALL_RPATH_USE_LINK_PATH OFF)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Qml Quick Widgets)
find_package(PkgConfig REQUIRED)
pkg_check_modules(QTERMWIDGET REQUIRED IMPORTED_TARGET qtermwidget6)

set(MODULE_OUTPUT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../widgets/terminalmodule/LocalTerminal")

qt_add_library(localterminalplugin SHARED)

# Place main library alongside the plugin so LocalTerminal/ is fully self-contained
set_target_properties(localterminalplugin PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${MODULE_OUTPUT_DIR}"
)

qt_add_qml_module(localterminalplugin
    URI LocalTerminal
    VERSION 1.0
    OUTPUT_DIRECTORY "${MODULE_OUTPUT_DIR}"
    SOURCES
        EmbeddedTerminal.hpp
        EmbeddedTerminal.cpp
)

target_link_libraries(localterminalplugin PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Qml
    Qt6::Quick
    Qt6::Widgets
    PkgConfig::QTERMWIDGET
)
