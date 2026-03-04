import json


class DictSetting:
    def __init__(self, key, default_value, setting_cls, get_settings_instance):
        self.key = key
        self.default_value = default_value
        self._setting_cls = setting_cls
        self._get_settings_instance = get_settings_instance
        self.cache = None

    def get(self):
        if self.cache is None:
            json_str = self._get_settings_instance().value(self.key, json.dumps(self.default_value), str)
            try:
                self.cache = json.loads(json_str) if json_str else self.default_value
            except (json.JSONDecodeError, TypeError):
                self.cache = self.default_value
        return self.cache

    def set(self, value):
        json_str = json.dumps(value)
        current_cache = self.cache if self.cache is not None else self.default_value
        if json_str != json.dumps(current_cache):
            self._get_settings_instance().setValue(self.key, json_str)
            self.cache = value
            self._get_settings_instance().sync()


def build_ui_mod_settings(setting_cls, get_settings_instance):
    pattern_enabled = DictSetting("patterns/enabled", {}, setting_cls, get_settings_instance)
    dark_mode_enabled = setting_cls('theme/dark_mode', True, bool)
    icon_theme = setting_cls('theme/icon_theme', 'cherries', str)
    return {
        'DictSetting': DictSetting,
        'pattern_enabled': pattern_enabled,
        'dark_mode_enabled': dark_mode_enabled,
        'icon_theme': icon_theme,
    }
