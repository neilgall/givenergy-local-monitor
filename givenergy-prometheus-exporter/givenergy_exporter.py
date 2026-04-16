#!/usr/bin/env python3
"""
GiveNergy Inverter Prometheus Exporter

Exports metrics from GiveNergy inverters via Modbus TCP to Prometheus.
"""

import logging
import os
import time
from typing import Any, Dict, Optional
from prometheus_client import start_http_server, Gauge, Counter
from givenergy_modbus.client import GivEnergyClient
from givenergy_modbus.model.plant import Plant

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("givenergy_modbus").setLevel(logging.WARNING)  # Suppress verbose library logs


class GiveEnergyExporter:
    """Exports GiveNergy inverter metrics to Prometheus."""

    INVERTER_STATUS_LABELS = {
        0: 'WAITING',
        1: 'NORMAL',
        2: 'WARNING',
        3: 'FAULT',
        4: 'FLASH_FW_UPDATE',
    }

    # Scalar metrics mapped to decoded givenergy-modbus inverter model attributes.
    # Format: metric_key: (inverter_attribute, metric_name, description)
    SCALAR_METRICS_MAP = {
        # Grid
        'grid_power': ('p_grid_out', 'givenergy_power_grid_power', 'Grid power (+ = export, - = import)'),
        'grid_voltage': ('v_ac1', 'givenergy_power_grid_voltage', 'Grid voltage'),
        'grid_current': ('i_grid_port', 'givenergy_power_grid_current', 'Grid output current'),
        'grid_frequency': ('f_ac1', 'givenergy_power_grid_frequency', 'Grid frequency'),

        # Consumption
        'consumption_power': ('p_load_demand', 'givenergy_power_consumption_power', 'House load/consumption power'),

        # Battery
        'battery_power': ('p_battery', 'givenergy_power_battery_power', 'Battery power (+ = discharge, - = charge)'),
        'battery_percent': ('battery_percent', 'givenergy_power_battery_percent', 'Battery state of charge percentage'),
        'battery_temperature': ('temp_battery', 'givenergy_power_battery_temperature', 'Battery pack temperature'),

        # Inverter
        'inverter_temperature': (
            'temp_inverter_heatsink',
            'givenergy_power_inverter_temperature',
            'Inverter heatsink temperature',
        ),
        'inverter_power': ('p_inverter_out', 'givenergy_power_inverter_power', 'Inverter AC output power'),
        'inverter_output_voltage': (
            'v_eps_backup',
            'givenergy_power_inverter_output_voltage',
            'Inverter output voltage',
        ),
        'inverter_output_frequency': (
            'f_eps_backup',
            'givenergy_power_inverter_output_frequency',
            'Inverter output frequency',
        ),
        'inverter_eps_power': (
            'p_eps_backup',
            'givenergy_power_inverter_eps_power',
            'Inverter EPS backup power',
        ),

        # Day counters
        'today_ac_charge': ('e_inverter_in_day', 'givenergy_today_ac_charge', 'AC charge energy today'),
        'today_battery_charge': (
            'e_battery_charge_day',
            'givenergy_today_battery_charge',
            'Battery charge energy today',
        ),
        'today_battery_discharge': (
            'e_battery_discharge_day',
            'givenergy_today_battery_discharge',
            'Battery discharge energy today',
        ),
        'today_grid_export': ('e_grid_out_day', 'givenergy_today_grid_export', 'Grid export energy today'),
        'today_grid_import': ('e_grid_in_day', 'givenergy_today_grid_import', 'Grid import energy today'),

        # Lifetime counters
        'total_ac_charge': ('e_inverter_in_total', 'givenergy_total_ac_charge', 'AC charge energy total'),
        'total_battery_charge': (
            'e_battery_charge_total',
            'givenergy_total_battery_charge',
            'Battery charge energy total',
        ),
        'total_battery_discharge': (
            'e_battery_discharge_total',
            'givenergy_total_battery_discharge',
            'Battery discharge energy total',
        ),
        'total_grid_export': ('e_grid_out_total', 'givenergy_total_grid_export', 'Grid export energy total'),
        'total_grid_import': ('e_grid_in_total', 'givenergy_total_grid_import', 'Grid import energy total'),
    }

    # PV array metrics expose the same names/labels used by the backfilled OpenMetrics.
    # Format: metric_key: (attr1, attr2, metric_name, description)
    ARRAY_METRICS_MAP = {
        'solar_arrays_power': ('p_pv1', 'p_pv2', 'givenergy_power_solar_arrays_power', 'PV array power'),
        'solar_arrays_voltage': ('v_pv1', 'v_pv2', 'givenergy_power_solar_arrays_voltage', 'PV array voltage'),
        'solar_arrays_current': ('i_pv1', 'i_pv2', 'givenergy_power_solar_arrays_current', 'PV array current'),
    }

    def __init__(self):
        """Initialize the exporter with environment configuration."""
        self.config = self._load_config_from_env()
        self.client: Optional[GivEnergyClient] = None
        self.plant: Optional[Plant] = None
        self.metrics: Dict = {}
        self._setup_metrics()
        
    @staticmethod
    def _get_env_int(name: str, default: int) -> int:
        """Read an integer environment variable with validation."""
        value = os.environ.get(name)
        if value is None or value == "":
            return default

        try:
            return int(value)
        except ValueError as e:
            raise ValueError(f"Environment variable {name} must be an integer") from e

    def _load_config_from_env(self) -> dict:
        """Load configuration from environment variables."""
        inverter_host = os.environ.get("INVERTER_HOST", "").strip()
        if not inverter_host:
            raise ValueError("Environment variable INVERTER_HOST is required")

        return {
            "inverter": {
                "host": inverter_host,
                "port": self._get_env_int("INVERTER_PORT", 8899),
                "poll_interval": self._get_env_int("POLL_INTERVAL", 30),
            },
            "prometheus": {
                "port": self._get_env_int("PROMETHEUS_PORT", 9100),
                "address": os.environ.get("PROMETHEUS_ADDRESS", "0.0.0.0"),
            },
        }

    def _setup_metrics(self):
        """Set up Prometheus metrics."""
        self.metrics['read_errors'] = Counter(
            'givenergy_read_errors_total',
            'Total number of read errors'
        )
        self.metrics['read_success'] = Counter(
            'givenergy_reads_total',
            'Total number of successful reads'
        )
        self.metrics['last_update_timestamp'] = Gauge(
            'givenergy_last_update_timestamp_seconds',
            'Timestamp of last successful update'
        )

        # Create gauges for scalar metrics.
        for metric_key, (_, metric_name, description) in self.SCALAR_METRICS_MAP.items():
            self.metrics[metric_key] = Gauge(
                metric_name,
                description
            )

        # Total solar power to match JSON/OpenMetrics backfill naming.
        self.metrics['solar_power_total'] = Gauge(
            'givenergy_power_solar_power',
            'Total PV solar power across arrays'
        )
        self.metrics['today_solar'] = Gauge(
            'givenergy_today_solar',
            'Solar generation energy today'
        )
        self.metrics['today_consumption'] = Gauge(
            'givenergy_today_consumption',
            'House consumption energy today'
        )
        self.metrics['total_solar'] = Gauge(
            'givenergy_total_solar',
            'Solar generation energy total'
        )
        self.metrics['total_consumption'] = Gauge(
            'givenergy_total_consumption',
            'House consumption energy total'
        )
        self.metrics['is_metered'] = Gauge(
            'givenergy_is_metered',
            'Whether the inverter has metered readings available'
        )
        self.metrics['status'] = Gauge(
            'givenergy_status',
            'Current inverter status',
            labelnames=('status',),
        )

        # Create gauges for array metrics with an "array" label.
        for metric_key, (_, _, metric_name, description) in self.ARRAY_METRICS_MAP.items():
            self.metrics[metric_key] = Gauge(
                metric_name,
                description,
                labelnames=('array',),
            )

    def _connect(self):
        """Initialize the givenergy-modbus client and plant model."""
        inverter_config = self.config['inverter']
        try:
            client = GivEnergyClient(host=inverter_config['host'])
            plant = Plant(number_batteries=1)
            # Probe the connection with a full refresh.
            client.refresh_plant(plant, full_refresh=True)
            self.client = client
            self.plant = plant
            logger.info(
                f"Connected to inverter at "
                f"{inverter_config['host']}:{inverter_config['port']}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to inverter: {e}")
            return False

    def _disconnect(self):
        """Disconnect from the client."""
        self.client = None
        self.plant = None
        logger.info("Disconnected from inverter")

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        """Convert known scalar values to float for Prometheus gauges."""
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def collect_metrics(self):
        """Collect metrics from the inverter."""
        # Check if client is initialized, reconnect if needed
        if not self.client or not self.plant:
            logger.debug("Client not connected, attempting to connect...")
            if not self._connect():
                self.metrics['read_errors'].inc()
                return

        try:
            logger.debug("Collecting metrics from inverter")

            assert self.client is not None
            assert self.plant is not None
            self.client.refresh_plant(self.plant, full_refresh=False)
            inverter = self.plant.inverter

            def inverter_value(field_name: str) -> Optional[float]:
                return self._as_float(getattr(inverter, field_name, None))

            for metric_key, (field_name, metric_name, _) in self.SCALAR_METRICS_MAP.items():
                value = inverter_value(field_name)
                if value is not None:
                    self.metrics[metric_key].set(value)
                    logger.debug(f"{metric_key}={value} ({metric_name})")
                else:
                    logger.debug(f"Skipping {metric_key}, unavailable field: {field_name}")

            # Derived total PV power to match givenergy_power_solar_power.
            pv1_power = inverter_value('p_pv1')
            pv2_power = inverter_value('p_pv2')
            if pv1_power is not None and pv2_power is not None:
                self.metrics['solar_power_total'].set(pv1_power + pv2_power)

            pv1_day = inverter_value('e_pv1_day')
            pv2_day = inverter_value('e_pv2_day')
            if pv1_day is not None and pv2_day is not None:
                today_solar = pv1_day + pv2_day
                self.metrics['today_solar'].set(today_solar)
            else:
                today_solar = None

            total_solar = inverter_value('e_pv_total')
            if total_solar is not None:
                self.metrics['total_solar'].set(total_solar)

            today_grid_import = inverter_value('e_grid_in_day')
            today_grid_export = inverter_value('e_grid_out_day')
            today_battery_charge = inverter_value('e_battery_charge_day')
            today_battery_discharge = inverter_value('e_battery_discharge_day')
            if all(
                value is not None
                for value in (
                    today_solar,
                    today_grid_import,
                    today_grid_export,
                    today_battery_charge,
                    today_battery_discharge,
                )
            ):
                today_consumption = (
                    today_solar
                    + today_grid_import
                    + today_battery_discharge
                    - today_grid_export
                    - today_battery_charge
                )
                self.metrics['today_consumption'].set(today_consumption)

            total_grid_import = inverter_value('e_grid_in_total')
            total_grid_export = inverter_value('e_grid_out_total')
            total_battery_charge = inverter_value('e_battery_charge_total')
            total_battery_discharge = inverter_value('e_battery_discharge_total')
            if all(
                value is not None
                for value in (
                    total_solar,
                    total_grid_import,
                    total_grid_export,
                    total_battery_charge,
                    total_battery_discharge,
                )
            ):
                total_consumption = (
                    total_solar
                    + total_grid_import
                    + total_battery_discharge
                    - total_grid_export
                    - total_battery_charge
                )
                self.metrics['total_consumption'].set(total_consumption)

            # The cloud API includes an is_metered boolean; modbus does not expose an exact equivalent.
            # Expose this family as a constant so live and backfilled series align.
            self.metrics['is_metered'].set(1.0)

            inverter_status_code = getattr(inverter, 'inverter_status', None)
            for status_label in self.INVERTER_STATUS_LABELS.values():
                self.metrics['status'].labels(status=status_label).set(0.0)
            resolved_status = self.INVERTER_STATUS_LABELS.get(inverter_status_code, 'UNKNOWN')
            self.metrics['status'].labels(status=resolved_status).set(1.0)

            # Per-array gauges labelled with array="1" and array="2".
            for metric_key, (field_one, field_two, metric_name, _) in self.ARRAY_METRICS_MAP.items():
                value_one = inverter_value(field_one)
                value_two = inverter_value(field_two)

                if value_one is not None:
                    self.metrics[metric_key].labels(array='1').set(value_one)
                    logger.debug(f"{metric_key}[array=1]={value_one} ({metric_name})")
                else:
                    logger.debug(f"Skipping {metric_key}[array=1], unavailable field: {field_one}")

                if value_two is not None:
                    self.metrics[metric_key].labels(array='2').set(value_two)
                    logger.debug(f"{metric_key}[array=2]={value_two} ({metric_name})")
                else:
                    logger.debug(f"Skipping {metric_key}[array=2], unavailable field: {field_two}")

            self.metrics['last_update_timestamp'].set(time.time())
            self.metrics['read_success'].inc()
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            self.metrics['read_errors'].inc()
            self._disconnect()

    def run(self):
        """Run the exporter."""
        prometheus_config = self.config['prometheus']
        poll_interval = self.config['inverter']['poll_interval']
        
        # Start Prometheus HTTP server
        logger.info(f"Starting Prometheus exporter on {prometheus_config['address']}:{prometheus_config['port']}")
        start_http_server(
            port=prometheus_config['port'],
            addr=prometheus_config['address']
        )
        
        # Main collection loop
        try:
            logger.info("Exporter started, collecting metrics...")
            while True:
                self.collect_metrics()
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self._disconnect()


def main():
    """Main entry point."""
    try:
        exporter = GiveEnergyExporter()
        exporter.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)


if __name__ == '__main__':
    main()
