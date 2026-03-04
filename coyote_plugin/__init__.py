"""
Coyote Plugin for restim
=========================
Self-contained DG-LAB Coyote 3.0 device support.
All Coyote-specific code lives here so it can be cleanly overlaid
on top of any upstream restim release.
"""

__version__ = "1.0.0"


def register_coyote(mainwindow):
	try:
		from coyote_plugin.algorithm_factory import register_coyote_algorithm_factories
		from qt_ui.algorithm_factory import register_algorithm_factory
		register_coyote_algorithm_factories(register_algorithm_factory)
	except Exception:
		pass

	if hasattr(mainwindow, "register_runtime_device_plugin"):
		from coyote_plugin.runtime_plugin import CoyoteDevicePlugin
		mainwindow.register_runtime_device_plugin(CoyoteDevicePlugin())
