/* src/input.c - Keyboard Input Implementation */
#define _POSIX_C_SOURCE 200809L

#include "input.h"
#include "hyprland.h"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/mman.h>
#include <unistd.h>
#include <xkbcommon/xkbcommon.h>

#define LOG(fmt, ...) fprintf(stderr, "[Input] " fmt "\n", ##__VA_ARGS__)

extern int output_scale;

static struct xkb_context *xkb_ctx = NULL;
static struct xkb_keymap *xkb_keymap = NULL;
static struct xkb_state *xkb_st = NULL;

#define MAX_DISMISS_MODS 8
static const char *dismiss_mod_names[MAX_DISMISS_MODS] = {"Mod1"};
static int dismiss_mod_count = 1;
static bool mod_was_held = false;
static bool ignore_first_release = true;
static bool toggle_mode = false;
static DismissType dismiss_type = DISMISS_TYPE_MODIFIER;
static xkb_keysym_t dismiss_keysym = XKB_KEY_NoSymbol;
static bool enter_primed_modifier = false;

alt_release_callback_t on_alt_release = NULL;
alt_release_callback_t on_escape = NULL;
static AppState *app_state = NULL;

/* Forward declaration: used by keyboard_enter before definition */
static bool any_dismiss_mod_held(void);

/* Classify a dismiss key name.
 * Returns true if it's a standard XKB modifier (sets *out_xkb to the XKB name).
 * Returns false if it's a regular key (sets *out_sym via xkb_keysym_from_name).
 * Falls back to Mod1 (Alt) if the name is completely unrecognized. */
static bool classify_dismiss_key(const char *name,
                                  const char **out_xkb,
                                  xkb_keysym_t *out_sym) {
  *out_xkb = NULL;
  *out_sym = XKB_KEY_NoSymbol;

  if (!name)
    return true;

  /* Standard modifier names → DISMISS_TYPE_MODIFIER */
  if (strcasecmp(name, "alt") == 0 || strcasecmp(name, "mod1") == 0) {
    *out_xkb = "Mod1"; return true;
  }
  if (strcasecmp(name, "super") == 0 || strcasecmp(name, "mod4") == 0 ||
      strcasecmp(name, "logo") == 0) {
    *out_xkb = "Mod4"; return true;
  }
  if (strcasecmp(name, "shift") == 0) {
    *out_xkb = "Shift"; return true;
  }
  if (strcasecmp(name, "control") == 0 || strcasecmp(name, "ctrl") == 0) {
    *out_xkb = "Control"; return true;
  }
  if (strcasecmp(name, "mod2") == 0) { *out_xkb = "Mod2"; return true; }
  if (strcasecmp(name, "mod3") == 0) { *out_xkb = "Mod3"; return true; }
  if (strcasecmp(name, "mod5") == 0) { *out_xkb = "Mod5"; return true; }

  /* Not a standard modifier — try resolving as a keysym name.
   * This handles "space", "2", "f", "Return", etc. */
  xkb_keysym_t sym = xkb_keysym_from_name(name, XKB_KEYSYM_CASE_INSENSITIVE);
  if (sym != XKB_KEY_NoSymbol) {
    *out_sym = sym;
    return false;
  }

  /* Truly unrecognized: warn and fall back to Alt */
  LOG("WARNING: Unknown dismiss key '%s', falling back to Alt (Mod1)", name);
  *out_xkb = "Mod1";
  return true;
}

void input_set_dismiss_modifier(const char *mod) {
  static char storage[MAX_DISMISS_MODS][16];
  dismiss_mod_count = 0;
  dismiss_type = DISMISS_TYPE_MODIFIER;
  dismiss_keysym = XKB_KEY_NoSymbol;

  if (!mod || !*mod) {
    strncpy(storage[0], "Mod1", 15);
    storage[0][15] = '\0';
    dismiss_mod_names[0] = storage[0];
    dismiss_mod_count = 1;
    return;
  }

  char buf[256];
  strncpy(buf, mod, sizeof(buf) - 1);
  buf[sizeof(buf) - 1] = '\0';

  char *p = buf;
  bool first_token = true;
  while (p && dismiss_mod_count < MAX_DISMISS_MODS) {
    while (*p == ' ' || *p == ',')
      p++;
    if (!*p)
      break;
    char *end = p;
    while (*end && *end != ',' && *end != ' ')
      end++;
    if (*end)
      *end++ = '\0';

    const char *xkb_name = NULL;
    xkb_keysym_t sym = XKB_KEY_NoSymbol;
    bool is_modifier = classify_dismiss_key(p, &xkb_name, &sym);

    if (first_token && !is_modifier) {
      /* First token is a non-modifier key — switch to keycode tracking */
      dismiss_type = DISMISS_TYPE_KEYCODE;
      dismiss_keysym = sym;
      dismiss_mod_count = 0;
      LOG("Dismiss key: '%s' (keysym 0x%x, keycode tracking)", p, sym);
      return;
    }

    if (is_modifier && xkb_name) {
      snprintf(storage[dismiss_mod_count], sizeof(storage[0]), "%.15s",
               xkb_name);
      dismiss_mod_names[dismiss_mod_count] = storage[dismiss_mod_count];
      dismiss_mod_count++;
    }

    first_token = false;
    p = end;
  }

  if (dismiss_mod_count == 0) {
    strncpy(storage[0], "Mod1", 15);
    storage[0][15] = '\0';
    dismiss_mod_names[0] = storage[0];
    dismiss_mod_count = 1;
  }
  LOG("Dismiss modifier: %s (%d mods, modifier tracking)", mod,
      dismiss_mod_count);
}

