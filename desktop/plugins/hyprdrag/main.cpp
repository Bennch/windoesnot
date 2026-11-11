#include <format>
#include <string>
#include <utility>

#include <hyprland/src/desktop/view/window/Window.hpp>
#include <hyprland/src/config/shared/actions/ConfigActions.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/layout/supplementary/DragController.hpp>
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
        scheduleDragUpdate();
    });
    mouseButtonListener = Event::bus()->m_events.input.mouse.button.listen([](IPointer::SButtonEvent, Event::SCallbackInfo&) {
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
