#!/usr/bin/env python3
"""
GiveNergy Inverter Prometheus Exporter

Exports metrics from GiveNergy inverters via Modbus TCP to Prometheus.
"""

import logging
import os
import time
import yaml
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

    # Metrics mapped to decoded givenergy-modbus inverter model attributes
    # Format: metric_key: (inverter_attribute, metric_name, description)
    METRICS_MAP = {
        # PV (Solar) Power
        'pv1_power': ('p_pv1', 'pv1_power_watts', 'PV string 1 power output'),
        'pv2_power': ('p_pv2', 'pv2_power_watts', 'PV string 2 power output'),

        # PV Voltages
        'pv1_voltage': ('v_pv1', 'pv1_voltage_volts', 'PV string 1 voltage'),
        'pv2_voltage': ('v_pv2', 'pv2_voltage_volts', 'PV string 2 voltage'),

        # PV Currents
        'pv1_current': ('i_pv1', 'pv1_current_amps', 'PV string 1 input current'),
        'pv2_current': ('i_pv2', 'pv2_current_amps', 'PV string 2 input current'),

        # Grid
        'grid_power': ('p_grid_out', 'grid_power_watts', 'Grid power (+ = export, - = import)'),
        'grid_voltage': ('v_ac1', 'grid_voltage_volts', 'Grid voltage'),
        'grid_current': ('i_grid_port', 'grid_current_amps', 'Grid output current'),
        'grid_frequency': ('f_ac1', 'grid_frequency_hz', 'Grid frequency'),

        # Load/Consumption
        'load_power': ('p_load_demand', 'load_power_watts', 'House load/consumption power'),

        # Battery
        'battery_power': ('p_battery', 'battery_power_watts', 'Battery power (+ = discharge, - = charge)'),
        'battery_voltage': ('v_battery', 'battery_voltage_volts', 'Battery pack voltage'),
        'battery_current': ('i_battery', 'battery_current_amps', 'Battery current (+ = discharge, - = charge)'),
        'battery_soc': ('battery_percent', 'battery_soc_percent', 'Battery state of charge percentage'),

        # Temperatures
        'inverter_temperature': (
            'temp_inverter_heatsink',
            'inverter_temperature_celsius',
            'Inverter heatsink temperature',
        ),
        'battery_temperature': ('temp_battery', 'battery_temperature_celsius', 'Battery pack temperature'),

        # System State
        'system_mode': ('system_mode', 'system_mode', 'Current operating mode'),
        'charge_status': ('charge_status', 'battery_charge_status', 'Battery charging status'),
        'inverter_status': ('inverter_status', 'inverter_status', 'System operational status'),
    }

    def __init__(self, config_file: str = 'config.yaml'):
        """Initialize the exporter with configuration."""
        self.config = self._load_config(config_file)
        self.client: Optional[GivEnergyClient] = None
        self.plant: Optional[Plant] = None
        self.metrics: Dict = {}
        self._setup_metrics()
        
    def _load_config(self, config_file: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_file}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            raise

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
        
        # Create gauges for all metrics
        for metric_key, (_, metric_name, description) in self.METRICS_MAP.items():
            self.metrics[metric_key] = Gauge(
                f'givenergy_{metric_name}',
                description
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

            for metric_key, (field_name, metric_name, _) in self.METRICS_MAP.items():
                raw_value = getattr(inverter, field_name, None)
                value = self._as_float(raw_value)
                if value is not None:
                    self.metrics[metric_key].set(value)
                    logger.debug(f"{metric_key}={value} ({metric_name})")
                else:
                    logger.debug(f"Skipping {metric_key}, unavailable field: {field_name}")

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
        exporter = GiveEnergyExporter('config.yaml')
        exporter.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)


if __name__ == '__main__':
    main()
