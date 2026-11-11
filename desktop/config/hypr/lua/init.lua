-- Shared WinDoesNot Hyprland Lua entry point.
local root = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
local reference = dofile(root .. "reference.lua")
local state = dofile(root .. "state.lua")
local personal = {}
local personalFile = io.open(root .. "host.lua", "r")
if personalFile then personalFile:close(); personal = dofile(root .. "host.lua") end
local geometry = {rules = {}}
local geometryFile = io.open(root .. "geometry.lua", "r")
if geometryFile then geometryFile:close(); geometry = dofile(root .. "geometry.lua") end
local primary = geometry.primary_monitor or state.primary_monitor
local verify = os.getenv("BENNI_LUA_VERIFY") == "1"
local isolated = os.getenv("BENNI_LUA_ISOLATED") == "1"
local pluginRoot = os.getenv("BENNI_LUA_PLUGIN_DIR") or (os.getenv("HOME") .. "/.config/hypr/plugins")

-- First parse queues the plugins. Hyprland loads them and reparses; plugin
-- functions and effects are registered by the time the second parse runs.
if not verify then
    hl.plugin.load(pluginRoot .. "/hyprbars.so")
    hl.plugin.load(pluginRoot .. "/hyprdrag.so")
end
local hasBars = not verify and hl.plugin.hyprbars and hl.plugin.hyprbars.add_button
local options = {}
for key, value in pairs(reference.options) do
    if not key:match("^plugin%.") or hasBars then options[key] = value end
end
for key, value in pairs(state.options) do
    if not key:match("^plugin%.") or hasBars then options[key] = value end
end
for key, value in pairs(personal.options or {}) do
    if state.options[key] == nil and (not key:match("^plugin%.") or hasBars) then options[key] = value end
end
-- Hyprland 0.57's KMS-only dmabuf format list makes Qt/GTK surfaces render
-- black or crash on virtio-gpu. Keep the default on physical GPUs, and allow
-- an explicit state or personal option to override this guest workaround.
-- PCI vendor IDs of the DRM devices. Real hardware never reports 0x1af4
-- (virtio) or 0x15ad (VMware), so these checks stay inactive there.
local gpuVendors = {}
for card = 0, 15 do
    local vendor = io.open("/sys/class/drm/card" .. card .. "/device/vendor", "r")
    if vendor then
        local id = vendor:read("*l")
        vendor:close()
        if id then gpuVendors[id] = true end
    end
end
if options["quirks.skip_non_kms_dmabuf_formats"] == nil and gpuVendors["0x1af4"] then
    options["quirks.skip_non_kms_dmabuf_formats"] = false
end
-- M3 boot-framebuffer sessions have no GPU render node. Avoid expensive
-- effects until the native display/GPU stack is available. Explicit user state
-- wins; a captured host.lua snapshot is not an explicit effects preference.
local modelFile = io.open("/proc/device-tree/model", "r")
local appleModel = ""
if modelFile then appleModel = modelFile:read("*a"); modelFile:close() end
-- Asahi trackpads: finger count chooses the click, instead of click location.
-- These are defaults; values selected in WinDoesNot settings take precedence.
local isApple = appleModel:match("^Apple ") ~= nil
if isApple then
    local trackpadDefaults = {
        ["input.touchpad.clickfinger_behavior"] = true,
        ["input.touchpad.tap_button_map"] = "lrm",
        ["input.touchpad.tap_to_click"] = true,
        ["input.touchpad.drag_3fg"] = 1,
        ["input.touchpad.natural_scroll"] = true,
        ["input.scroll_method"] = "2fg",
    }
    for key, value in pairs(trackpadDefaults) do
        if state.options[key] == nil then options[key] = value end
    end
end
local simpleFramebuffer = false
local hasRenderNode = false
for card = 0, 15 do
    local alias = io.open("/sys/class/drm/card" .. card .. "/device/modalias", "r")
    if alias then
        local value = alias:read("*a"); alias:close()
        if value and value:find("simple%-framebuffer") then simpleFramebuffer = true end
    end
    local render = io.open("/sys/class/drm/renderD" .. (128 + card) .. "/dev", "r")
    if render then hasRenderNode = true; render:close() end
end
if appleModel:match("^Apple ") and simpleFramebuffer and not hasRenderNode then
    for _, key in ipairs({"decoration.blur.enabled", "decoration.shadow.enabled",
                          "animations.enabled", "plugin.hyprbars.bar_blur"}) do
        if state.options[key] == nil and (not key:match("^plugin%.") or hasBars) then
            options[key] = false
        end
    end
