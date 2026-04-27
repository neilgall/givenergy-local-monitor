#!/usr/bin/env python3
"""
GivEnergy Inverter Control API

FastAPI server for controlling a GivEnergy inverter via local Modbus TCP.

Environment variables:
    INVERTER_HOST   (required) IP address or hostname of the inverter
    INVERTER_PORT   (optional, default 8899) Modbus TCP port
    LOG_LEVEL       (optional, default INFO)
    API_PORT        (optional, default 8000)
"""

import asyncio
import datetime
import logging
import os
from contextlib import asynccontextmanager
from datetime import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field, validator

from givenergy_modbus.client import GivEnergyClient
from givenergy_modbus.model.plant import Plant

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logging.getLogger("givenergy_modbus").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class TimeSlotRequest(BaseModel):
    start: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Start time in HH:MM")
    end: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="End time in HH:MM")

    def as_times(self) -> tuple[time, time]:
        sh, sm = map(int, self.start.split(":"))
        eh, em = map(int, self.end.split(":"))
        return time(sh, sm), time(eh, em)


class EnabledRequest(BaseModel):
    enabled: bool = Field(..., description="True to enable, False to disable")


class SoCPercentRequest(BaseModel):
    percent: int = Field(..., ge=4, le=100, description="Battery SoC percentage (4-100)")


class PowerLimitRequest(BaseModel):
    percent: int = Field(..., ge=0, le=50, description="Power limit as percentage of max (0-50)")


class WinterModeRequest(BaseModel):
    enabled: bool = Field(..., description="True to enable winter mode, False to disable")
    target_soc: Optional[int] = Field(
        None, ge=4, le=100,
        description="Target SoC to stop charging at (required when enabled=True)"
    )

    @validator("target_soc", always=True)
    @classmethod
    def validate_target_soc(cls, v, values) -> Optional[int]:
        if values.get("enabled") and v is None:
            raise ValueError("target_soc is required when enabling winter mode")
        return v


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

def _make_client() -> GivEnergyClient:
    host = os.environ.get("INVERTER_HOST", "").strip()
    if not host:
        raise RuntimeError("INVERTER_HOST environment variable is required")
    port = int(os.environ.get("INVERTER_PORT", "8899"))
    return GivEnergyClient(host=host, port=port)


async def _execute(op_name: str, fn):
    """Run a synchronous inverter operation in a thread pool, mapping errors to HTTP responses."""
    def _run():
        client = _make_client()
        fn(client)

    try:
        await asyncio.to_thread(_run)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("%s failed: %s", op_name, exc)
        raise HTTPException(
            status_code=503, detail=f"Inverter communication failed: {exc}"
        ) from exc


def _format_time(value: datetime.time) -> str:
    return value.strftime("%H:%M")


def _format_slot(slot_value) -> dict[str, Optional[str]]:
    start, end = slot_value
    return {
        "start": _format_time(start) if isinstance(start, datetime.time) else None,
        "end": _format_time(end) if isinstance(end, datetime.time) else None,
    }


def _is_slot_enabled(slot_value) -> bool:
    start, end = slot_value
    return not (
        isinstance(start, datetime.time)
        and isinstance(end, datetime.time)
        and start.hour == 0
        and start.minute == 0
        and end.hour == 0
        and end.minute == 0
    )


