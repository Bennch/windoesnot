#include <format>
#include <string>
#include <utility>

#include <hyprland/src/desktop/view/window/Window.hpp>
#include <hyprland/src/config/shared/actions/ConfigActions.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/layout/supplementary/DragController.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/state/ViewHitTester.hpp>
#include <hyprland/src/desktop/view/LayerSurface.hpp>
#include <hyprland/src/state/MonitorState.hpp>
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/state/LayerState.hpp>
#include <hyprland/src/protocols/LayerShell.hpp>
#include <chrono>
#include <linux/input-event-codes.h>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <hyprland/src/version.h>

#include "globals.hpp"

APICALL EXPORT std::string PLUGIN_API_VERSION() {
    return HYPRLAND_API_VERSION;
}

namespace {
    CHyprSignalListener mouseMoveListener;
    CHyprSignalListener mouseButtonListener;
    CHyprSignalListener keyboardListener;
    CHyprSignalListener windowCloseListener;
    UP<SEventLoopDoLaterLock> pendingUpdate;

    PHLWINDOWREF lastDraggedWindow;
    std::string lastAddress;
    bool wasMoving = false;

    std::chrono::steady_clock::time_point lastPosEvent;

    // Stream the pointer position while a window is moved, so the snap logic in the shell reacts to every motion
    // instead of polling hyprctl. Throttled to ~120 Hz; the final position is always sent (force).
    void postPosition(bool force = false) {
        const auto now = std::chrono::steady_clock::now();
        if (!force && now - lastPosEvent < std::chrono::milliseconds(8))
            return;
        lastPosEvent = now;
        const auto mouse = g_pInputManager->getMouseCoordsInternal();
        (void)Config::Actions::event(std::format("hyprdrag-pos>>{},{}", static_cast<int>(mouse.x), static_cast<int>(mouse.y)));
    }

    // While a window is resized, stream its geometry the same way ("hyprdrag-geo>>addr,x,y,w,h"): a snapped neighbour
    // follows the shared edge from these events instead of a polled hyprctl snapshot.
    void postGeometry(bool force = false) {
        const auto now = std::chrono::steady_clock::now();
        if (!force && now - lastPosEvent < std::chrono::milliseconds(8))
            return;
        const auto window = lastDraggedWindow.lock();
        if (!validMapped(window))
            return;
        lastPosEvent = now;
        const auto pos  = window->position(Desktop::View::IGeometric::GEOMETRIC_CURRENT);
        const auto size = window->size(Desktop::View::IGeometric::GEOMETRIC_CURRENT);
        (void)Config::Actions::event(std::format("hyprdrag-geo>>{},{},{},{},{}", lastAddress, static_cast<int>(pos.x), static_cast<int>(pos.y),
                                                 static_cast<int>(size.x), static_cast<int>(size.y)));
    }

    // ---- Explicit edge resizing -------------------------------------------------------------------------------------
    // Hyprland's own resize_on_border showed the right arrow on hover but started the drag as a corner resize (both axes)
    // for side edges. Take over the press: a side edge resizes along that one axis, a bottom corner along both, with the
    // edge named explicitly (same call hyprbars uses for the top corners). Floating windows only; tiling is untouched.
    bool borderResizeActive = false;

    // Which edge of `window` is under `mouse`, or CORNER_NONE. The top edge belongs to the title bar.
    Layout::eRectCorner borderEdgeAt(const PHLWINDOW& window, const Vector2D& mouse) {
        constexpr double OUTSIDE = 12.0;  // grab band outside the window (Hyprland extends the border grab area by 15)
        constexpr double INSIDE  = 5.0;   // and a few pixels inside
        constexpr double CORNER  = 28.0;  // extent of a bottom corner along the edges
        const auto pos  = window->position(Desktop::View::IGeometric::GEOMETRIC_CURRENT);
        const auto size = window->size(Desktop::View::IGeometric::GEOMETRIC_CURRENT);
        const double x = mouse.x - pos.x, y = mouse.y - pos.y;
        const bool inBandX = y >= 0 && y <= size.y + OUTSIDE;
        const bool inBandY = x >= -OUTSIDE && x <= size.x + OUTSIDE;
        const bool left   = inBandX && x >= -OUTSIDE && x <= INSIDE;
        const bool right  = inBandX && x >= size.x - INSIDE && x <= size.x + OUTSIDE;
        const bool bottom = inBandY && y >= size.y - INSIDE && y <= size.y + OUTSIDE;
        if (bottom && left && x <= CORNER - OUTSIDE)
            return Layout::CORNER_BOTTOMLEFT;
        if (bottom && right && x >= size.x - CORNER + OUTSIDE)
            return Layout::CORNER_BOTTOMRIGHT;
        if (bottom && !left && !right) {
            if (x <= CORNER - OUTSIDE)
                return Layout::CORNER_BOTTOMLEFT;
            if (x >= size.x - CORNER + OUTSIDE)
                return Layout::CORNER_BOTTOMRIGHT;
            return Layout::CORNER_BOTTOM;
        }
        if (left && y >= size.y - CORNER)
            return Layout::CORNER_BOTTOMLEFT;
        if (right && y >= size.y - CORNER)
            return Layout::CORNER_BOTTOMRIGHT;
        if (left)
            return Layout::CORNER_LEFT;
        if (right)
            return Layout::CORNER_RIGHT;
        if (bottom)
            return Layout::CORNER_BOTTOM;
        return Layout::CORNER_NONE;
    }

