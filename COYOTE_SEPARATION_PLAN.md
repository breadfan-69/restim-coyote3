# Coyote + UI Mod Separation Plan

**Goal:** Cleanly separate our Coyote device support and UI upgrades from the upstream
diglet48/restim codebase so we can rebase onto new restim releases without merge hell.

---

## 1. The Problem

Every time diglet48 pushes a new restim version we hit merge conflicts because our Coyote
mods are woven into shared files (`mainwindow.py`, `algorithm_factory.py`, `settings.py`,
`enums.py`, `main_window_ui.py`, etc.). We lose work, waste time resolving conflicts, and
risk regressions.

---

## 2. Inventory of Our Changes

### 2A. **Pure Coyote Files (NEW — no upstream counterpart)**

These are 100% ours. Zero conflict risk. Just drop them on top.

| File / Directory | Purpose |
|---|---|
| `device/coyote/` (entire directory) | BLE device, algorithm, pulse gen, channel controller, state, types, constants, config, common |
| `qt_ui/coyote_settings_widget.py` | Coyote tab UI (930 lines) |
| `qt_ui/device_wizard/coyote_waveform_select.py` | Wizard page for Coyote waveform choice |
| `qt_ui/device_wizard/coyote_waveform_select_ui.py` | Auto-generated UI for above |
| `designer/device_wizard/coyote_waveform_select.ui` | Qt Designer source |
| `resources/coyote.ico` | Coyote icon |
| `resources/icons/coyote.png` | Coyote icon (PNG) |

### 2B. **Modified Upstream Files (merge conflict risk)**

| File | What We Changed |
|---|---|
| **`qt_ui/mainwindow.py`** | ~80 Coyote references: imports, `tab_coyote` init, `coyote_mode_label` in status bar, device start/stop/switch logic, funscript pulse_frequency gating, output_device CoyoteDevice checks. Also: `_load_icon_theme()`, `restim_rc` import, icon theme switching for our UI mods. |
| **`qt_ui/algorithm_factory.py`** | Added `create_coyote_two_channel()`, `create_coyote_diglet()`, Coyote imports, `CoyoteAlgorithm` return type, pulse-frequency axis getters. |
| **`qt_ui/main_window_ui.py`** | Added `CoyoteSettingsWidget` import, `tab_coyote` + `tab_coyote_calibration` tab creation, tab text labels. |
| **`qt_ui/settings.py`** | ~25 new `coyote_*` settings, `DictSetting` class, `pattern_enabled`, `dark_mode_enabled`, `icon_theme` settings. |
| **`qt_ui/device_wizard/enums.py`** | Added `COYOTE_THREE_PHASE = 8`, `COYOTE_TWO_CHANNEL = 9` to `DeviceType`. |
| **`qt_ui/device_wizard/wizard.py`** | Coyote wizard page import, `Page_coyote_waveform` enum, coyote_radio checks, Coyote device config creation. |
| **`qt_ui/device_wizard/type_select.py`** | `coyote_radio` default selection, toggled signal, isComplete check. |
| **`qt_ui/tcode_command_router.py`** | `pulse_frequency` axis, `set_pulse_frequency_axis()`, `set_pulse_frequency_limits()` methods. |
| **`qt_ui/axis_controller.py`** | Added `.axis` property, external-value tracking, timeout logic. |
| **`stim_math/audio_gen/params.py`** | Added `CoyoteChannelParams`, `CoyoteAlgorithmParams` dataclasses. |
| **`qt_ui/theme.py`** | NEW file — `apply_theme()`, `toggle_dark_mode()`, `update_graphics_views()`. |
| **`qt_ui/resources.py`** / **`restim_rc.py`** | Icon/resource registration changes. |

### 2C. **UI-Only Upgrades (non-Coyote, also ours)**

| Feature | Files |
|---|---|
| Dark mode / theme toggle | `qt_ui/theme.py`, `qt_ui/settings.py` (dark_mode_enabled, icon_theme) |
| Icon theme system | `mainwindow.py` (`_load_icon_theme`), icon .png/.ico files |
| Pattern preferences | `qt_ui/settings.py` (DictSetting, pattern_enabled) |

---

## 3. Separation Strategy: Plugin/Overlay Architecture

### Approach: **Patch Layer with Hook Points**