void input_set_toggle_mode(bool enabled) {
  toggle_mode = enabled;
}

void input_reset_alt_state(void) {
  enter_primed_modifier = false;
  if (toggle_mode) {
    /* TOGGLE mode: no modifier is held, so do not arm the dismiss mechanism.
     * The switcher will only close via Enter, Escape, or a second TOGGLE. */
    mod_was_held = false;
    ignore_first_release = false;
    LOG("Modifier state reset (toggle mode - dismiss on release disabled)");
  } else {
    /* NEXT/PREV mode: modifier IS held, arm the standard dismiss-on-release. */
    mod_was_held = true;
    ignore_first_release = true;
    LOG("Modifier state reset");
  }
}

static void keyboard_keymap(void *data, struct wl_keyboard *keyboard,
                            uint32_t format, int fd, uint32_t size) {
  (void)keyboard;
  (void)data;
  if (format != WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1) {
    close(fd);
    return;
  }

  char *map = mmap(NULL, size, PROT_READ, MAP_PRIVATE, fd, 0);
  if (map == MAP_FAILED) {
    close(fd);
    return;
  }

  if (!xkb_ctx)
    xkb_ctx = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
  if (!xkb_ctx) {
    munmap(map, size);
    close(fd);
    return;
  }

  if (xkb_st) {
    xkb_state_unref(xkb_st);
    xkb_st = NULL;
  }
  if (xkb_keymap) {
    xkb_keymap_unref(xkb_keymap);
    xkb_keymap = NULL;
  }

  xkb_keymap = xkb_keymap_new_from_string(
      xkb_ctx, map, XKB_KEYMAP_FORMAT_TEXT_V1, XKB_KEYMAP_COMPILE_NO_FLAGS);
  munmap(map, size);
  close(fd);

  if (xkb_keymap)
    xkb_st = xkb_state_new(xkb_keymap);
}

static void keyboard_enter(void *data, struct wl_keyboard *keyboard,
                           uint32_t serial, struct wl_surface *surface,
                           struct wl_array *keys) {
  (void)keyboard;
  (void)serial;
  (void)surface;
  app_state = (AppState *)data;

  if (!xkb_st || !keys)
    return;

  /* Prime XKB state with currently-held keys.
   * This fixes the Wayland race condition where keyboard_modifiers
   * arrives before the compositor has reported the full modifier state.
   * By feeding the held keycodes into xkb_state here, the modifier
   * bitmask will be correct when keyboard_modifiers fires next. */
  uint32_t *key;
  wl_array_for_each(key, keys) {
    xkb_state_update_key(xkb_st, *key + 8, XKB_KEY_DOWN);
  }

  /* For DISMISS_TYPE_MODIFIER: check if the dismiss modifier is active
   * after priming. This flag is used by keyboard_modifiers to resolve
   * the race where depressed=0 arrives despite the modifier being held. */
  if (dismiss_type == DISMISS_TYPE_MODIFIER && !toggle_mode) {
    if (any_dismiss_mod_held()) {
      enter_primed_modifier = true;
      LOG("Dismiss modifier confirmed in keyboard_enter");
    } else if (keys->size == 0) {
      /* Rapid alt-tab: the user released ALL keys (including the dismiss
       * modifier) before the compositor granted us keyboard focus.
       * With EXCLUSIVE interactivity, focus is guaranteed but may still
       * arrive after a fast Alt+Tab release. Auto-dismiss immediately
       * rather than waiting for a keyboard_modifiers event that would
       * confirm the empty state — the key_up was already lost. */
      LOG("Rapid alt-tab: no keys held at keyboard_enter, auto-dismissing");
      if (on_alt_release)
        on_alt_release();
      return;
    }
  }

  /* For DISMISS_TYPE_KEYCODE: check if the target key is already
   * in the pressed-keys array from this very first frame. */
  if (dismiss_type == DISMISS_TYPE_KEYCODE &&
      dismiss_keysym != XKB_KEY_NoSymbol) {
    bool found = false;
    wl_array_for_each(key, keys) {
      xkb_keysym_t sym = xkb_state_key_get_one_sym(xkb_st, *key + 8);
      if (sym == dismiss_keysym) {
        mod_was_held = true;
        found = true;
        LOG("Dismiss key primed from keyboard_enter");
        break;
      }
    }
    /* If the dismiss key is NOT held but other keys ARE held (real keybind),
     * and we're not in toggle mode: config mismatch — show error banner.
     * e.g. bind is ALT+Tab but --mod SPACE was specified. */
    if (!found && !toggle_mode && app_state) {
      uint32_t mods_depressed =
          xkb_state_serialize_mods(xkb_st, XKB_STATE_MODS_DEPRESSED);
      if (mods_depressed != 0) {
        /* A modifier IS held but it's not our dismiss key → real mismatch */
        mod_was_held = false;
        free(app_state->error_message);
        app_state->error_message =
            strdup("CONFIG ERROR: Dismiss key not held.\n"
                   "Ensure --mod flag matches your keybind.");
        app_state->needs_render = true;
        LOG("ERROR: Dismiss key not held (depressed=0x%x) — switcher disarmed",
            mods_depressed);
      } else if (keys->size == 0) {
        /* No keys and no modifiers held → rapid tap, auto-dismiss */
        if (on_alt_release)
          on_alt_release();
      }
      /* keys->size > 0 && depressed == 0: non-modifier keys held without
       * our dismiss key — unusual but harmless; let keyboard_key handle it */
    }
  }

  LOG("keyboard_enter: primed %zu held keys",
      keys->size / sizeof(uint32_t));
}

