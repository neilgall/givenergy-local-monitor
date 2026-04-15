# GiveNergy Prometheus Exporter

A Prometheus exporter for GiveNergy inverter metrics via Modbus TCP.

## Features

- **Real-time Monitoring**: Collects inverter metrics at configurable intervals
- **Modbus TCP Support**: Connects to GiveNergy inverters via Modbus TCP protocol
- **Prometheus Integration**: Exposes metrics in Prometheus format
- **Comprehensive Metrics**: 
  - AC Power and Frequency
  - PV Power, Voltage, and Current
  - Battery Power, Voltage, Current, SOC, and Temperature
  - Inverter Temperature
  - Connection Status and Error Tracking

## Prerequisites

- Python 3.8+
- Network access to GiveNergy inverter via TCP/IP

## Installation

### Using uv (Recommended)

1. Install [uv](https://github.com/astral-sh/uv):
```bash
pip install uv
```

2. Clone the repository:
```bash
cd /Users/neilgall/Projects/prometheus-givenergy
```

3. Install the project with dependencies:
```bash
uv sync
```

For development with additional tools:
```bash
uv sync --all-extras
```

### Using pip (Alternative)

1. Clone the repository:
```bash
cd /Users/neilgall/Projects/prometheus-givenergy
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install the project:
```bash
pip install -e .
```

## Configuration

Edit `config.yaml` to configure:

- **Inverter Settings**:
  - `host`: IP address of the GiveNergy inverter
  - `port`: Modbus TCP port (typically 502)
  - `unit_id`: Modbus unit ID (typically 1)
  - `timeout`: Connection timeout in seconds
  - `poll_interval`: Metric collection interval in seconds

- **Prometheus Settings**:
  - `port`: Port to expose metrics on (default: 9100)
  - `address`: Bind address (default: 0.0.0.0)

Example:
```yaml
inverter:
  host: "192.168.1.100"
  port: 502
  unit_id: 1
  timeout: 10
  poll_interval: 30

prometheus:
  port: 9100
  address: "0.0.0.0"
```

## Usage

### Run Locally

Using uv:
```bash
uv run givenergy_exporter.py
```

Or directly with Python:
```bash
python3 givenergy_exporter.py
```

The exporter will start collecting metrics and expose them on the configured Prometheus port. You can access the metrics at:
```
http://localhost:9100/metrics
```

### Example Prometheus Configuration

Add to your `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'givenergy'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 30s
```

## Metrics

All metrics are prefixed with `givenergy_`:

| Metric | Description | Unit |
|--------|-------------|------|
| `power_watts` | Current AC power output | W |
| `ac_frequency_hz` | AC frequency | Hz |
| `grid_voltage_volts` | Grid voltage | V |
| `pv_power_watts` | Current PV power input | W |
| `pv_voltage_volts` | PV voltage | V |
| `pv_current_amps` | PV current | A |
| `battery_power_watts` | Battery power (positive=discharge) | W |
| `battery_voltage_volts` | Battery voltage | V |
| `battery_current_amps` | Battery current | A |
| `battery_soc_percent` | Battery state of charge | % |
| `battery_temperature_celsius` | Battery temperature | °C |
| `inverter_temperature_celsius` | Inverter temperature | °C |
| `inverter_status` | Inverter status code | - |
| `read_errors_total` | Total number of read errors | - |
| `reads_total` | Total number of successful reads | - |
| `last_update_timestamp_seconds` | Timestamp of last successful update | s |

## Troubleshooting

### Connection Issues

1. Verify the inverter IP address and port are correct
2. Ensure network connectivity: `ping 192.168.1.100`
3. Check firewall rules allow Modbus TCP (port 502)

### No Metrics Appearing

1. Check logs for error messages
2. Verify the Modbus unit ID matches inverter configuration
3. Ensure the inverter is accessible on the network

### Register Address Verification

GiveNergy inverters may use different register addresses. If metrics are not appearing:

1. Use a Modbus TCP client tool to scan available registers
2. Update the `REGISTERS` dictionary in `givenergy_exporter.py` with correct addresses
3. Consult GiveNergy documentation for your specific inverter model

## Development

Install development dependencies:
```bash
uv sync --all-extras
```

Run tests:
```bash
pytest
```

Code formatting and linting:
```bash
black givenergy_exporter.py
ruff check givenergy_exporter.py
mypy givenergy_exporter.py
```

## Running as a Service

### Systemd Service

Copy the example service file and customize it:
```bash
sudo cp systemd-service.example /etc/systemd/system/givenergy-exporter.service
sudo systemctl daemon-reload
sudo systemctl enable givenergy-exporter
sudo systemctl start givenergy-exporter
```

Monitor the service:
```bash
sudo journalctl -u givenergy-exporter -f
```

## Docker Deployment

### Docker Compose (Recommended)

```bash
docker-compose up -d
```

This runs both the exporter and Prometheus for testing.

### Docker Build and Run

```bash
docker build -t givenergy-exporter .
docker run -p 9100:9100 -v $(pwd)/config.yaml:/app/config.yaml givenergy-exporter
```

## License

MIT

## Support

For issues or questions, please check the GiveNergy inverter documentation and Modbus protocol specifications.