Instead of forking restim, we maintain a **thin overlay** that patches the upstream code
at well-defined hook points. This keeps our mods in separate files and makes rebasing
trivial.

### Step-by-Step Plan

#### Phase 1: Create `coyote_plugin/` Package (Low Risk)

Create a self-contained package that holds ALL Coyote logic:

```
coyote_plugin/
    __init__.py              # register_coyote(mainwindow) entry point
    device/                  # move device/coyote/* here
        __init__.py
        algorithm.py
        channel_controller.py
        channel_state.py
        common.py
        config.py
        constants.py
        device.py
        pulse_generator.py
        types.py
    ui/
        __init__.py
        coyote_settings_widget.py
        coyote_waveform_select.py
        coyote_waveform_select_ui.py
    params.py                # CoyoteChannelParams, CoyoteAlgorithmParams
    settings.py              # all coyote_* settings
    algorithm_factory.py     # create_coyote_two_channel, create_coyote_diglet
    wizard_integration.py    # wizard page registration, enums extension
```

#### Phase 2: Add Hook Points to Upstream Files (Small, Stable Diffs)

Modify upstream files minimally with **registration hooks** that our plugin calls into.
These are small, forward-compatible additions that rarely change.

**`qt_ui/device_wizard/enums.py`** — register new device types:
```python
# AT END OF FILE — plugin extension point
_extra_device_types = {}
def register_device_type(name, value):
    _extra_device_types[name] = value
```

**`qt_ui/algorithm_factory.py`** — plugin algorithm dispatch:
```python
# AT END of create_algorithm()
_plugin_factories = {}
def register_algorithm_factory(device_type, factory_fn):
    _plugin_factories[device_type] = factory_fn
```

**`qt_ui/mainwindow.py`** — tab registration + device lifecycle hooks:
```python
_device_plugins = []
def register_device_plugin(plugin):
    """Plugin implements: create_tabs(), on_device_changed(), on_start(), on_stop()"""
    _device_plugins.append(plugin)
```

**`qt_ui/settings.py`** — no hook needed, just append coyote settings from plugin.

#### Phase 3: Refactor mainwindow.py Coyote Code Into Plugin

Move all `coyote`-related logic from `mainwindow.py` into
`coyote_plugin/__init__.py::register_coyote()` which:

1. Creates `tab_coyote` and `tab_coyote_calibration`
2. Registers them with the tab widget
3. Hooks into device-changed signal for show/hide logic
4. Handles CoyoteDevice creation/teardown
5. Manages `coyote_mode_label`
6. Wires up pulse_frequency to tcode_command_router

#### Phase 4: Separate UI Upgrades Into `ui_mods/` Package

```
ui_mods/
    __init__.py
    theme.py                # existing qt_ui/theme.py
    icon_loader.py          # _load_icon_theme logic from mainwindow
    settings.py             # dark_mode_enabled, icon_theme, pattern_enabled, DictSetting
```

---

## 4. Resulting Upstream Diff (What We'd Patch On Each Rebase)

After full separation, our diff against upstream would be **~50 lines total** across:

| File | Lines Changed | Change |
|---|---|---|
| `qt_ui/mainwindow.py` | ~10 | Import + call `register_coyote()` and `register_ui_mods()` at init |
| `qt_ui/algorithm_factory.py` | ~8 | Plugin dispatch in `create_algorithm()` |
| `qt_ui/device_wizard/enums.py` | ~4 | Two enum values OR dynamic registration |
| `qt_ui/device_wizard/wizard.py` | ~8 | Plugin page registration |
| `qt_ui/device_wizard/type_select.py` | ~3 | Extra radio button from plugin |
| `qt_ui/main_window_ui.py` | ~5 | Tab creation hooks |
| `qt_ui/settings.py` | ~2 | Import coyote_plugin.settings |
| `stim_math/audio_gen/params.py` | ~4 | Import CoyoteAlgorithmParams from plugin |
| `qt_ui/tcode_command_router.py` | ~5 | pulse_frequency hook |

**Total: ~50 lines of small, stable patches** vs. the current ~800+ lines scattered
across many files.

---

## 5. Implementation Priority & Status

