# GiveNergy Modbus TCP Register Map

This document contains the complete Modbus TCP register mapping for GiveNergy inverters and battery systems. The information is derived from the official GiveNergy modbus implementation and GivTCP project.

## Connection Details

- **Protocol:** Modbus TCP (proprietary GiveNergy framing)
- **Default Port:** 8899
- **Slave Address:** 0x11 (inverter), 0x32+ (batteries)
- **Max Registers per Read:** 60
- **Register Alignment:** Registers must be aligned on 60-byte offset boundaries for optimal reads

---

## Holding Registers (Writable Configuration)

Holding registers are used for configuration and control parameters that persist on the device.

| Register | Address | Name | Type | Units | Description |
|----------|---------|------|------|-------|-------------|
| 0 | 0x0000 | Device Type Code | unsigned | - | Inverter model code |
| 1 | 0x0001 | Registers Module (high) | unsigned | - | Firmware module version (high) |
| 2 | 0x0002 | Registers Module (low) | unsigned | - | Firmware module version (low) |
| 3 | 0x0003 | Input/Output Phase | unsigned | - | Input tracker number and output phase |
| 8-12 | 0x0008-0x000C | Battery Serial Number | ascii | - | Battery serial number (5 registers) |
| 13-17 | 0x000D-0x0011 | Inverter Serial Number | ascii | - | Inverter serial number (5 registers) |
| 18 | 0x0012 | Battery Firmware Version | unsigned | - | BMS firmware version |
| 19 | 0x0013 | DSP Firmware Version | unsigned | - | DSP firmware version |
| 20 | 0x0014 | Winter Mode | boolean | - | Enable/disable winter mode (0=off, 1=on) |
| 21 | 0x0015 | ARM Firmware Version | unsigned | - | ARM firmware version |
| 27 | 0x001B | Battery Power Mode | boolean | - | Battery operation mode (0=ECO, 1=TIMED DEMAND, etc) |
| 31 | 0x001F | Charge Slot 2 Start | time | HHMM | Charge start time for slot 2 |
| 32 | 0x0020 | Charge Slot 2 End | time | HHMM | Charge end time for slot 2 |
| 35 | 0x0023 | System Time - Year | unsigned | - | System year (e.g., 2024) |
| 36 | 0x0024 | System Time - Month | unsigned | - | System month (1-12) |
| 37 | 0x0025 | System Time - Day | unsigned | - | System day (1-31) |
| 38 | 0x0026 | System Time - Hour | unsigned | - | System hour (0-23) |
| 39 | 0x0027 | System Time - Minute | unsigned | - | System minute (0-59) |
| 40 | 0x0028 | System Time - Second | unsigned | - | System second (0-59) |
| 44 | 0x002C | Discharge Slot 2 Start | time | HHMM | Discharge start time for slot 2 |
| 45 | 0x002D | Discharge Slot 2 End | time | HHMM | Discharge end time for slot 2 |
| 50 | 0x0032 | Active Power Rate | unsigned | % | Active power output percentage (0-100) |
| 56 | 0x0038 | Discharge Slot 1 Start | time | HHMM | Discharge start time for slot 1 |
| 57 | 0x0039 | Discharge Slot 1 End | time | HHMM | Discharge end time for slot 1 |
| 59 | 0x003B | Discharge Enable | boolean | - | Enable/disable discharge (0=disable, 1=enable) |
| 94 | 0x005E | Charge Slot 1 Start | time | HHMM | Charge start time for slot 1 |
| 95 | 0x005F | Charge Slot 1 End | time | HHMM | Charge end time for slot 1 |
| 96 | 0x0060 | Battery Smart Charge | boolean | - | Enable/disable smart charging (0=disable, 1=enable) |
| 110 | 0x006E | Battery SOC Reserve | unsigned | % | Minimum battery discharge SOC (0-100) |
| 111 | 0x006F | Battery Charge Limit | unsigned | % | Battery charge limit percentage |
| 112 | 0x0070 | Battery Discharge Limit | unsigned | % | Battery discharge limit percentage |
| 114 | 0x0072 | Battery Power Reserve | unsigned | W | Battery power reserve in watts |
| 116 | 0x0074 | Target SOC | unsigned | % | Target battery state of charge (4-100) |
| 163 | 0x00A3 | Reboot Inverter | unsigned | - | Send 1 to reboot inverter |

---

## Input Registers (Read-Only Status)

Input registers contain real-time monitoring data from the inverter and battery system. These are read-only values.

