"""Plugins package

This package contains all plugin implementations for XAgent.
Each plugin is a module with a plugin.py file that defines a plugin class.

Plugin Types:
- delivery: Message delivery plugins (email, webhook)
- filter: Data filtering plugins (dedup, rename, scale)
- north: North-bound communication plugins (mqtt_client, xnc_client)
- rule: Rule engine plugins (expression, threshold)
- south: South-bound device plugins (bacnet, knx, modbus)
"""

ALL_PLUGINS = [
    'xagent.plugins.delivery.action.plugin',
    'xagent.plugins.delivery.email.plugin',
    'xagent.plugins.delivery.system.plugin',
    'xagent.plugins.delivery.webhook.plugin',
    'xagent.plugins.filter.dedup.plugin',
    'xagent.plugins.filter.rename.plugin',
    'xagent.plugins.filter.scale.plugin',
    'xagent.plugins.north.mqtt_client.plugin',
    'xagent.plugins.north.xnc_client.plugin',
    'xagent.plugins.rule.expression.plugin',
    'xagent.plugins.rule.schedule.plugin',
    'xagent.plugins.rule.threshold.plugin',
    'xagent.plugins.south.bacnet.plugin',
    'xagent.plugins.south.knx.plugin',
    'xagent.plugins.south.modbus.rtu.plugin',
    'xagent.plugins.south.modbus.tcp.plugin',
]

__all__ = ['ALL_PLUGINS']
