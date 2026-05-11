# Default Configuration Templates

This directory contains default configuration templates that will be copied to the user configuration directory on first run.

## Directory Structure

```
resources/
├── config/
│   ├── config.yaml          # Main configuration template
│   ├── plugins/             # Plugin default configuration templates
│   │   ├── modbus_tcp.yaml  # Modbus TCP plugin template
│   │   ├── bacnet.yaml      # BACnet plugin template
│   │   ├── knx.yaml         # KNX plugin template
│   │   └── mqtt_client.yaml # MQTT client plugin template
│   └── devices/             # Example device configurations
│       ├── example_modbus_device.yaml
│       └── example_mqtt_north.yaml
└── static/                  # Static web files
```

## How It Works

1. On first run, the application checks if the user configuration directory exists
2. If not, it copies these default templates to the user configuration directory
3. Users can then modify the copied files to customize their setup

## User Configuration Directory

The default user configuration directory location depends on the operating system:

| OS | Path |
|----|------|
| Windows | `C:\Users\<username>\AppData\Roaming\adveco\XAgent\config\` |
| macOS | `~/Library/Application Support/XAgent/config/` |
| Linux | `~/.config/XAgent/config/` |

## Adding New Plugin Templates

To add a new plugin template:

1. Create a YAML file in `resources/config/plugins/` directory
2. Define the plugin name, type, version, and default configuration
3. The template will be automatically copied on first run

Example:

```yaml
name: my_plugin
type: south
version: "1.0.0"
description: "My Custom Plugin"
enabled: true

defaults:
  host: "127.0.0.1"
  port: 8080

capabilities:
  - read
  - write
```
