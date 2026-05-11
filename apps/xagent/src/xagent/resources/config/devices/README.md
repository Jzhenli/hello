# Example Device Configurations

This directory contains example device configuration files that demonstrate how to configure devices in XAgent.

## Files

- `example_modbus_device.yaml` - Example Modbus TCP south device
- `example_mqtt_north.yaml` - Example MQTT north device for data publishing

## Usage

These example files are copied to the user configuration directory on first run. You can:

1. Use them as templates to create new device configurations
2. Modify them directly to suit your needs
3. Delete them if not needed

## Creating a New Device

### Option 1: Copy and Modify

```bash
cp example_modbus_device.yaml my_device.yaml
# Edit my_device.yaml with your device settings
```

### Option 2: Use REST API

```bash
curl -X POST http://localhost:8080/api/devices/ \
  -H "Content-Type: application/json" \
  -d @my_device.json
```

## Device Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `asset` | Yes | Unique device identifier |
| `name` | No | Human-readable device name |
| `description` | No | Device description |
| `enabled` | No | Whether device is enabled (default: true) |
| `status` | No | Device status: active/inactive/maintenance/error |
| `plugin.name` | Yes | Plugin type to use |
| `plugin.config` | No | Plugin-specific configuration |
| `points` | No | List of data points to collect |
| `metadata` | No | Additional device metadata |
| `tags` | No | Tags for categorization |