    bool tryBorderResize(Event::SCallbackInfo& info) {
        if (!g_layoutManager || !g_pInputManager || g_pSeatManager->m_seatGrab || static_cast<uint32_t>(g_pInputManager->getModsFromAllKBs()) != 0)
            return false;

        const auto mouse   = g_pInputManager->getMouseCoordsInternal();
        const auto monitor = Desktop::focusState()->monitor();
        if (!monitor)
            return false;

        Desktop::CViewHitTester hitTester{*Desktop::viewState()};
        const auto window = hitTester.windowAt(mouse, Desktop::View::RESERVED_EXTENTS | Desktop::View::INPUT_EXTENTS | Desktop::View::ALLOW_FLOATING);
        if (!validMapped(window) || !window->isFloating() || window->metadata().title().starts_with("quickshell-"))
            return false;

        // Panels above windows (taskbar ...) keep their clicks.
        PHLLS    surface = nullptr;
        Vector2D local;
        hitTester.layerSurfaceAt(mouse, &monitor->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_TOP], &local, &surface);
        if (surface)
            return false;
        hitTester.layerSurfaceAt(mouse, &monitor->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY], &local, &surface);
        if (surface)
            return false;

        const auto edge = borderEdgeAt(window, mouse);
        if (edge == Layout::CORNER_NONE)
            return false;

        // A press inside the window's own surface (INSIDE band) must still reach the app when the pointer is over content.
        if (Desktop::focusState()->window() != window)
            Desktop::focusState()->fullWindowFocus(window, Desktop::FOCUS_REASON_CLICK);
        Desktop::windowState()->raise(window);

        info.cancelled = true;
        g_layoutManager->beginDragTarget(window->layoutTarget(), MBIND_RESIZE, edge);
        borderResizeActive = true;
        return true;
    }

    void postDragEvent(const PHLWINDOW& window, const std::string& address, bool moving, bool start, bool updateTag = true) {
        const char* event = start ? (moving ? "hyprdrag-movestart" : "hyprdrag-resizestart")
                                  : (moving ? "hyprdrag-movestop" : "hyprdrag-resizestop");
        (void)Config::Actions::event(std::format("{}>>{}", event, address));

        if (updateTag && validMapped(window)) {
            const std::string tag = std::format("{}hyprdrag-{}", start ? "" : "-", moving ? "move" : "resize");
            // Native action works with both config managers and preserves the
            // same tag/rule updates as the old tagwindow dispatcher.
            (void)Config::Actions::tag(tag, window);
        }
    }

    void finishDrag(bool updateTag = true) {
        if (lastAddress.empty())
            return;

        if (wasMoving)
            postPosition(true);
        else
            postGeometry(true);
        const auto window = lastDraggedWindow.lock();
        const auto address = std::exchange(lastAddress, {});
        lastDraggedWindow.reset();
        postDragEvent(window, address, wasMoving, false, updateTag);
    }

    void syncDragState() {
        if (!g_layoutManager)
            return;

        const auto& controller = g_layoutManager->dragController();
        const auto target = controller->target();
        const auto window = target ? target->window() : nullptr;
        const bool dragging = validMapped(window) && controller->mode() != MBIND_INVALID && controller->dragThresholdReached();
        const bool moving = controller->mode() == MBIND_MOVE;

        if (!lastAddress.empty() && (!dragging || lastDraggedWindow.lock() != window || moving != wasMoving))
            finishDrag();

        if (dragging && lastAddress.empty()) {
            wasMoving = moving;
            lastDraggedWindow = window;
            lastAddress = std::format("0x{:x}", reinterpret_cast<uintptr_t>(window.get()));
            postDragEvent(window, lastAddress, moving, true);
        }
    }

    void scheduleDragUpdate() {
        // Input signals precede Hyprland's drag handling. Check again after the
        // event, especially on release without any further pointer movement.
        // The lock cancels the idle callback when the plugin is unloaded.
        if (!pendingUpdate) {
            pendingUpdate = g_pEventLoopManager->doLaterLock([] {
                pendingUpdate.reset();
                syncDragState();
            });
        }
    }
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    PHANDLE = handle;
    const std::string serverHash = __hyprland_api_get_hash();
    const std::string clientHash = __hyprland_api_get_client_hash();
    if (serverHash != clientHash)
        throw std::runtime_error(std::format("[hyprdrag] Version mismatch: running {}, built {}", serverHash, clientHash));

    mouseMoveListener = Event::bus()->m_events.input.mouse.move.listen([](Vector2D, Event::SCallbackInfo&) {
        syncDragState();
        if (!lastAddress.empty()) {
            if (wasMoving)
                postPosition();
            else
                postGeometry();
        }
        scheduleDragUpdate();
    });
    mouseButtonListener = Event::bus()->m_events.input.mouse.button.listen([](IPointer::SButtonEvent e, Event::SCallbackInfo& info) {
        if (e.button == BTN_LEFT) {
            if (e.state == WL_POINTER_BUTTON_STATE_PRESSED)
                tryBorderResize(info);
            else if (borderResizeActive) {
                borderResizeActive = false;
                info.cancelled = true;
                (void)g_layoutManager->endDragTarget();
            }
        }
        syncDragState();
        scheduleDragUpdate();
    });
    keyboardListener = Event::bus()->m_events.input.keyboard.key.listen([](IKeyboard::SKeyEvent, Event::SCallbackInfo&) {
        // Keybinds can cancel a drag without a subsequent mouse event.
        scheduleDragUpdate();
    });
    windowCloseListener = Event::bus()->m_events.window.close.listen([](PHLWINDOW window) {
        if (lastDraggedWindow.lock() == window)
            finishDrag(false);
    });

    return {"hyprdrag", "Window move/resize interaction plugin", "yz778", "0.2.0"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    mouseMoveListener.reset();
    mouseButtonListener.reset();
    keyboardListener.reset();
    windowCloseListener.reset();
    pendingUpdate.reset();
    finishDrag();
    wasMoving = false;
    PHANDLE = nullptr;
}
