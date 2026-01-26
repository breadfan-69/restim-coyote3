# Coyote Device API Compliance Analysis

## Official DG-LAB Coyote API Documentation

**Device:** Coyote 3.0 (郊狼情趣脉冲主机 V3)  
**Protocol:** BLE  
**Source:** [DG-LAB-OPENSOURCE/coyote/v3/README_V3.md](https://github.com/DG-LAB-OPENSOURCE/DG-LAB-OPENSOURCE/blob/main/coyote/v3/README_V3.md)

---

## BF Command Structure

The **BF command** (7 bytes) configures permanent device parameters that survive power cycles:

```
0xBF (1 byte)
+ Channel A Power Limit (1 byte)
+ Channel B Power Limit (1 byte)
+ Channel A Frequency Balance (1 byte)
+ Channel B Frequency Balance (1 byte)
+ Channel A Intensity Balance (1 byte)
+ Channel B Intensity Balance (1 byte)
```

**⚠️ Critical:** BF command has **no return acknowledgment**. Must be resent on every reconnect.

---

## Your Implementation vs Official API

### ✅ COMPLIANT: Channel Power Limits

| Control | Your Range | Official Range | Purpose | Status |
|---------|-----------|-----------------|---------|--------|
| `coyote_channel_a_limit` | 0-200 | 0-200 | Soft limit cap for Channel A strength | ✅ Correct |
| `coyote_channel_b_limit` | 0-200 | 0-200 | Soft limit cap for Channel B strength | ✅ Correct |

**Implementation:**  
- Read from preferences in [preferences_dialog.py](qt_ui/preferences_dialog.py#L158-L159)
- Stored in `CoyoteParams` in [types.py](device/coyote/types.py#L17-L18)
- Sent via BF command in [device.py](device/coyote/device.py#L251-L252)

**How it works:** These limits cap the maximum intensity reachable on each channel, regardless of B0 intensity commands.

---

### ✅ COMPLIANT: Frequency Balance Parameters

| Control | Your Range | Official Range | Purpose | Status |
|---------|-----------|-----------------|---------|--------|
| `coyote_channel_a_freq_balance` | 0-255 | 0-255 | Freq balance for Channel A | ✅ Correct |
| `coyote_channel_b_freq_balance` | 0-255 | 0-255 | Freq balance for Channel B | ✅ Correct |

**Official Name:** "频率平衡参数 1" (Frequency Balance Parameter 1)

**What it does:** Adjusts how different frequencies feel at the same power level. Higher values = stronger low-frequency sensation impact.

> "波形频率平衡参数会调整波形高低频的感受，值越大，低频波形冲击感越强。"  
> "Adjusts high/low frequency sensation. Higher value = stronger low frequency impact."

**Implementation:**
- Read from preferences in [preferences_dialog.py](qt_ui/preferences_dialog.py#L160-L161)
- Stored in `CoyoteParams` in [types.py](device/coyote/types.py#L21-L22)
- Sent via BF command in [device.py](device/coyote/device.py#L253-L254)

---

### ✅ COMPLIANT: Intensity Balance Parameters

| Control | Your Range | Official Range | Purpose | Status |
|---------|-----------|-----------------|---------|--------|
| `coyote_channel_a_intensity_balance` | 0-255 | 0-255 | Intensity balance for Channel A | ✅ Correct |
| `coyote_channel_b_intensity_balance` | 0-255 | 0-255 | Intensity balance for Channel B | ✅ Correct |

**Official Name:** "频率平衡参数 2" (Frequency Balance Parameter 2 - note: despite name, it's intensity-based)

**What it does:** Adjusts pulse width based on frequency. Higher values = stronger low-frequency sensation when combined with intensity.

> "波形强度平衡参数会调整波形脉冲宽度，值越大，低频波形刺激越强。"  
> "Adjusts waveform pulse width. Higher value = stronger low frequency stimulation."

**Implementation:**
- Read from preferences in [preferences_dialog.py](qt_ui/preferences_dialog.py#L162-L163)
- Stored in `CoyoteParams` in [types.py](device/coyote/types.py#L23-L24)
- Sent via BF command in [device.py](device/coyote/device.py#L255-L256)

---

## UI-Only Settings (Algorithm/Display)

### ⚠️ NOT API PARAMETERS

These settings are **algorithm tuning** and **UI display preferences**, NOT sent to the device:

| Control | Purpose | API Command | Status |
|---------|---------|-------------|--------|
| `coyote_max_intensity_change_per_pulse` | Smoothing constraint for algorithm | None (local only) | ℹ️ Algorithm-only |
| `coyote_graph_window` | Visualizer time window duration | None (local only) | ℹ️ UI-only |
| `coyote_debug_logging` | Enable debug output to console | None (local only) | ℹ️ UI-only |

---

## Wiring Verification

### ✅ Parameter Flow: Preferences → Device

```
preferences_dialog.py (UI)
    ↓ (user sets values)
settings.py (persistence layer)
    ↓ (on "Apply")
CoyoteParams (dataclass in types.py)
    ↓ (at connection)
device.py._send_parameters()
    ↓ (constructs BF command)
BLE GATT Write (0xBF command to device)
```

**Code Path:**
1. User adjusts spinbox in Preferences dialog
2. [preferences_dialog.py#L335-L339](qt_ui/preferences_dialog.py#L335-L339) calls `settings.set()`
3. On device connect: [device.py#L260-L274](device/coyote/device.py#L260-L274) calls `_send_parameters()`
4. BF command sent via `write_gatt_char(WRITE_CHAR_UUID, command)`

---

## Critical Issues & Recommendations

### ⚠️ ISSUE 1: Missing Resend on Reconnect

**Current:** Parameters sent once at connection  
**Required:** Parameters must be resent after EVERY reconnection

**API Documentation:**
> "🚨 BF 指令写入之后会直接生效，没有返回值，所以每次重连设备之后都必须重新写入 BF 指令设置软上限"  
> "🚨 After BF command is written, it takes effect immediately with no return value. **You MUST resend the BF command after every reconnection** to prevent unexpected soft limit values."

**Current Code in device.py:**
```python
async def _send_parameters(self):  # Called once at connection
    """Send device parameters"""
    command = bytes([0xBF, ...])
    await self.client.write_gatt_char(WRITE_CHAR_UUID, command)
```

**Fix Needed:** Resend parameters after reconnection events

---

### ⚠️ ISSUE 2: No BF Command Timing Control

**Current:** BF command sent early in connection sequence  
**Recommended:** Should be sent AFTER battery and status notify subscriptions

**From Official Protocol:**
The BF command should be part of the full initialization sequence, not first.

---

### ✅ ISSUE 3: B0 Command Implementation

Your [channel_controller.py](device/coyote/channel_controller.py) correctly implements the B0 command (pulse waveform data) which is separate from the BF command. The strength/power parameters are correctly handled through the B0 command's relative/absolute mode bits.

---

## Summary Table

| Parameter | Type | Range | Device Command | Persisted | Your Status |
|-----------|------|-------|-----------------|-----------|-------------|
| Channel A Limit | Device Param | 0-200 | BF byte 1 | ✅ Yes (power cycle) | ✅ Correct |
| Channel B Limit | Device Param | 0-200 | BF byte 2 | ✅ Yes (power cycle) | ✅ Correct |
| A Freq Balance | Device Param | 0-255 | BF byte 3 | ✅ Yes (power cycle) | ✅ Correct |
| B Freq Balance | Device Param | 0-255 | BF byte 4 | ✅ Yes (power cycle) | ✅ Correct |
| A Intensity Balance | Device Param | 0-255 | BF byte 5 | ✅ Yes (power cycle) | ✅ Correct |
| B Intensity Balance | Device Param | 0-255 | BF byte 6 | ✅ Yes (power cycle) | ✅ Correct |
| Max Intensity Change | Algorithm | 0-100% | None (local) | ✅ App config | ℹ️ Not API |
| Graph Window | UI Display | 0.1-10s | None (local) | ✅ App config | ℹ️ Not API |
| Debug Logging | UI Display | Toggle | None (local) | ✅ App config | ℹ️ Not API |

---

## Conclusion

✅ **Your preferences controls are CORRECTLY mapped to the Coyote API** for all 6 device parameters (limits + balance parameters).

⚠️ **One critical issue:** Parameters must be resent on every reconnection as per official API requirement. Currently only sent once at initial connection.

📍 **Recommendation:** Add parameter resend logic to device reconnection handler.