### Power Measurements

| Register | Address | Name | Type | Scale | Units | Description |
|----------|---------|------|------|-------|-------|-------------|
| 18 | 0x0012 | PV1 Energy Today | unsigned | 0.1 | kWh | Solar generation from string 1 today |
| 19 | 0x0013 | PV1 Power | unsigned | 1 | W | Real-time power from PV string 1 |
| 20 | 0x0014 | PV2 Energy Today | unsigned | 0.1 | kWh | Solar generation from string 2 today |
| 21 | 0x0015 | PV2 Power | unsigned | 1 | W | Real-time power from PV string 2 |
| 25 | 0x0019 | Grid Energy Out Day | unsigned | 0.1 | kWh | Grid export energy today |
| 26 | 0x001A | Grid Energy In Day | unsigned | 0.1 | kWh | Grid import energy today |
| 30 | 0x001E | Grid Output Power | signed | 1 | W | Grid power (+ = export, - = import) |
| 35 | 0x0023 | Total Load Energy Today | unsigned | 0.1 | kWh | House consumption energy today |
| 36 | 0x0024 | Battery Charge Energy Today | unsigned | 0.1 | kWh | Battery charge energy today |
| 37 | 0x0025 | Battery Discharge Energy Today | unsigned | 0.1 | kWh | Battery discharge energy today |
| 42 | 0x002A | Load Total Power | unsigned | 1 | W | Current house load/consumption |
| 52 | 0x0034 | Battery Power | signed | 1 | W | Battery power (+ = discharge, - = charge) |

### Voltage Measurements

| Register | Address | Name | Type | Scale | Units | Description |
|----------|---------|------|------|-------|-------|-------------|
| 1 | 0x0001 | PV1 Voltage | unsigned | 0.1 | V | PV string 1 voltage |
| 2 | 0x0002 | PV2 Voltage | unsigned | 0.1 | V | PV string 2 voltage |
| 5 | 0x0005 | Grid Voltage | unsigned | 0.1 | V | Single phase grid voltage |
| 50 | 0x0032 | Battery Voltage | unsigned | 0.01 | V | Battery pack voltage |
| 53 | 0x0035 | Output Voltage | unsigned | 0.1 | V | Inverter output voltage |

### Current Measurements

| Register | Address | Name | Type | Scale | Units | Description |
|----------|---------|------|------|-------|-------|-------------|
| 8 | 0x0008 | PV1 Input Current | unsigned | 0.01 | A | PV string 1 input current |
| 9 | 0x0009 | PV2 Input Current | unsigned | 0.01 | A | PV string 2 input current |
| 10 | 0x000A | Grid Output Current | unsigned | 0.01 | A | Grid output current |
| 51 | 0x0033 | Battery Current | signed | 0.01 | A | Battery current (+ = discharge, - = charge) |
| 58 | 0x003A | Grid Port Current | unsigned | 0.01 | A | Grid port current |

### Battery & System State

| Register | Address | Name | Type | Scale | Units | Description |
|----------|---------|------|------|-------|-------|-------------|
| 0 | 0x0000 | Inverter Status | unsigned | 1 | - | System operational status code |
| 14 | 0x000E | Charge Status | unsigned | 1 | - | Battery charging status (0=idle, 1=charging, etc) |
| 49 | 0x0031 | System Mode | unsigned | 1 | - | Current operating mode |
| 59 | 0x003B | Battery Percent | unsigned | 1 | % | **Battery SOC (State of Charge)** |

### Temperature Measurements

| Register | Address | Name | Type | Scale | Units | Description |
|----------|---------|------|------|-------|-------|-------------|
| 41 | 0x0029 | Inverter Temperature | unsigned | 0.1 | °C | Inverter heatsink/internal temperature |
| 55 | 0x0037 | Charger Temperature | unsigned | 0.1 | °C | Charger/BMS temperature |
| 56 | 0x0038 | Battery Temperature | unsigned | 0.1 | °C | Battery pack temperature |

### Frequency & Efficiency

| Register | Address | Name | Type | Scale | Units | Description |
|----------|---------|------|------|-------|-------|-------------|
| 13 | 0x000D | Grid Frequency | unsigned | 0.01 | Hz | Grid frequency |
| 54 | 0x0036 | Output Frequency | unsigned | 0.01 | Hz | Output frequency |

### Energy Counters (Total)