end
hl.config(options)
if isolated then
    hl.config({debug = {enable_stdout_logs = true, disable_logs = false},
        xwayland = {enabled = false}, cursor = {no_hardware_cursors = true}})
end
for _, monitor in ipairs(state.monitors) do hl.monitor(monitor) end
if isolated then hl.monitor({output = "", mode = "1280x720@60", position = "0x0", scale = 1}) end
if isolated or primary ~= "" then
    hl.workspace_rule({workspace = "1", monitor = isolated and "WAYLAND-1" or primary, default = true})
end
for _, device in ipairs(personal.devices or reference.devices) do hl.device(device) end
for _, gesture in ipairs(reference.gestures) do hl.gesture(gesture) end
if isApple then
    -- Three fingers drag; four fingers navigate. Leave two-finger gestures
    -- to applications so scrolling, browser history and pinch zoom still work.
    hl.gesture({fingers = 3, direction = "horizontal", action = "unset"})
    hl.gesture({fingers = 4, direction = "horizontal", action = "workspace"})
    for _, spec in ipairs({
        {direction = "up", command = "windows"},
        {direction = "down", command = "app-windows"},
        {direction = "pinchin", command = "apps"},
        {direction = "pinchout", command = "desktop"},
    }) do
        local command = spec.command
        hl.gesture({fingers = 4, direction = spec.direction, action = function()
            hl.exec_cmd("windoesnot-gesture " .. command)
        end})
    end
end
for _, curve in ipairs(reference.curves) do hl.curve(curve[1], curve[2]) end
for _, animation in ipairs(reference.animations) do hl.animation(animation) end

-- Optional floating mode precedes per-window rules, as in the old config.
if state.window_mode == "floating" then
    hl.window_rule({name = "user-floating", match = {class = ".*"}, float = true})
    hl.window_rule({name = "user-floating-center", match = {class = ".*", title = "negative:^quickshell-.*$"}, center = true})
end
for _, rule in ipairs(reference.rules) do
    local copy = {}
    for key, value in pairs(rule) do
        if key ~= "hyprbars:no_bar" or hasBars then
            if value == "__primary__" then value = primary ~= "" and primary or nil end
            copy[key] = value
        end
    end
    for key, value in pairs(personal.rules and personal.rules[rule.name] or {}) do copy[key] = value end
    for key, value in pairs(state.rules[rule.name] or {}) do copy[key] = value end
    for key, value in pairs(geometry.rules[rule.name] or {}) do copy[key] = value end
    -- Hyprland's center effect clears the move effect even when center=false.
    -- Lua table iteration order is unspecified: never emit both in one rule.
    if copy.move ~= nil then copy.center = nil end
    hl.window_rule(copy)
end
for _, rule in ipairs(reference.layers) do hl.layer_rule(rule) end
if hasBars then
    for _, button in ipairs(state.buttons) do hl.plugin.hyprbars.add_button(button) end
end
dofile(root .. "bindings.lua")

-- The verification entry point makes no external calls. Isolated compositor
-- tests load real plugins and dispatchers but never start the user's desktop.
if not verify and not isolated then
    hl.env("WINDOESNOT_PLATFORM", isApple and "asahi" or "generic")
    hl.env("PATH", os.getenv("HOME") .. "/.local/bin:" .. (os.getenv("PATH") or "/usr/local/bin:/usr/bin"))
    -- VMware guests (vmwgfx): the compositor cannot import GPU dmabufs, so
    -- every GPU client dies on wl_surface.attach and the desktop stays black
    -- (aquamarine #360, Hyprland #16175). Mesa software rendering is the
    -- workaround reported to work (Omarchy #8113). Only with VMware's vendor ID.
    if gpuVendors["0x15ad"] then hl.env("LIBGL_ALWAYS_SOFTWARE", "1") end
    for _, env in ipairs(reference.env) do hl.env(env[1], env[2]) end
    for _, env in ipairs(personal.env or {}) do hl.env(env[1], env[2]) end
    for _, permission in ipairs(reference.permissions) do hl.permission(table.unpack(permission)) end
    hl.on("hyprland.start", function()
        for _, command in ipairs(reference.autostart) do hl.exec_cmd(command) end
        for _, command in ipairs(personal.autostart or {}) do hl.exec_cmd(command) end
    end)
end
_G.benni_lua_candidate = true
