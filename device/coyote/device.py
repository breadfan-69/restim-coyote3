import asyncio
import concurrent.futures
import inspect
import logging
from typing import Any, Optional, cast
import time
import threading
import sys

from bleak import BleakClient, BleakScanner
from device.output_device import OutputDevice
import qt_ui.settings as ui_settings

from PySide6.QtCore import QObject, Signal
from device.coyote.constants import (
    LOG_PREFIX,
    MAIN_SERVICE_UUID,
    WRITE_CHAR_UUID,
    NOTIFY_CHAR_UUID,
    BATTERY_CHAR_UUID,
    CMD_B0,
    CMD_POWER_UPDATE,
    CMD_ACK,
    CMD_ACTIVE_POWER,
    INTERP_ABSOLUTE_SET,
    INTERP_NO_CHANGE,
    SEQUENCE_MODULO,
    B0_NO_PULSES_PAD_BYTES,
    PULSES_PER_PACKET,
    SCAN_RETRY_SECONDS,
)
from device.coyote.types import CoyoteParams, CoyotePulse, CoyotePulses, CoyoteStrengths, ConnectionStage
from device.coyote.algorithm import CoyoteAlgorithm, CoyoteDigletAlgorithm

logger = logging.getLogger('restim.coyote')

class CoyoteDevice(OutputDevice, QObject):
    parameters: CoyoteParams
    connection_status_changed = Signal(bool, str)  # Connected, Stage
    battery_level_changed = Signal(int)
    parameters_changed = Signal()
    power_levels_changed = Signal(CoyoteStrengths)
    pulse_sent = Signal(CoyotePulses)

    def __init__(self, device_name: str, parameters: CoyoteParams):
        OutputDevice.__init__(self)
        QObject.__init__(self)
        self.device_name = device_name
        self.client: Optional[BleakClient] = None
        self.algorithm: Optional[CoyoteAlgorithm] = None
        self.running = False
        self.connection_stage = ConnectionStage.DISCONNECTED
        self.strengths = CoyoteStrengths(channel_a=0, channel_b=0)
        self.battery_level = 100
        self.parameters = parameters
        self._event_loop = None
        self.sequence_number = 1
        self._had_successful_connection = False  # Track if we've ever connected before
        self._shutdown = False  # Flag to permanently stop the connection loop
        self._force_disconnect = False  # Flag for temporary disconnect (e.g., reset button)
        persisted_address = ui_settings.coyote_last_device_address.get()
        self._last_device_address: Optional[str] = (persisted_address.strip() if isinstance(persisted_address, str) else None) or None
        self._using_cached_address = False
        self._cached_connect_failure_count = 0
        self._cached_connect_failure_limit = 3
        self._skip_cached_reconnect_scans = 0
        self._next_scan_time = 0.0
        self._scan_attempt_counter = 0
        self._last_scan_elapsed = 0.0
        self._scan_failure_streak = 0
        self._connect_failure_streak = 0
        self._logged_first_send_payload = False
        self._first_active_power_seen: bool = False
        self._last_battery_poll: float = 0.0
        self._last_parameter_resend: float = 0.0
        
        # Start connection process
        self._start_connection_loop()

    def _start_connection_loop(self):
        """Start the connection process in a separate thread"""
        loop = asyncio.new_event_loop()
        self._event_loop = loop
        
        def run_loop():
            logger.info(f"{LOG_PREFIX} Starting asyncio loop thread")
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._connection_loop())
            
        threading.Thread(target=run_loop, daemon=True).start()

    async def _connection_loop(self):
        """Main connection loop that runs the state machine"""
        logger.info(f"{LOG_PREFIX} Starting connection loop")
        prev_stage = self.connection_stage
        
        while not self._shutdown:
            try:
                # Handle temporary disconnect (e.g., from reset button)
                if self._force_disconnect:
                    logger.info(f"{LOG_PREFIX} Force disconnect triggered")
                    self._force_disconnect = False
                    await self._disconnect_client()
                    self._scan_attempt_counter = 0
                    self._next_scan_time = 0.0
                    self._first_active_power_seen = False
                    self.connection_stage = ConnectionStage.DISCONNECTED
                    continue
                
                # Check if client is still connected
                if (self.connection_stage == ConnectionStage.CONNECTED and 
                    (not self.client or not self.client.is_connected)):
                    logger.warning(f"{LOG_PREFIX} Device disconnected unexpectedly")
                    await self._disconnect_client()
                    self._first_active_power_seen = False
                    self.connection_stage = ConnectionStage.DISCONNECTED
                    continue

                if self.connection_stage == ConnectionStage.DISCONNECTED:
                    logger.info(f"{LOG_PREFIX} Starting connection process")
                    self.connection_stage = ConnectionStage.SCANNING
                    
                elif self.connection_stage == ConnectionStage.SCANNING:
                    now = time.time()
                    if now < self._next_scan_time:
                        await asyncio.sleep(min(0.5, self._next_scan_time - now))
                        continue

                    if await self._scan_for_device():
                        self._scan_attempt_counter = 0
                        self._next_scan_time = 0.0
                        logger.info(f"{LOG_PREFIX} Device found, connecting...")
                        self.connection_stage = ConnectionStage.CONNECTING
                    else:
                        self._scan_attempt_counter += 1
                        retry_delay = min(4.0, max(2.0, SCAN_RETRY_SECONDS * 0.5))
                        self._next_scan_time = time.time() + retry_delay
                        logger.info(
                            f"{LOG_PREFIX} Device not found (attempt {self._scan_attempt_counter}); "
                            f"scan took {self._last_scan_elapsed:.1f}s; retrying in {retry_delay:.1f}s..."
                        )
                        
                elif self.connection_stage == ConnectionStage.CONNECTING:
                    try:
                        if not self.client:
                            logger.error(f"{LOG_PREFIX} No BLE client available during CONNECTING")
                            await self._recover_from_transient_failure("missing client")
                            continue

                        # Windows can need longer to establish GATT after scan discovery.
                        # Keep non-Windows tighter for responsiveness.
                        connect_timeout_seconds = 15.0 if sys.platform.startswith("win") else 8.0
                        logger.info(f"{LOG_PREFIX} Connect timeout configured to {connect_timeout_seconds:.1f}s")
                        await asyncio.wait_for(self.client.connect(), timeout=connect_timeout_seconds)
                        self._cached_connect_failure_count = 0
                        self._connect_failure_streak = 0
                        self._using_cached_address = False
                        logger.info(f"{LOG_PREFIX} Connected, discovering services...")
                        self.connection_stage = ConnectionStage.SERVICE_DISCOVERY
                    except asyncio.TimeoutError:
                        logger.error(f"{LOG_PREFIX} Connection timed out after {connect_timeout_seconds:.1f}s")
                        self._connect_failure_streak += 1
                        if self._using_cached_address and self._last_device_address:
                            self._cached_connect_failure_count += 1
                            self._skip_cached_reconnect_scans = max(self._skip_cached_reconnect_scans, 2)
                            if self._cached_connect_failure_count >= self._cached_connect_failure_limit:
                                logger.warning(
                                    f"{LOG_PREFIX} Cached address connect timed out "
                                    f"({self._cached_connect_failure_count}/{self._cached_connect_failure_limit}); "
                                    f"clearing cached address and forcing fresh discovery"
                                )
                                self._remember_device_address(None)
                            else:
                                logger.warning(
                                    f"{LOG_PREFIX} Cached address connect timed out "
                                    f"({self._cached_connect_failure_count}/{self._cached_connect_failure_limit}); "
                                    f"keeping cached address for fast retry"
                                )
                            self._using_cached_address = False
                        # After repeated timeouts, force the Windows BLE scanner refresh path
                        # on the next scan attempt - equivalent to a manual BT toggle
                        if sys.platform.startswith("win") and self._connect_failure_streak >= 2:
                            logger.warning(
                                f"{LOG_PREFIX} {self._connect_failure_streak} consecutive connect timeouts; "
                                f"forcing Windows BLE scanner refresh on next scan"
                            )
                            self._scan_failure_streak = max(self._scan_failure_streak, 2)
                        await self._recover_from_transient_failure("connect timeout", extra_delay=self._connect_failure_streak)
                    except Exception as e:
                        logger.error(f"{LOG_PREFIX} Connection failed: {e}")
                        self._connect_failure_streak += 1
                        if self._using_cached_address and self._last_device_address:
                            self._cached_connect_failure_count += 1
                            self._skip_cached_reconnect_scans = max(self._skip_cached_reconnect_scans, 2)
                            if self._cached_connect_failure_count >= self._cached_connect_failure_limit:
                                logger.warning(
                                    f"{LOG_PREFIX} Cached address connect failed {self._cached_connect_failure_count}x; "
                                    f"clearing cached address and forcing fresh discovery"
                                )
                                self._remember_device_address(None)
                            else:
                                logger.warning(
                                    f"{LOG_PREFIX} Cached address connect failed "
                                    f"({self._cached_connect_failure_count}/{self._cached_connect_failure_limit}); "
                                    f"keeping cached address for fast retry"
                                )
                            self._using_cached_address = False
                        if sys.platform.startswith("win") and self._connect_failure_streak >= 2:
                            logger.warning(
                                f"{LOG_PREFIX} {self._connect_failure_streak} consecutive connect failures; "
                                f"forcing Windows BLE scanner refresh on next scan"
                            )
                            self._scan_failure_streak = max(self._scan_failure_streak, 2)
                        await self._recover_from_transient_failure("connect failure", extra_delay=self._connect_failure_streak)
                        
                elif self.connection_stage == ConnectionStage.SERVICE_DISCOVERY:
                    try:
                        client = self.client
                        if not client or not client.is_connected:
                            logger.error(f"{LOG_PREFIX} Lost client before service discovery")
                            await self._recover_from_transient_failure("service discovery missing client")
                            continue

                        get_services = getattr(client, "get_services", None)
                        if callable(get_services):
                            services_result = get_services()
                            services = await services_result if inspect.isawaitable(services_result) else services_result
                            services_any = cast(Any, services)
                            service_count = len(list(services_any))
                        else:
                            services = getattr(client, "services", None)
                            service_count = len(list(services)) if services else 0

                        if service_count > 0:
                            logger.info(f"{LOG_PREFIX} Services discovered ({service_count}), waiting for characteristics to load...")
                            await asyncio.sleep(0.5)  # Wait for characteristics to fully load
                            logger.info(f"{LOG_PREFIX} Sending initial 0,0 before status subscribe...")
                            if await self._send_initial_power_zero():
                                self.connection_stage = ConnectionStage.STATUS_SUBSCRIBE
                            else:
                                logger.error(f"{LOG_PREFIX} Failed to send initial 0,0 before subscribe")
                                await self._recover_from_transient_failure("initial zero command failed")
                        else:
                            logger.error(f"{LOG_PREFIX} Service discovery failed")
                            await self._recover_from_transient_failure("service discovery failed")
                    except Exception as e:
                        logger.error(f"{LOG_PREFIX} Service discovery error: {e}")
                        await self._recover_from_transient_failure("service discovery error")
                        
                elif self.connection_stage == ConnectionStage.STATUS_SUBSCRIBE:
                    if await self._subscribe_to_notifications(NOTIFY_CHAR_UUID):
                        logger.info(f"{LOG_PREFIX} Status subscribed, syncing parameters...")
                        self.connection_stage = ConnectionStage.SYNC_PARAMETERS
                    else:
                        logger.error(f"{LOG_PREFIX} Status subscription failed")
                        await self._recover_from_transient_failure("status subscription failed")
                        
                elif self.connection_stage == ConnectionStage.SYNC_PARAMETERS:
                    if await self._send_parameters():
                        is_reconnection = self._had_successful_connection
                        if is_reconnection:
                            logger.info(f"{LOG_PREFIX} Parameters resent after reconnection (critical per BF command spec)")
                        else:
                            logger.info(f"{LOG_PREFIX} Parameters synced on initial connection")

                        self._had_successful_connection = True

                        # Try to read battery level immediately after connection
                        await self._read_battery_level()
                        # TODO: wait for ACK so we know device is ready
                        self.connection_stage = ConnectionStage.CONNECTED
                    else:
                        logger.error(f"{LOG_PREFIX} Parameter sync failed")
                        await self._recover_from_transient_failure("parameter sync failed")
                        
                elif self.connection_stage == ConnectionStage.CONNECTED:
                    # Maintain connection and resend parameters periodically
                    # This is critical per official API: BF command has no ACK and must be
                    # resent on every reconnection, and periodically to ensure parameters survive
                    # any device state resets
                    current_time = time.time()
                    if current_time - self._last_battery_poll >= 10:
                        await self._read_battery_level()
                        self._last_battery_poll = current_time
                    
                    if current_time - self._last_parameter_resend >= 5:
                        await self._send_parameters()
                        self._last_parameter_resend = current_time
                    
                    await asyncio.sleep(1)
                    
                # Emit signal when connection status changes
                if prev_stage != self.connection_stage:
                    is_connected = self.connection_stage == ConnectionStage.CONNECTED
                    self.connection_status_changed.emit(is_connected, self.connection_stage)
                    prev_stage = self.connection_stage
                
            except Exception as e:
                logger.error(f"{LOG_PREFIX} Connection loop error: {e}")
                await self._recover_from_transient_failure("connection loop error")
                
            # Small delay between iterations
            await asyncio.sleep(0.1)

    async def _send_initial_power_zero(self) -> bool:
        """Send initial power levels 0,0 to the device and report success."""
        strengths = CoyoteStrengths(channel_a=0, channel_b=0)
        return await self.send_command(strengths=strengths)

    async def _recover_from_transient_failure(self, reason: str, extra_delay: int = 0):
        """Handle recoverable BLE failures without permanently stopping auto-reconnect.

        extra_delay: number of consecutive failures (used to scale backoff on Windows
        to give WinRT time to actually release the stale connection).
        """
        logger.info(f"{LOG_PREFIX} Recovering from transient failure: {reason}")
        await self._disconnect_client()
        self._scan_attempt_counter = 0
        self.connection_stage = ConnectionStage.SCANNING
        # On Windows, scale backoff with failure streak so WinRT has time to release
        # the stale connection before we attempt again (min 1s, max 5s)
        if sys.platform.startswith("win") and extra_delay > 0:
            backoff = min(5.0, 1.0 + extra_delay * 1.0)
            logger.info(f"{LOG_PREFIX} Windows BLE backoff {backoff:.1f}s (streak={extra_delay})")
            # Running an active BleakScanner during the backoff nudges WinRT to release
            # the stale GATT session -- this is what actually clears WinRT connection
            # state, not just the scan cache. Equivalent to a soft BT adapter poke.
            try:
                logger.info(f"{LOG_PREFIX} Running active BLE scan during backoff to release WinRT GATT session")
                async with BleakScanner(scanning_mode="active") as _:
                    await asyncio.sleep(backoff)
                return  # _next_scan_time already irrelevant; return immediately to SCANNING
            except Exception as e:
                logger.debug(f"{LOG_PREFIX} Active scan during backoff failed: {e}")
        else:
            backoff = 1.0
        self._next_scan_time = time.time() + backoff

    def _create_client(self, device_or_address):
        """Create a Bleak client with conservative Windows behavior to reduce stale-cache issues."""
        def _on_disconnect(client):
            logger.warning(f"{LOG_PREFIX} BleakClient disconnected callback fired")

        if sys.platform.startswith("win"):
            try:
                return BleakClient(
                    device_or_address,
                    winrt={"use_cached_services": False},
                    disconnected_callback=_on_disconnect,
                )
            except TypeError:
                logger.debug(f"{LOG_PREFIX} Bleak backend does not support winrt kwargs; falling back")
                try:
                    return BleakClient(device_or_address, disconnected_callback=_on_disconnect)
                except TypeError:
                    return BleakClient(device_or_address)
        try:
            return BleakClient(device_or_address, disconnected_callback=_on_disconnect)
        except TypeError:
            return BleakClient(device_or_address)

    def _remember_device_address(self, address: Optional[str]):
        self._last_device_address = address
        self._cached_connect_failure_count = 0
        self._skip_cached_reconnect_scans = 0
        ui_settings.coyote_last_device_address.set(address or "")

    def start_updates(self, algorithm: Optional[Any]):
        logger.info(f"{LOG_PREFIX} start_updates called")
        self.algorithm = algorithm
        self.running = True

        future = None
        if self._event_loop:
            logger.info(f"{LOG_PREFIX} scheduling update_loop in event loop")
            future = asyncio.run_coroutine_threadsafe(self.update_loop(), self._event_loop)
        else:
            logger.error(f"{LOG_PREFIX} No event loop present!")

        if future:
            logger.info(f"{LOG_PREFIX} Future scheduled")
        else:
            logger.warning(f"{LOG_PREFIX} Update loop not scheduled")

    def stop_updates(self):
        """Stop the update loop but maintain connection"""
        logger.info(f"{LOG_PREFIX} Stopping updates")
        self.running = False
        self.algorithm = None
        
    async def _handle_battery_notification(self, sender, data: bytearray):
        """Handle battery level notifications"""
        battery_level = data[0]

        logger.info(f"{LOG_PREFIX} Battery level notification received: {battery_level}%")
        
        self.battery_level = battery_level
        self.battery_level_changed.emit(battery_level)

    async def _read_battery_level(self):
        """Read battery level directly from characteristic"""
        try:
            if not self.client or not self.client.is_connected:
                return
            
            data = await self.client.read_gatt_char(BATTERY_CHAR_UUID)
            if data and len(data) > 0:
                battery_level = data[0]
                logger.info(f"{LOG_PREFIX} Battery level read: {battery_level}%")
                self.battery_level = battery_level
                self.battery_level_changed.emit(battery_level)
        except Exception as e:
            logger.debug(f"{LOG_PREFIX} Failed to read battery level: {e}")

    async def _handle_status_notification(self, sender, data: bytearray):
        """Handle incoming status notifications from the device."""

        if not data:
            logger.warning(f"{LOG_PREFIX} Received empty status notification")
            return

        # if len(data) != 4:
        #     logger.warning(f"Unexpected notification length: {len(data)} - {list(data)}")
        #     return

        command_id = data[0]
        sequence_number = data[1]
        power_a = data[2]
        power_b = data[3]

        if command_id == CMD_POWER_UPDATE:
            logger.info(f"{LOG_PREFIX} Power level update (seq={sequence_number}) - Channel A: {power_a}, Channel B: {power_b}")
            self.strengths.channel_a = power_a
            self.strengths.channel_b = power_b
            self.power_levels_changed.emit(self.strengths)

        elif command_id == CMD_ACK:
            logger.debug(f"{LOG_PREFIX} Command acknowledged (seq={sequence_number})")
        
        elif command_id == CMD_ACTIVE_POWER:
            if len(data) < 4:
                logger.warning(f"{LOG_PREFIX} Malformed active power notification: {list(data)}")
                return

            # Track if this is the absolute first CMD_ACTIVE_POWER after connection
            if not self._first_active_power_seen:
                power_a = 0
                power_b = 0
                self._first_active_power_seen = True
            else:
                power_a = data[2]
                power_b = data[3]

            logger.info(f"{LOG_PREFIX} Active power update - Channel A: {power_a}, Channel B: {power_b}")

            # self.strengths.channel_a = power_a
            # self.strengths.channel_b = power_b
            # self.power_levels_changed.emit(self.strengths)

            # if len(data) > 4:
            #     extra = data[4:]
            #     logger.warning(f"Extra fields in 0x53 notification (undocumented): {list(extra)}")

        else:
            logger.warning(f"{LOG_PREFIX} Unknown notification type: 0x{command_id:02X} (seq={sequence_number})")
            logger.warning(f"{LOG_PREFIX} Raw notification: {list(data)}")

    async def _send_parameters(self) -> bool:
        """Send device parameters"""
        client = self.client
        if not client or not client.is_connected:
            logger.warning(f"{LOG_PREFIX} Cannot sync parameters while disconnected")
            return False

        logger.info(
            f"{LOG_PREFIX} Syncing parameters - "
            f"Limits: A={self.parameters.channel_a_limit}, B={self.parameters.channel_b_limit}, "
            f"Freq Balance: A={self.parameters.channel_a_freq_balance}, B={self.parameters.channel_b_freq_balance}, "
            f"Intensity Balance: A={self.parameters.channel_a_intensity_balance}, B={self.parameters.channel_b_intensity_balance}"
        )

        command = bytes([
            0xBF, # Does this command produce an ACK? Only if the seq nibble is > 0
            self.parameters.channel_a_limit,
            self.parameters.channel_b_limit,
            self.parameters.channel_a_freq_balance,
            self.parameters.channel_b_freq_balance,
            self.parameters.channel_a_intensity_balance,
            self.parameters.channel_b_intensity_balance
        ])
        
        # Send parameters with retry logic for characteristic not found
        max_retries = 3
        retry_delay = 0.05  # 50ms between retries
        last_error = None
        
        for attempt in range(max_retries):
            try:
                await client.write_gatt_char(WRITE_CHAR_UUID, command)
                return True  # Success
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
        
        # All retries exhausted
        logger.error(f"{LOG_PREFIX} Failed to sync parameters after {max_retries} retries: {last_error}")
        return False

    async def _subscribe_to_notifications(self, char_uuid: str) -> bool:
        """Subscribe to notifications for a characteristic"""
        try:
            client = self.client
            if not client or not client.is_connected:
                logger.error(f"{LOG_PREFIX} Cannot subscribe to {char_uuid} while disconnected")
                return False

            services = getattr(client, "services", None)
            if services is None:
                logger.error(f"{LOG_PREFIX} Services unavailable while subscribing to {char_uuid}")
                return False

            char = services.get_characteristic(char_uuid)
            if not char:
                logger.error(f"{LOG_PREFIX} Characteristic {char_uuid} not found")
                return False
            
            await client.start_notify(char_uuid, self._handle_status_notification)
            return True
        except Exception as e:
            logger.error(f"{LOG_PREFIX} Failed to subscribe to {char_uuid}: {e}")
            return False

    async def _scan_for_device(self):
        """Scan for Coyote device"""
        scan_start = time.time()

        def _finish(found: bool) -> bool:
            self._last_scan_elapsed = time.time() - scan_start
            self._scan_failure_streak = 0 if found else self._scan_failure_streak + 1
            return found

        try:
            logger.info(f"{LOG_PREFIX} Scanning for device: {self.device_name}")
            target_name = self.device_name.lower()
            target_prefix = "47l121"
            target_service_uuids = {
                MAIN_SERVICE_UUID.lower(),
                "00001812-0000-1000-8000-00805f9b34fb",
            }

            def _is_target(device, advertisement_data=None) -> bool:
                dev_name = (getattr(device, 'name', None) or "").lower()
                if dev_name == target_name or dev_name.startswith(target_prefix):
                    return True

                if advertisement_data:
                    adv_name = (getattr(advertisement_data, 'local_name', None) or "").lower()
                    if adv_name == target_name or adv_name.startswith(target_prefix):
                        return True
                    adv_uuids = [u.lower() for u in (getattr(advertisement_data, 'service_uuids', None) or [])]
                    if any(uuid in target_service_uuids for uuid in adv_uuids):
                        return True

                return False

            should_try_cached_address = bool(self._last_device_address and self._skip_cached_reconnect_scans <= 0)
            deferred_cached_address = None

            if should_try_cached_address:
                if sys.platform.startswith("win") and self._scan_failure_streak < 2:
                    logger.info(f"{LOG_PREFIX} Deferring cached-address reconnect until after fresh scans on Windows")
                    deferred_cached_address = self._last_device_address
                    should_try_cached_address = False
            elif self._last_device_address and self._skip_cached_reconnect_scans > 0:
                logger.info(
                    f"{LOG_PREFIX} Skipping cached-address reconnect this scan "
                    f"({self._skip_cached_reconnect_scans} scan(s) remaining)"
                )
                self._skip_cached_reconnect_scans -= 1

            if should_try_cached_address:
                try:
                    logger.info(f"{LOG_PREFIX} Trying direct reconnect to known address: {self._last_device_address}")
                    self.client = self._create_client(self._last_device_address)
                    self._using_cached_address = True
                    return _finish(True)
                except Exception as e:
                    self._using_cached_address = False
                    logger.debug(f"{LOG_PREFIX} Direct address reconnect setup failed: {e}")

            # Try filter-based scan that can match advertisement local name / prefix / service UUID
            try:
                def _matches(device, advertisement_data):
                    return _is_target(device, advertisement_data)

                device = await BleakScanner.find_device_by_filter(_matches, timeout=5.0)
                if device:
                    logger.info(f"{LOG_PREFIX} Device found via advertisement filter: {device.name} ({device.address})")
                    self._remember_device_address(device.address)
                    self.client = self._create_client(device.address)
                    self._using_cached_address = False
                    return _finish(True)
            except Exception as e:
                logger.info(f"{LOG_PREFIX} Filter scan error: {e}")

            # Run discover() every attempt for consistency and to avoid stale conditional branches.
            try:
                devices = await BleakScanner.discover(timeout=5.0)
                nearby = [f"{dev.name} ({dev.address})" for dev in devices if dev.name and dev.name.startswith("47L")]
                if nearby:
                    logger.info(f"{LOG_PREFIX} Nearby 47L devices: {', '.join(nearby)}")
                for dev in devices:
                    if _is_target(dev):
                        logger.info(f"{LOG_PREFIX} Device found via discover: {dev.name} ({dev.address})")
                        self._remember_device_address(dev.address)
                        self.client = self._create_client(dev.address)
                        self._using_cached_address = False
                        return _finish(True)
            except Exception as e:
                logger.info(f"{LOG_PREFIX} Discover scan error: {e}")

            try:
                device = await BleakScanner.find_device_by_name(self.device_name, timeout=5.0)
                if device:
                    logger.info(f"{LOG_PREFIX} Device found by name: {device.name} ({device.address})")
                    self._remember_device_address(device.address)
                    self.client = self._create_client(device.address)
                    self._using_cached_address = False
                    return _finish(True)
            except Exception as e:
                logger.info(f"{LOG_PREFIX} Name search error: {e}")

            if sys.platform.startswith("win") and self._scan_failure_streak >= 2:
                try:
                    logger.warning(
                        f"{LOG_PREFIX} Triggering Windows BLE scanner refresh "
                        f"after {self._scan_failure_streak + 1} consecutive misses"
                    )
                    async with BleakScanner(scanning_mode="active") as scanner:
                        await asyncio.sleep(4.0)
                        discovered_with_adv = getattr(scanner, 'discovered_devices_and_advertisement_data', {})
                        if discovered_with_adv:
                            for _, (dev, adv) in discovered_with_adv.items():
                                if _is_target(dev, adv):
                                    logger.info(
                                        f"{LOG_PREFIX} Device found after scanner refresh: "
                                        f"{dev.name} ({dev.address})"
                                    )
                                    self._remember_device_address(dev.address)
                                    self.client = self._create_client(dev.address)
                                    self._using_cached_address = False
                                    return _finish(True)
                        else:
                            for dev in scanner.discovered_devices:
                                if _is_target(dev):
                                    logger.info(
                                        f"{LOG_PREFIX} Device found after scanner refresh: "
                                        f"{dev.name} ({dev.address})"
                                    )
                                    self._remember_device_address(dev.address)
                                    self.client = self._create_client(dev.address)
                                    self._using_cached_address = False
                                    return _finish(True)
                except Exception as e:
                    logger.info(f"{LOG_PREFIX} Scanner refresh error: {e}")

            if deferred_cached_address:
                try:
                    logger.info(f"{LOG_PREFIX} Trying direct reconnect to known address: {deferred_cached_address}")
                    self.client = self._create_client(deferred_cached_address)
                    self._using_cached_address = True
                    return _finish(True)
                except Exception as e:
                    logger.debug(f"{LOG_PREFIX} Cached-address fallback setup failed: {e}")

            logger.warning(f"{LOG_PREFIX} Device {self.device_name} not found. Check device power and proximity.")
            return _finish(False)
            
        except Exception as e:
            logger.error(f"{LOG_PREFIX} Scan error: {e}")
            return _finish(False)

    async def send_command(self, 
                            strengths: Optional[CoyoteStrengths] = None,
                            pulses: Optional[CoyotePulses] = None):
        """
        Send strength update and/or pulse pattern command to device.

        Args:
            strengths: Optional strength update for channels A and B
            pulses: Optional pulse patterns for channels A and B
        """

        if pulses:
            self.pulse_sent.emit(pulses)
        
        if not self.client or not self.client.is_connected:
            # logger.warning("Attempted to send command while disconnected")

            # Optimistic update for offline testing
            if strengths:
                self.strengths.channel_a = strengths.channel_a
                self.strengths.channel_b = strengths.channel_b

            return False

        client = self.client

        if not strengths and not pulses:
            logger.warning(f"{LOG_PREFIX} send_command called with no data")
            return False

        # Determine strength interpretation (default absolute set if new strength provided)
        if strengths:
            interp_a = INTERP_ABSOLUTE_SET  # Absolute set for Channel A
            interp_b = INTERP_ABSOLUTE_SET  # Absolute set for Channel B
        else:
            interp_a = INTERP_NO_CHANGE  # No change
            interp_b = INTERP_NO_CHANGE  # No change

        # Pack sequence number + interpretation into 1 byte (upper 4 = seq, lower 4 = interp)
        # Request ACK only when strength is being changed (need confirmation from device)
        request_ack = strengths is not None
        control_byte = ((self.sequence_number if request_ack else 0) << 4) | (interp_a << 2) | interp_b

        # Validate pulses before sending (protocol requirement: intensity must be 0-100)
        valid_pulses = pulses
        if pulses:
            invalid_a = any(p.intensity < 0 or p.intensity > 100 for p in pulses.channel_a)
            invalid_b = any(p.intensity < 0 or p.intensity > 100 for p in pulses.channel_b)
            if invalid_a or invalid_b:
                logger.warning(f"{LOG_PREFIX} Invalid pulse intensity detected (must be 0-100). Discarding pulses.")
                valid_pulses = None

        # Build base command (B0 packet structure)
        command = bytearray([
            CMD_B0,            # Command ID
            control_byte,              # Combined seq + interpretation
            strengths.channel_a if strengths else 0,
            strengths.channel_b if strengths else 0,
        ])

        # Append pulse data if provided (waveform duration (aka frequency) + intensity)
        if valid_pulses:
            command.extend([a.duration for a in valid_pulses.channel_a])
            command.extend([a.intensity for a in valid_pulses.channel_a])
            command.extend([b.duration for b in valid_pulses.channel_b])
            command.extend([b.intensity for b in valid_pulses.channel_b])
        else:
            command.extend([0] * B0_NO_PULSES_PAD_BYTES)  # No pulses = zero padding

        # Log what we're sending
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"{LOG_PREFIX} Sending command (seq={self.sequence_number}):")

            if valid_pulses:
                pulses_a = "\n".join(
                    f"  Pulse {i+1}: Freq={pulse.frequency} Hz, Intensity={pulse.intensity}"
                    for i, pulse in enumerate(valid_pulses.channel_a)
                )
                pulses_b = "\n".join(
                    f"  Pulse {i+1}: Freq={pulse.frequency} Hz, Intensity={pulse.intensity}"
                    for i, pulse in enumerate(valid_pulses.channel_b)
                )
                
                logger.debug(
                    f"{LOG_PREFIX} Channel A ({self.strengths.channel_a}):\n{pulses_a}\n"
                    f"{LOG_PREFIX} Channel B ({self.strengths.channel_b}):\n{pulses_b}"
                )

        # Send the final command with retry logic for characteristic not found
        max_retries = 3
        retry_delay = 0.05  # 50ms between retries
        last_error = None

        if not self._logged_first_send_payload:
            logger.debug(
                f"{LOG_PREFIX} First send payload at {time.time():.6f}, len(command)={len(command)}"
            )
            self._logged_first_send_payload = True
        
        for attempt in range(max_retries):
            try:
                await client.write_gatt_char(WRITE_CHAR_UUID, command)
                self.sequence_number = (self.sequence_number + 1) % SEQUENCE_MODULO  # Wrap seq at 4 bits (0-15)
                return True  # Success
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
        
        # All retries exhausted
        logger.error(f"{LOG_PREFIX} Failed to send command after {max_retries} retries: {last_error}")
        return False
    
    async def _disconnect_client(self):
        """Internal method to disconnect the Bluetooth client without shutting down the loop"""
        if self.client:
            self.running = False
            
            # Send zero pulses to turn off outputs
            try:
                zero_pulses = CoyotePulses(
                    channel_a=[CoyotePulse(frequency=0, intensity=0, duration=0)] * PULSES_PER_PACKET,
                    channel_b=[CoyotePulse(frequency=0, intensity=0, duration=0)] * PULSES_PER_PACKET
                )
                await self.send_command(pulses=zero_pulses)
            except Exception as e:
                logger.debug(f"{LOG_PREFIX} Error sending zero pulses during disconnect: {e}")
            
            try:
                # Timeout prevents WinRT from blocking the reconnect loop when the
                # GATT session is already in a stuck/closed state.
                await asyncio.wait_for(self.client.disconnect(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"{LOG_PREFIX} disconnect() timed out (WinRT stale session); forcing cleanup")
            except Exception as e:
                logger.debug(f"{LOG_PREFIX} Error disconnecting client: {e}")
        
        self.client = None
    
    async def disconnect(self):
        """Permanent disconnect - shuts down the connection loop"""
        logger.info(f"{LOG_PREFIX} Disconnecting from device")
        self._shutdown = True  # Stop the connection loop from trying to reconnect
        await self._disconnect_client()
        self.connection_stage = ConnectionStage.DISCONNECTED
    
    def reset_connection(self):
        """Temporary disconnect for resetting connection (reconnect will happen automatically)"""
        logger.info(f"{LOG_PREFIX} Reset connection requested")
        self._scan_attempt_counter = 0
        self._next_scan_time = 0.0
        self._force_disconnect = True  # Signal the connection loop to disconnect temporarily

    async def update_loop(self):
        logger.info(f"{LOG_PREFIX} Starting update loop, running={self.running}, algorithm={self.algorithm}")
        last_battery_read = time.time()
        battery_read_interval = 5.0  # Read battery every 5 seconds

        try:
            logger.info(f"{LOG_PREFIX} Update loop started, running={self.running}")

            while self.running:
                try:
                    if not self.algorithm:
                        logger.warning(f"{LOG_PREFIX} Algorithm not yet set")
                        await asyncio.sleep(0.1)
                        continue

                    current_time = time.time()
                    # Periodically read battery level
                    if current_time - last_battery_read >= battery_read_interval:
                        await self._read_battery_level()
                        last_battery_read = current_time

                    # Only log when a packet is actually generated and sent
                    if current_time >= self.algorithm.next_update_time:
                        pulses = self.algorithm.generate_packet(current_time)
                        if pulses is not None:
                            await self.send_command(pulses=pulses)
                        # Check if algorithm still exists after generate_packet()
                        if self.algorithm:
                            sleep_time = max(0.001, self.algorithm.next_update_time - time.time())
                        else:
                            sleep_time = 0.01
                    else:
                        sleep_time = 0.01

                    await asyncio.sleep(sleep_time)

                except Exception as inner_e:
                    logger.exception(f"{LOG_PREFIX} Exception inside update loop iteration: {inner_e}")
                    await asyncio.sleep(0.1)  # prevent tight-crash-loop

        except Exception as outer_e:
            logger.exception(f"{LOG_PREFIX} Fatal exception in update_loop: {outer_e}")

        finally:
            logger.info(f"{LOG_PREFIX} Update loop stopped")
    
    def is_connected_and_running(self) -> bool:
        return bool(
            self.connection_stage == ConnectionStage.CONNECTED
            and self.client
            and self.client.is_connected
        )

    def stop(self):
        """Stop updates and attempt a clean disconnect before app shutdown."""
        self.stop_updates()

        if self._event_loop and not self._event_loop.is_closed():
            try:
                future = asyncio.run_coroutine_threadsafe(self.disconnect(), self._event_loop)
                future.result(timeout=2.0)
            except concurrent.futures.TimeoutError:
                logger.warning(f"{LOG_PREFIX} Timed out waiting for disconnect during stop()")
            except Exception as e:
                logger.debug(f"{LOG_PREFIX} stop() disconnect scheduling failed: {e}")