static void keyboard_leave(void *data, struct wl_keyboard *keyboard,
                           uint32_t serial, struct wl_surface *surface) {
  (void)data;
  (void)keyboard;
  (void)serial;
  (void)surface;
}

static void keyboard_key(void *data, struct wl_keyboard *keyboard,
                         uint32_t serial, uint32_t time, uint32_t key,
                         uint32_t state_w) {
  (void)keyboard;
  (void)serial;
  (void)time;
  app_state = (AppState *)data;

  if (!xkb_st || !app_state)
    return;

  xkb_keysym_t sym = xkb_state_key_get_one_sym(xkb_st, key + 8);

  /* --- Keycode-based dismiss: track press and release --- */
  if (dismiss_type == DISMISS_TYPE_KEYCODE &&
      dismiss_keysym != XKB_KEY_NoSymbol && sym == dismiss_keysym) {
    if (state_w == WL_KEYBOARD_KEY_STATE_PRESSED) {
      mod_was_held = true;
    } else if (state_w == WL_KEYBOARD_KEY_STATE_RELEASED) {
      if (mod_was_held && !toggle_mode) {
        mod_was_held = false;
        if (on_alt_release)
          on_alt_release();
      }
      return;
    }
  }

  /* Only process navigation on key press */
  if (state_w != WL_KEYBOARD_KEY_STATE_PRESSED)
    return;

  switch (sym) {
  case XKB_KEY_Tab:
  case XKB_KEY_ISO_Left_Tab:
    if (app_state->count > 0) {
      if (sym == XKB_KEY_ISO_Left_Tab) {
        app_state->selected_index--;
        if (app_state->selected_index < 0)
          app_state->selected_index = app_state->count - 1;
      } else {
        app_state->selected_index++;
        if (app_state->selected_index >= app_state->count)
          app_state->selected_index = 0;
      }
      app_state->needs_render = true;
    }
    break;

  case XKB_KEY_Left:
    if (app_state->count > 0) {
      app_state->selected_index--;
      if (app_state->selected_index < 0)
        app_state->selected_index = app_state->count - 1;
      app_state->needs_render = true;
    }
    break;

  case XKB_KEY_Right:
    if (app_state->count > 0) {
      app_state->selected_index++;
      if (app_state->selected_index >= app_state->count)
        app_state->selected_index = 0;
      app_state->needs_render = true;
    }
    break;

  case XKB_KEY_Up:
    if (app_state->count > 0 && app_state->cols > 0) {
      int next = app_state->selected_index - app_state->cols;
      if (next >= 0)
        app_state->selected_index = next;
      app_state->needs_render = true;
    }
    break;

  case XKB_KEY_Down:
    if (app_state->count > 0 && app_state->cols > 0) {
      int next = app_state->selected_index + app_state->cols;
      if (next < app_state->count)
        app_state->selected_index = next;
      app_state->needs_render = true;
    }
    break;

  case XKB_KEY_Escape:
    if (on_escape)
      on_escape();
    else if (on_alt_release) {
      app_state->selected_index = 0;
      on_alt_release();
    }
    break;

  case XKB_KEY_Return:
  case XKB_KEY_KP_Enter:
    if (app_state->count > 0 && app_state->selected_index >= 0 &&
        app_state->selected_index < app_state->count) {
      if (on_alt_release)
        on_alt_release();
    }
    break;
  }
}

