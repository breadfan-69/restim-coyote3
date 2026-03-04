"""
Coyote-specific settings extracted from qt_ui/settings.py.

All Setting instances use the same QSettings INI file via get_settings_instance().
"""
from qt_ui.settings import Setting


# Channel limits and balances
coyote_channel_a_limit = Setting("coyote/channel_a_limit", 200, int)
coyote_channel_b_limit = Setting("coyote/channel_b_limit", 200, int)
coyote_channel_a_freq_balance = Setting("coyote/channel_a_freq_balance", 160, int)
coyote_channel_b_freq_balance = Setting("coyote/channel_b_freq_balance", 160, int)
coyote_channel_a_intensity_balance = Setting("coyote/channel_a_intensity_balance", 0, int)
coyote_channel_b_intensity_balance = Setting("coyote/channel_b_intensity_balance", 0, int)

# Per-channel frequency & strength bounds
coyote_channel_a_strength_max = Setting("coyote/channel_a_strength_max", 75, int)
coyote_channel_a_freq_min = Setting("coyote/channel_a_freq_min", 4, int)
coyote_channel_a_freq_max = Setting("coyote/channel_a_freq_max", 100, int)
coyote_channel_b_strength_max = Setting("coyote/channel_b_strength_max", 75, int)
coyote_channel_b_freq_min = Setting("coyote/channel_b_freq_min", 4, int)
coyote_channel_b_freq_max = Setting("coyote/channel_b_freq_max", 100, int)

# Algorithm tuning
coyote_max_intensity_change_per_pulse = Setting("coyote/max_intensity_change_per_pulse", 1.0, float)

# Debug / graph
coyote_debug_logging = Setting("coyote/debug_logging", False, bool)
coyote_graph_window = Setting("coyote/graph_window", 3.0, float)

# Pulse timing / texture
coyote_queue_horizon_seconds = Setting("coyote/queue_horizon_seconds", 0.15, float)
coyote_packet_margin = Setting("coyote/packet_margin", 0.8, float)
coyote_texture_min_hz = Setting("coyote/texture_min_hz", 0.5, float)
coyote_texture_max_hz = Setting("coyote/texture_max_hz", 5.0, float)
coyote_texture_depth_fraction = Setting("coyote/texture_depth_fraction", 0.5, float)
coyote_jitter_limit_fraction = Setting("coyote/jitter_limit_fraction", 0.5, float)
coyote_residual_bound = Setting("coyote/residual_bound", 0.49, float)

# Remembered device address
coyote_last_device_address = Setting("coyote/last_device_address", "", str)
