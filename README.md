# Restim

Restim is a realtime e-stim signal generator for multi-electrode setups.
This is a fork of diglet48/restim with added features.
Coyote connection and visualizer based on code written by [voltmouse69.](https://github.com/voltmouse69/restim)
Refer to the [wiki](https://github.com/diglet48/restim/wiki) for help.

## Supported hardware

* Stereostim (three-phase only) and other audio-based devices (Mk312, 2B, ...)
* FOC-Stim
* NeoDK
* Coyote 3.0
  
## Main features

* Control e-stim signals with funscript or user interface.
* Synchronize e-stim with video or games.
* Calibrate signal for your preferred electrode configuration.
  
THIS VERSION ADDS:
* Coyote 3 support with Visualizer
    * Dynamic Pulse Script Mapping
    * Two-Channel and "Simulated" Three Phase Modes
* Dark Mode
* Funscript Sync Offset
* Selectable Icons for Multiple Instances (IYKYK)

## Installation

**Windows**: download the latest release package: https://github.com/breadfan-69/restim-coyote3/releases

**Linux/mac**: make sure python 3.10 or newer is installed on your system.
Download the Restim source code, and execute `run.sh`

**Developers**: install PyCharm and python 3.10 or newer.
Open Settings, python interpreter, and configure a new venv.
Navigate to requirements.txt and install the dependencies. Then run restim.py.