static bool any_dismiss_mod_held(void) {
  for (int i = 0; i < dismiss_mod_count; i++) {
    if (xkb_state_mod_name_is_active(xkb_st, dismiss_mod_names[i],
                                     XKB_STATE_MODS_EFFECTIVE))
      return true;
  }
  return false;
}

static void keyboard_modifiers(void *data, struct wl_keyboard *keyboard,
                               uint32_t serial, uint32_t depressed,
                               uint32_t latched, uint32_t locked,
                               uint32_t group) {
  (void)keyboard;
  (void)serial;
  app_state = (AppState *)data;

  if (!xkb_st)
    return;
  xkb_state_update_mask(xkb_st, depressed, latched, locked, 0, 0, group);

  /* Keycode-based dismiss is handled entirely in keyboard_key;
   * skip all modifier-based dismiss logic. */
  if (dismiss_type == DISMISS_TYPE_KEYCODE)
    return;

  bool any_held_now = any_dismiss_mod_held();

  /* Toggle mode: modifier release should never dismiss the switcher.
   * Still track state so we don't carry stale values into the next session. */
  if (toggle_mode) {
    mod_was_held = any_held_now;
    return;
  }

  if (ignore_first_release) {
    ignore_first_release = false;
    if (any_held_now) {
      /* Scenario A (Normal): User is still holding the modifier.
       * We safely clear the flag and wait for the actual physical release. */
      mod_was_held = true;
      enter_primed_modifier = false;
    } else if (enter_primed_modifier) {
      /* Race condition resolved: keyboard_enter confirmed the modifier
       * is physically held, but this modifiers event reports depressed=0.
       * Trust the enter-based priming and wait for the real release. */
      mod_was_held = true;
      enter_primed_modifier = false;
      LOG("Modifier race resolved via keyboard_enter priming");
    } else {
      /* Modifier is NOT held and NOT primed from keyboard_enter.
       * Two sub-scenarios:
       *   B1 — Rapid Tap (depressed == 0):
       *         User released ALL modifiers before we processed the event.
       *         No keys are physically down → auto-dismiss immediately.
       *   B2 — Config Mismatch (depressed != 0):
       *         A DIFFERENT modifier is currently depressed (e.g. Super
       *         instead of Alt).  This is a genuine keybind mismatch.
       *         Show error banner and disarm. */
      mod_was_held = false;

      /* Check if a real (non-"none") modifier was configured */
      bool has_real_mod = (dismiss_mod_count > 0 &&
                           strcmp(dismiss_mod_names[0], "none") != 0);

      if (!toggle_mode && has_real_mod && app_state) {
        if (depressed != 0) {
          /* B2: A modifier IS physically held, but it's NOT the configured
           * dismiss modifier → genuine config mismatch. */
          free(app_state->error_message);
          app_state->error_message =
              strdup("CONFIG ERROR: Modifier not held.\n"
                     "Ensure --mod flag matches your keybind.");
          app_state->needs_render = true;
          LOG("ERROR: Dismiss modifier not held (depressed=0x%x) — switcher "
              "disarmed", depressed);
        } else {
          /* B1: depressed == 0 → user released everything (rapid tap).
           * Auto-dismiss immediately. */
          if (on_alt_release)
            on_alt_release();
        }
      } else {
        /* No real modifier configured or toggle mode — dismiss immediately */
        if (on_alt_release)
          on_alt_release();
      }
    }
    return;
  }

  if (mod_was_held && !any_held_now) {
    if (on_alt_release)
      on_alt_release();
  }
  mod_was_held = any_held_now;
}

static void keyboard_repeat_info(void *data, struct wl_keyboard *keyboard,
                                 int32_t rate, int32_t delay) {
  (void)data;
  (void)keyboard;
  (void)rate;
  (void)delay;
}

static const struct wl_keyboard_listener keyboard_listener = {
    .keymap = keyboard_keymap,
    .enter = keyboard_enter,
    .leave = keyboard_leave,
    .key = keyboard_key,
    .modifiers = keyboard_modifiers,
    .repeat_info = keyboard_repeat_info,
};

const struct wl_keyboard_listener *get_keyboard_listener(void) {
  return &keyboard_listener;
}

void input_cleanup(void) {
  if (xkb_st) {
    xkb_state_unref(xkb_st);
    xkb_st = NULL;
  }
  if (xkb_keymap) {
    xkb_keymap_unref(xkb_keymap);
    xkb_keymap = NULL;
  }
  if (xkb_ctx) {
    xkb_context_unref(xkb_ctx);
    xkb_ctx = NULL;
  }
}