| Priority | Task | Effort | Impact | Status |
|---|---|---|---|---|
| **P0** | Move `device/coyote/` into `coyote_plugin/device/` | Low | Isolates core device code | **DONE** ✅ |
| **P0** | Move `CoyoteChannelParams`/`CoyoteAlgorithmParams` into plugin | Low | Removes stim_math edit | **DONE** ✅ |
| **P1** | Extract coyote settings from `qt_ui/settings.py` | Low | Removes ~25 lines from upstream | **DONE** ✅ |
| **P1** | Extract `coyote_settings_widget.py` into plugin | Low | Already self-contained | Skipped (no conflict risk — new file) |
| **P2** | Create algorithm factory hooks | Medium | Removes algorithm_factory.py edits | **DONE** ✅ |
| **P2** | Create mainwindow device plugin hooks | Medium | Biggest win — removes most mainwindow edits | **DONE** ✅ |
| **P3** | Extract wizard integration | Medium | Removes wizard.py, type_select.py, enums.py edits | **DONE** ✅ |
| **P3** | Extract UI mods (theme, icons) | Low | Separates non-Coyote improvements too | **DONE** ✅ |

### Phase 1 Completion Summary

**What was done:**
- Created `coyote_plugin/` package with `device/`, `params.py`, `settings.py`
- All 9 `device/coyote/*.py` files now have backward-compatibility shims that re-export from `coyote_plugin.device.*`
- `CoyoteChannelParams` and `CoyoteAlgorithmParams` moved to `coyote_plugin/params.py`
- All 22 coyote settings moved to `coyote_plugin/settings.py`
- `qt_ui/settings.py` uses module `__getattr__` for lazy re-export (avoids circular import)
- `stim_math/audio_gen/params.py` cleaned: coyote classes removed, no re-export (consumers import directly)
- `qt_ui/algorithm_factory.py` updated to import from `coyote_plugin.params`

**Files created:**
- `coyote_plugin/__init__.py`
- `coyote_plugin/device/__init__.py`
- `coyote_plugin/device/algorithm.py`
- `coyote_plugin/device/channel_controller.py`
- `coyote_plugin/device/channel_state.py`
- `coyote_plugin/device/common.py`
- `coyote_plugin/device/config.py`
- `coyote_plugin/device/constants.py`
- `coyote_plugin/device/device.py`
- `coyote_plugin/device/pulse_generator.py`
- `coyote_plugin/device/types.py`
- `coyote_plugin/params.py`
- `coyote_plugin/settings.py`

**Files modified (minimal upstream delta):**
- `device/coyote/*.py` → replaced with thin re-export shims
- `stim_math/audio_gen/params.py` → removed CoyoteChannelParams/CoyoteAlgorithmParams (clean upstream file)
- `qt_ui/settings.py` → removed coyote settings, added `__getattr__` lazy re-export (~8 lines)
- `qt_ui/algorithm_factory.py` → added `from coyote_plugin.params import ...` (1 line)

**App startup verified:** `Window()` instantiation succeeds with all imports resolved.

### Phase 2 Completion Summary

**What was done:**
- Added algorithm factory plugin dispatch with `register_algorithm_factory()` and `_plugin_factories`
- Moved Coyote algorithm creation from `qt_ui/algorithm_factory.py` into `coyote_plugin/algorithm_factory.py`
- Added mainwindow plugin hook surface (`register_device_plugin`, runtime plugin callbacks)
- Added Coyote runtime plugin (`coyote_plugin/runtime_plugin.py`) for:
    - Coyote tab/show-hide behavior
    - Coyote mode label lifecycle
    - Coyote device creation/disconnect/start/stop handling
    - TCode pulse-frequency axis routing and funscript pulse-frequency gating

**Files created:**
- `coyote_plugin/algorithm_factory.py`
- `coyote_plugin/runtime_plugin.py`

**Files modified:**
- `qt_ui/algorithm_factory.py`
- `qt_ui/mainwindow.py`
- `coyote_plugin/__init__.py`

### Phase 3 Completion Summary

**What was done:**
- Added wizard plugin hook API to `qt_ui/device_wizard/wizard.py`
- Moved Coyote wizard flow/config handling into `coyote_plugin/wizard_integration.py`
- Kept `type_select.py` generic (no required hardcoded Coyote branch)
- Added device-wizard enum extension hooks (`register_device_type`, `get_registered_device_types`)

**Files created:**
- `coyote_plugin/wizard_integration.py`