async def _read_state() -> dict:
    """Read current inverter state from holding + input registers."""

    def _run() -> dict:
        client = _make_client()
        plant = Plant(number_batteries=1)
        client.refresh_plant(plant, full_refresh=True)
        inverter = plant.inverter

        charge_slot_1 = getattr(inverter, "charge_slot_1", (None, None))
        charge_slot_2 = getattr(inverter, "charge_slot_2", (None, None))
        discharge_slot_1 = getattr(inverter, "discharge_slot_1", (None, None))
        discharge_slot_2 = getattr(inverter, "discharge_slot_2", (None, None))

        battery_power_mode = int(getattr(inverter, "battery_power_mode", 1))
        enable_charge_target = bool(getattr(inverter, "enable_charge_target", False))

        return {
            "charge_slots": {
                "1": {
                    **_format_slot(charge_slot_1),
                    "enabled": _is_slot_enabled(charge_slot_1),
                },
                "2": {
                    **_format_slot(charge_slot_2),
                    "enabled": _is_slot_enabled(charge_slot_2),
                },
            },
            "discharge_slots": {
                "1": {
                    **_format_slot(discharge_slot_1),
                    "enabled": _is_slot_enabled(discharge_slot_1),
                },
                "2": {
                    **_format_slot(discharge_slot_2),
                    "enabled": _is_slot_enabled(discharge_slot_2),
                },
            },
            "battery": {
                "soc_reserve_percent": int(getattr(inverter, "battery_soc_reserve", 0)),
                "charge_limit_percent": int(getattr(inverter, "battery_charge_limit", 0)),
                "discharge_limit_percent": int(getattr(inverter, "battery_discharge_limit", 0)),
                "target_soc_percent": int(getattr(inverter, "charge_target_soc", 100)),
                "eco_mode_enabled": battery_power_mode == 1,
                "winter_mode_enabled": enable_charge_target,
                "winter_mode_target_soc": (
                    int(getattr(inverter, "charge_target_soc", 100))
                    if enable_charge_target
                    else None
                ),
                "discharge_enabled": bool(getattr(inverter, "enable_discharge", False)),
                "charge_enabled": bool(getattr(inverter, "enable_charge", False)),
            },
        }

    try:
        return await asyncio.to_thread(_run)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("read_state failed: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"Inverter communication failed: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    host = os.environ.get("INVERTER_HOST", "").strip()
    if not host:
        raise RuntimeError("INVERTER_HOST environment variable is required")
    logger.info("GivEnergy Control API starting — inverter: %s", host)
    yield
    logger.info("GivEnergy Control API stopped")


app = FastAPI(
    title="GivEnergy Control API",
    description="Control a GivEnergy inverter via local Modbus TCP.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Charge slot endpoints
# ---------------------------------------------------------------------------

@app.put(
    "/slots/charge/{slot}",
    summary="Set charge slot start and end times",
    tags=["Charge Slots"],
)
async def set_charge_slot(
    slot: int = Path(..., ge=1, le=2, description="Slot number (1 or 2)"),
    body: TimeSlotRequest = ...,
):
    times = body.as_times()
    if slot == 1:
        await _execute("set_charge_slot_1", lambda c: c.set_charge_slot_1(times))
    else:
        await _execute("set_charge_slot_2", lambda c: c.set_charge_slot_2(times))
    return {"slot": slot, "start": body.start, "end": body.end}


@app.delete(
    "/slots/charge/{slot}",
    summary="Clear (disable) a charge slot",
    tags=["Charge Slots"],
)
async def reset_charge_slot(
    slot: int = Path(..., ge=1, le=2, description="Slot number (1 or 2)"),
):
    if slot == 1:
        await _execute("reset_charge_slot_1", lambda c: c.reset_charge_slot_1())
    else:
        await _execute("reset_charge_slot_2", lambda c: c.reset_charge_slot_2())
    return {"slot": slot, "cleared": True}


@app.get(
    "/slots/charge/{slot}",
    summary="Get charge slot current state",
    tags=["Charge Slots"],
)
async def get_charge_slot(
    slot: int = Path(..., ge=1, le=2, description="Slot number (1 or 2)"),
):
    state = await _read_state()
    slot_state = state["charge_slots"][str(slot)]
    return {"slot": slot, **slot_state}


# ---------------------------------------------------------------------------
# Discharge slot endpoints
# ---------------------------------------------------------------------------

@app.put(
    "/slots/discharge/{slot}",
    summary="Set discharge slot start and end times",
    tags=["Discharge Slots"],
)
async def set_discharge_slot(
    slot: int = Path(..., ge=1, le=2, description="Slot number (1 or 2)"),
    body: TimeSlotRequest = ...,
):
    times = body.as_times()
    if slot == 1:
        await _execute("set_discharge_slot_1", lambda c: c.set_discharge_slot_1(times))
    else:
        await _execute("set_discharge_slot_2", lambda c: c.set_discharge_slot_2(times))
    return {"slot": slot, "start": body.start, "end": body.end}


@app.delete(
    "/slots/discharge/{slot}",
    summary="Clear (disable) a discharge slot",
    tags=["Discharge Slots"],
)
async def reset_discharge_slot(
    slot: int = Path(..., ge=1, le=2, description="Slot number (1 or 2)"),
):
    if slot == 1:
        await _execute("reset_discharge_slot_1", lambda c: c.reset_discharge_slot_1())
    else:
        await _execute("reset_discharge_slot_2", lambda c: c.reset_discharge_slot_2())
    return {"slot": slot, "cleared": True}


@app.get(
    "/slots/discharge/{slot}",
    summary="Get discharge slot current state",
    tags=["Discharge Slots"],
)
async def get_discharge_slot(
    slot: int = Path(..., ge=1, le=2, description="Slot number (1 or 2)"),
):
    state = await _read_state()
    slot_state = state["discharge_slots"][str(slot)]
    return {"slot": slot, **slot_state}


# ---------------------------------------------------------------------------
# Battery SoC limit endpoints
# ---------------------------------------------------------------------------

@app.put(
    "/battery/soc-reserve",
    summary="Set minimum battery SoC reserve (shallow charge)",
    description="Sets the minimum SoC the battery will discharge to before stopping. Range: 4-100%.",
    tags=["Battery"],
)
async def set_soc_reserve(body: SoCPercentRequest):
    await _execute("set_shallow_charge", lambda c: c.set_shallow_charge(body.percent))
    return {"soc_reserve_percent": body.percent}


@app.put(
    "/battery/charge-limit",
    summary="Set battery charge power limit",
    description="Sets the charge power limit as a percentage of maximum (0-50%). 50% ≈ 2.6 kW.",
    tags=["Battery"],
)
async def set_charge_limit(body: PowerLimitRequest):
    await _execute("set_battery_charge_limit", lambda c: c.set_battery_charge_limit(body.percent))
    return {"charge_limit_percent": body.percent}


@app.put(
    "/battery/discharge-limit",
    summary="Set battery discharge power limit",
    description="Sets the discharge power limit as a percentage of maximum (0-50%). 50% ≈ 2.6 kW.",
    tags=["Battery"],
)
async def set_discharge_limit(body: PowerLimitRequest):
    await _execute(
        "set_battery_discharge_limit",
        lambda c: c.set_battery_discharge_limit(body.percent),
    )
    return {"discharge_limit_percent": body.percent}


@app.put(
    "/battery/target-soc",
    summary="Set battery target SoC",
    description="Sets the target SoC the battery charges up to. Range: 4-100%.",
    tags=["Battery"],
)
async def set_target_soc(body: SoCPercentRequest):
    await _execute("set_battery_target_soc", lambda c: c.set_battery_target_soc(body.percent))
    return {"target_soc_percent": body.percent}


@app.get(
    "/battery/soc-reserve",
    summary="Get minimum battery SoC reserve",
    tags=["Battery"],
)
async def get_soc_reserve():
    state = await _read_state()
    return {"soc_reserve_percent": state["battery"]["soc_reserve_percent"]}


@app.get(
    "/battery/charge-limit",
    summary="Get battery charge power limit",
    tags=["Battery"],
)
async def get_charge_limit():
    state = await _read_state()
    return {"charge_limit_percent": state["battery"]["charge_limit_percent"]}


@app.get(
    "/battery/discharge-limit",
    summary="Get battery discharge power limit",
    tags=["Battery"],
)
async def get_discharge_limit_value():
    state = await _read_state()
    return {"discharge_limit_percent": state["battery"]["discharge_limit_percent"]}


@app.get(
    "/battery/target-soc",
    summary="Get battery target SoC",
    tags=["Battery"],
)
async def get_target_soc():
    state = await _read_state()
    return {"target_soc_percent": state["battery"]["target_soc_percent"]}


# ---------------------------------------------------------------------------
# Mode endpoints
# ---------------------------------------------------------------------------

@app.put(
    "/battery/eco-mode",
    summary="Enable or disable eco mode",
    description=(
        "Eco mode (demand): battery discharges only to meet house load, avoiding grid export. "
        "Disabled (max power): battery discharges at full power, exporting surplus to grid."
    ),
    tags=["Battery"],
)
async def set_eco_mode(body: EnabledRequest):
    if body.enabled:
        await _execute(
            "set_battery_discharge_mode_demand",
            lambda c: c.set_battery_discharge_mode_demand(),
        )
    else:
        await _execute(
            "set_battery_discharge_mode_max_power",
            lambda c: c.set_battery_discharge_mode_max_power(),
        )
    return {"eco_mode_enabled": body.enabled}


@app.get(
    "/battery/eco-mode",
    summary="Get eco mode state",
    tags=["Battery"],
)
async def get_eco_mode():
    state = await _read_state()
    return {"eco_mode_enabled": state["battery"]["eco_mode_enabled"]}


@app.put(
    "/battery/winter-mode",
    summary="Enable or disable winter mode (charge target SoC)",
    description=(
        "Winter mode stops charging once the battery reaches the target SoC. "
        "target_soc is required when enabled=true."
    ),
    tags=["Battery"],
)
async def set_winter_mode(body: WinterModeRequest):
    if body.enabled:
        soc = body.target_soc
        await _execute("enable_charge_target", lambda c: c.enable_charge_target(soc))
    else:
        await _execute("disable_charge_target", lambda c: c.disable_charge_target())
    return {"winter_mode_enabled": body.enabled, "target_soc": body.target_soc}


@app.get(
    "/battery/winter-mode",
    summary="Get winter mode state",
    tags=["Battery"],
)
async def get_winter_mode():
    state = await _read_state()
    return {
        "winter_mode_enabled": state["battery"]["winter_mode_enabled"],
        "target_soc": state["battery"]["winter_mode_target_soc"],
    }


@app.put(
    "/battery/discharge",
    summary="Enable or disable battery discharge",
    description="When disabled the battery will not discharge regardless of mode or slots.",
    tags=["Battery"],
)
async def set_discharge_enabled(body: EnabledRequest):
    if body.enabled:
        await _execute("enable_discharge", lambda c: c.enable_discharge())
    else:
        await _execute("disable_discharge", lambda c: c.disable_discharge())
    return {"discharge_enabled": body.enabled}


@app.get(
    "/battery/discharge",
    summary="Get battery discharge enable state",
    tags=["Battery"],
)
async def get_discharge_enabled():
    state = await _read_state()
    return {"discharge_enabled": state["battery"]["discharge_enabled"]}


@app.put(
    "/battery/charge",
    summary="Enable or disable battery charging (smart charge)",
    description="When disabled the battery will not charge regardless of mode or slots.",
    tags=["Battery"],
)
async def set_charge_enabled(body: EnabledRequest):
    if body.enabled:
        await _execute("enable_charge", lambda c: c.enable_charge())
    else:
        await _execute("disable_charge", lambda c: c.disable_charge())
    return {"charge_enabled": body.enabled}


@app.get(
    "/battery/charge",
    summary="Get battery charge (smart charge) enable state",
    tags=["Battery"],
)
async def get_charge_enabled():
    state = await _read_state()
    return {"charge_enabled": state["battery"]["charge_enabled"]}


@app.get(
    "/state",
    summary="Get full current control state",
    description="Returns charge/discharge slots and battery control flags/limits.",
    tags=["State"],
)
async def get_full_state():
    return await _read_state()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    import uvicorn

    uvicorn.run(
        "givenergy_control:app",
        host="0.0.0.0",
        port=int(os.environ.get("API_PORT", "8000")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
