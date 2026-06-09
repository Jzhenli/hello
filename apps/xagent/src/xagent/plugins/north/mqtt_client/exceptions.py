"""MQTT适配器异常层次

设计原则：
- 顶层 MQTTAdapterError：所有适配器异常的基类
- DataConversionError：数据转换失败（上行）
- TopicError：Topic相关错误（模板缺失、格式化失败）
- CommandParseError：命令解析失败（下行）
"""


class MQTTAdapterError(Exception):
    """适配器异常基类"""
    pass


class DataConversionError(MQTTAdapterError):
    """数据转换失败"""
    pass


class TopicError(MQTTAdapterError):
    """Topic相关错误"""
    pass


class CommandParseError(MQTTAdapterError):
    """命令解析失败"""
    pass