**Files modified:**
- `qt_ui/device_wizard/wizard.py`
- `qt_ui/device_wizard/type_select.py`
- `qt_ui/device_wizard/enums.py`

### Phase 4 Completion Summary

**What was done:**
- Created `ui_mods/` overlay package for non-Coyote UI upgrades
- Moved icon loading/taskbar icon update implementation into `ui_mods/icon_loader.py`
- Moved UI-mod setting declarations (`pattern_enabled`, `dark_mode_enabled`, `icon_theme`, `DictSetting`) into `ui_mods/settings.py`
- Added `ui_mods/theme.py` bridge and switched mainwindow to import theme APIs from `ui_mods`
- Updated `qt_ui/settings.py` to lazily re-export both coyote and ui-mod settings via `__getattr__`

**Files created:**
- `ui_mods/__init__.py`
- `ui_mods/icon_loader.py`
- `ui_mods/settings.py`
- `ui_mods/theme.py`

**Files modified:**
- `qt_ui/mainwindow.py`
- `qt_ui/settings.py`

---

## 6. Rebase Workflow After Separation

```
1. git fetch upstream
2. git checkout our-main
3. git rebase upstream/master
   - Only ~50 lines of hooks to resolve (if any)
4. Coyote plugin + UI mods are untouched (separate directories)
5. Run tests
6. Done
```

---

## 6A. Post-Refactor Diff Snapshot (Current Working Tree)

Measured on **2026-03-03** from current `git diff --numstat`.

### Core upstream-touch files (hook layer)

| File | + | - | Notes |
|---|---:|---:|---|
| `qt_ui/mainwindow.py` | 58 | 183 | Coyote lifecycle moved to runtime plugin hooks; icon/theme delegated to `ui_mods` |
| `qt_ui/algorithm_factory.py` | 23 | 117 | Coyote creation moved to plugin factory registration |
| `qt_ui/device_wizard/wizard.py` | 52 | 28 | Coyote flow delegated to wizard plugin callbacks |
| `qt_ui/device_wizard/type_select.py` | 13 | 12 | Generic device-radio handling (no hard Coyote dependency) |
| `qt_ui/device_wizard/enums.py` | 12 | 1 | Enum extension hooks added |
| `qt_ui/settings.py` | 28 | 55 | Coyote + UI-mod settings lazy re-export |

**Core total:** **+186 / -396** across **6 files** (net **-210** lines).

### Overlay/plugin files (our layer)

Primary new overlay files now carrying logic:

- `coyote_plugin/algorithm_factory.py`
- `coyote_plugin/runtime_plugin.py`
- `coyote_plugin/wizard_integration.py`
- `ui_mods/icon_loader.py`
- `ui_mods/settings.py`
- `ui_mods/theme.py`

### Remaining upstream-touch hotspots

Still likely to need small future hooking if you want to shrink conflict surface further:

- `qt_ui/main_window_ui.py` (Coyote tab creation is still a generated/core touchpoint)
- `qt_ui/tcode_command_router.py` (already extended for pulse-frequency axis behavior)
- `qt_ui/axis_controller.py` (external-control/timeout behavior changes)

---

## 7. Alternative: Simpler "Patch File" Approach

If the plugin architecture feels like too much refactoring upfront, a lighter option:

1. Keep all Coyote code in `device/coyote/` and `qt_ui/coyote_*` (as-is)
2. Maintain a **single patch file** (`coyote_hooks.patch`) that contains all our edits
   to upstream files
3. On rebase: `git apply coyote_hooks.patch` and fix any failures
4. Regenerate patch: `git diff upstream/master -- qt_ui/mainwindow.py qt_ui/algorithm_factory.py ... > coyote_hooks.patch`

**Pros:** No restructuring needed now.
**Cons:** Patch may bitrot; still touching many files; conflicts still possible, just easier to see.

---

## 8. Recommendation

**Start with Phase 1 (move device/coyote into coyote_plugin/)** — this is zero-risk, takes
an hour, and immediately isolates the biggest chunk of code. Then do Phase 2-3 incrementally
as time allows. Each phase independently reduces merge pain.

The full plugin architecture (Phases 1-4) would shrink our upstream diff from **800+ lines
in 12+ files** down to **~50 lines in 9 files**, making rebases nearly automatic.

---

*Created: 2026-03-03*
*Based on analysis of current codebase vs. upstream diglet48/master*
