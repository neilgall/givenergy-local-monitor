# GivEnergy Prometheus Exporter

A Prometheus exporter for GivEnergy inverter metrics via Modbus TCP.

## Features

- Real-time metric collection at a configurable interval
- Connects to GivEnergy inverters directly via Modbus TCP
- Metric names are aligned with the GivEnergy Cloud API data structure, enabling seamless joining of live data with historical backfill data

## Prerequisites

- Python 3.12+
- Network access to the GivEnergy inverter on port 8899 (Modbus TCP)

## Installation

```bash
uv sync
```

For development tools:
```bash
uv sync --all-extras
```

## Configuration

All configuration is via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INVERTER_HOST` | yes | — | IP address or hostname of the inverter |
| `INVERTER_PORT` | no | `8899` | Modbus TCP port |
| `POLL_INTERVAL` | no | `30` | Metric collection interval in seconds |
| `PROMETHEUS_PORT` | no | `9100` | Port to expose metrics on |
| `PROMETHEUS_ADDRESS` | no | `0.0.0.0` | Bind address for the metrics server |

## Usage

### Run Locally

```bash
INVERTER_HOST=192.168.1.100 uv run givenergy_exporter.py
```

Metrics are available at `http://localhost:9100/metrics`.

### Example Prometheus Configuration

```yaml
scrape_configs:
  - job_name: 'givenergy'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 30s
```

### Docker Compose

```bash
docker-compose up -d
```

### Systemd Service

```bash
sudo cp systemd-service.example /etc/systemd/system/givenergy-exporter.service
sudo systemctl daemon-reload
sudo systemctl enable --now givenergy-exporter
sudo journalctl -u givenergy-exporter -f
```

## Metrics

All metrics are prefixed with `givenergy_`. Metric names mirror the GivEnergy Cloud API JSON structure so that live and backfilled data share the same series names in Prometheus.

### Instantaneous power

| Metric | Labels | Description | Unit |
|--------|--------|-------------|------|
| `givenergy_power_solar_power` | — | Total PV solar power | W |
| `givenergy_power_solar_arrays_power` | `array` | Per-array PV power | W |
| `givenergy_power_solar_arrays_voltage` | `array` | Per-array PV voltage | V |
| `givenergy_power_solar_arrays_current` | `array` | Per-array PV current | A |
| `givenergy_power_grid_power` | — | Grid power (+ export, − import) | W |
| `givenergy_power_grid_voltage` | — | Grid voltage | V |
| `givenergy_power_grid_current` | — | Grid current | A |
| `givenergy_power_grid_frequency` | — | Grid frequency | Hz |
| `givenergy_power_battery_power` | — | Battery power (+ discharge, − charge) | W |
| `givenergy_power_battery_percent` | — | Battery state of charge | % |
| `givenergy_power_battery_temperature` | — | Battery temperature | °C |
| `givenergy_power_consumption_power` | — | House load / consumption | W |
| `givenergy_power_inverter_power` | — | Inverter AC output power | W |
| `givenergy_power_inverter_temperature` | — | Inverter heatsink temperature | °C |
| `givenergy_power_inverter_output_voltage` | — | Inverter output voltage | V |
| `givenergy_power_inverter_output_frequency` | — | Inverter output frequency | Hz |
| `givenergy_power_inverter_eps_power` | — | EPS backup power | W |

### Today energy counters

| Metric | Description | Unit |
|--------|-------------|------|
| `givenergy_today_solar` | Solar generation today | kWh |
| `givenergy_today_consumption` | House consumption today (derived) | kWh |
| `givenergy_today_grid_import` | Grid import today | kWh |
| `givenergy_today_grid_export` | Grid export today | kWh |
| `givenergy_today_battery_charge` | Battery charge today | kWh |
| `givenergy_today_battery_discharge` | Battery discharge today | kWh |
| `givenergy_today_ac_charge` | AC charge today | kWh |

### Lifetime energy counters

| Metric | Description | Unit |
|--------|-------------|------|
| `givenergy_total_solar` | Solar generation lifetime | kWh |
| `givenergy_total_consumption` | House consumption lifetime (derived) | kWh |
| `givenergy_total_grid_import` | Grid import lifetime | kWh |
| `givenergy_total_grid_export` | Grid export lifetime | kWh |
| `givenergy_total_battery_charge` | Battery charge lifetime | kWh |
| `givenergy_total_battery_discharge` | Battery discharge lifetime | kWh |
| `givenergy_total_ac_charge` | AC charge lifetime | kWh |

### Status and housekeeping

| Metric | Labels | Description |
|--------|--------|-------------|
| `givenergy_status` | `status` | Inverter status; value is 1 for the current status label (`WAITING`, `NORMAL`, `WARNING`, `FAULT`, `FLASH_FW_UPDATE`) |
| `givenergy_is_metered` | — | Always 1 (metered readings are available via Modbus) |
| `givenergy_last_update_timestamp_seconds` | — | Unix timestamp of last successful poll |
| `givenergy_reads_total` | — | Total successful reads |
| `givenergy_read_errors_total` | — | Total read errors |

## Troubleshooting

**No metrics appearing**
1. Check that `INVERTER_HOST` is set and the host is reachable from where the exporter runs.
2. Check logs for connection errors.
3. Verify port 8899 is open: `nc -zv 192.168.1.100 8899`

**Metrics missing after restart**
Some modbus fields may not be available on partial register reads. Run with `LOG_LEVEL=DEBUG` to see which fields are skipped.

**Register mismatches**
If your inverter model uses different register addresses, check `GIVENERGY_REGISTER_MAP.md` and confirm the installed `givenergy-modbus` version supports your hardware.

## Development

```bash
uv sync --all-extras
pytest
black givenergy_exporter.py
ruff check givenergy_exporter.py
```

This runs both the exporter and Prometheus for testing.

### Docker Build and Run

```bash
docker build -t givenergy-exporter .
docker run -p 9100:9100 \
  -e INVERTER_HOST=192.168.1.100 \
  -e INVERTER_PORT=8899 \
  -e POLL_INTERVAL=30 \
  -e PROMETHEUS_PORT=9100 \
  -e PROMETHEUS_ADDRESS=0.0.0.0 \
  givenergy-exporter
```

## License

MIT

## Support

For issues or questions, please check the GivEnergy inverter documentation and Modbus protocol specifications.