| Register | Address | Name | Type | Scale | Units | Description |
|----------|---------|------|------|-------|-------|-------------|
| 27-28 | 0x001B-0x001C | Total PV Energy (High/Low) | hex | 0.1 | kWh | Total solar generation (lifetime) |
| 32-33 | 0x0020-0x0021 | Grid Import Total (High/Low) | hex | 0.1 | kWh | Total grid import (lifetime) |
| 45-46 | 0x002D-0x002E | Total Generate Energy (High/Low) | hex | 0.1 | kWh | Total generation (lifetime) |
| 105 | 0x0069 | Battery Discharge Energy Total AC | unsigned | 0.1 | kWh | Battery discharge total (AC) |
| 106 | 0x006A | Battery Charge Energy Total AC | unsigned | 0.1 | kWh | Battery charge total (AC) |
| 180 | 0x00B4 | Battery Discharge Energy Total | unsigned | 0.1 | kWh | Battery discharge energy (lifetime) |
| 181 | 0x00B5 | Battery Charge Energy Total | unsigned | 0.1 | kWh | Battery charge energy (lifetime) |

### Fault/Status Codes

| Register | Address | Name | Type | Scale | Units | Description |
|----------|---------|------|------|-------|-------|-------------|
| 39 | 0x0027 | Fault Code (High 16bits) | hex | 1 | - | Error code - high word |
| 40 | 0x0028 | Fault Code (Low 16bits) | hex | 1 | - | Error code - low word |

---

## Common Data Patterns

### Reading Power Data (Recommended Batch)
To get current power flow data, read holding registers **0-60** which includes:
- PV power from both strings
- Battery power and SOC
- Grid power (import/export)
- Load power
- All temperature readings

### Reading Daily Energy (Recommended Batch)
To get daily energy statistics, read registers **17-40** which includes:
- Today's PV generation
- Today's battery charge/discharge
- Today's grid import/export
- Today's consumption

### Status Registers
- **Register 0 (0x0000):** Inverter Status - Check this for operational health
- **Register 59 (0x003B):** **Battery SOC** - Primary state of charge indicator
- **Register 52 (0x0034):** Battery Power - Shows charge/discharge direction

---

## Special Notes

### Data Types

- **unsigned:** Unsigned 16-bit integer (0-65535)
- **signed:** Signed 16-bit integer (-32768 to 32767)
- **boolean:** 0 = Off/False, 1 = On/True
- **hex:** Hexadecimal value (requires special decoding for 32-bit values)
- **time:** Time in HHMM format (e.g., 1430 = 14:30)
- **ascii:** ASCII string (typically 5 registers for serial numbers)

### Scaling Factors

Many registers use scaling factors (e.g., 0.1, 0.01). The actual physical value = register_value × scale_factor
- Example: PV1 Voltage register = 1234, scale = 0.1 → Actual voltage = 123.4V

### 32-Bit Values

Some energy counters span two registers (High/Low). Combine them as:
```
32bit_value = (high_register << 16) | low_register
physical_value = 32bit_value × scale_factor
```

### Write-Safe Registers

Only these registers are safe to write to (others are read-only):
- 20, 27, 31, 32, 35-40, 44, 45, 50, 56, 57, 59, 94-96, 110-112, 114, 116, 163

---

## Prometheus Exporter Implementation Notes

For the prometheus-givenergy exporter, these are the key registers to monitor:

1. **Battery SOC** → Gauge metric (Register 59)
2. **Solar Power** → Gauge metric (Registers 18+19)
3. **Battery Power** → Gauge metric (Register 52)
4. **Grid Power** → Gauge metric (Register 30)
5. **Load Power** → Gauge metric (Register 42)
6. **Battery Temperature** → Gauge metric (Register 56)
7. **Inverter Temperature** → Gauge metric (Register 41)
8. **Daily Energy Counters** → Counter metrics (Registers 35-37)

---

## References

- Source: [GiveNergy giv_tcp Project](https://github.com/GivEnergy/giv_tcp)
- Register Lookup Table: `givenergy_modbus/lut.py`
- Protocol Implementation: `givenergy_modbus/modbus.py`
- Modbus Client: [jak/givenergy-modbus](https://github.com/jak/givenergy-modbus)
- MQTT Bridge: [jak/givenergy-mqtt](https://github.com/jak/givenergy-mqtt)
- Home Assistant Integration: [cdpuk/givenergy-local](https://github.com/cdpuk/givenergy-local)

---

**Last Updated:** 15 April 2026
**GiveNergy Modbus Protocol Version:** Non-standard TCP with proprietary framing
