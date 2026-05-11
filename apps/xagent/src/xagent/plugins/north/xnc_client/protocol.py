"""UDP Protocol Codec - Binary protocol encoding/decoding with CRC16-X25"""

import logging
import struct
import threading
import warnings
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


CRC16_X25_TABLE = [
    0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
    0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
    0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
    0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
    0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
    0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
    0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
    0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
    0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
    0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
    0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
    0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
    0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
    0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
    0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
    0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
    0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
    0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
    0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
    0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
    0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
    0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
    0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
    0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
    0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
    0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
    0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
    0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
    0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
    0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
    0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
    0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78
]


def crc16_x25(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc = (crc >> 8) ^ CRC16_X25_TABLE[(crc ^ byte) & 0xFF]
    return (~crc) & 0xFFFF


def crc16_x25_bitwise(data: bytes) -> int:
    """
    [DEPRECATED] CRC16-X25 逐位计算法（教学版本）
    
    此函数仅用于教学目的，生产代码请使用查表版 crc16_x25()。
    
    这个函数展示了CRC计算的核心原理，不使用查表，逐位处理数据。
    虽然速度较慢，但能清晰展示CRC算法的工作过程。
    
    CRC16-X25 参数:
        - 多项式: x^16 + x^12 + x^5 + 1 (正常形式 0x1021)
        - 反射多项式: 0x8408 (位序反转，用于LSB-first算法)
        - 初始值: 0xFFFF
        - 输入反射: 是 (LSB-first，最低位优先处理)
        - 输出反射: 是
        - 最终异或: 0xFFFF (取反)
    
    算法原理:
        CRC本质是多项式除法，将数据视为一个大的二进制多项式，
        除以生成多项式，余数就是CRC校验值。
        
        反射算法(LSB-first)从最低位开始处理:
        1. 将当前字节与CRC寄存器低8位异或
        2. 检查最低位是否为1
        3. 如果为1：右移一位，然后异或多项式
        4. 如果为0：仅右移一位
        5. 重复8次处理完一个字节的所有位
    
    Args:
        data: 待计算CRC的字节数据
        
    Returns:
        16位CRC校验值
        
    Example:
        >>> crc16_x25_bitwise(b'123456789')
        0x906E  # 标准测试向量的预期结果
    """
    warnings.warn(
        "crc16_x25_bitwise() is deprecated for production use. Use crc16_x25() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    POLY = 0x8408
    
    crc = 0xFFFF
    
    for byte in data:
        crc ^= byte
        
        for bit_index in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ POLY
            else:
                crc = crc >> 1
    
    return (~crc) & 0xFFFF


class UDPProtocolCodec:
    """UDP Binary Protocol Codec
    
    Packet Structure:
    | Offset | Length | Field          | Type   | Description                    |
    |--------|--------|----------------|--------|--------------------------------|
    | 0      | 2      | Magic Number   | bytes  | Fixed 0x55AA (big-endian)      |
    | 2      | 2      | Sequence       | uint16 | Sequence number (big-endian)   |
    | 4      | 1      | Command        | uint8  | Command type (currently 9)     |
    | 5      | 1      | Version        | uint8  | Protocol version (currently 2) |
    | 6      | 4      | Payload Length | uint32 | Payload length (big-endian)    |
    | 10     | N      | Payload        | bytes  | Protobuf encoded payload       |
    | 10+N   | 2      | CRC16          | uint16 | CRC16-X25 checksum (big-endian)|
    """
    
    MAGIC_NUMBER = 0x55AA
    HEADER_SIZE = 10
    CURRENT_VERSION = 2
    COMMAND_TYPE = 9
    
    def __init__(self):
        self._sequence = 0
        self._sequence_lock = threading.Lock()
    
    def _get_next_sequence(self) -> int:
        with self._sequence_lock:
            self._sequence = (self._sequence + 1) & 0xFFFF
            return self._sequence
    
    def encode(self, payload: bytes, sequence: Optional[int] = None) -> bytes:
        if sequence is None:
            sequence = self._get_next_sequence()
        
        payload_length = len(payload)
        
        header = struct.pack(
            ">HHBBI",
            self.MAGIC_NUMBER,
            sequence,
            self.COMMAND_TYPE,
            self.CURRENT_VERSION,
            payload_length
        )
        
        header_with_payload = header + payload
        
        crc = crc16_x25(header_with_payload)
        
        packet = header_with_payload + struct.pack(">H", crc)
        
        logger.debug(
            f"Encoded packet: seq={sequence}, payload_len={payload_length}, crc=0x{crc:04X}"
        )
        
        return packet
    
    def decode(self, data: bytes) -> Tuple[int, bytes]:
        if len(data) < self.HEADER_SIZE + 2:
            raise ValueError(f"Packet too short: {len(data)} bytes, minimum required {self.HEADER_SIZE + 2} bytes")
        
        magic, sequence, command, version, payload_length = struct.unpack(
            ">HHBBI", data[:self.HEADER_SIZE]
        )
        
        if magic != self.MAGIC_NUMBER:
            raise ValueError(f"Invalid magic number: 0x{magic:04X}, expected 0x{self.MAGIC_NUMBER:04X}")
        
        expected_total_length = self.HEADER_SIZE + payload_length + 2
        if len(data) < expected_total_length:
            raise ValueError(
                f"Length mismatch: packet length {len(data)}, expected {expected_total_length}"
            )
        
        payload = data[self.HEADER_SIZE:self.HEADER_SIZE + payload_length]
        
        received_crc = struct.unpack(">H", data[self.HEADER_SIZE + payload_length:])[0]
        
        calculated_crc = crc16_x25(data[:self.HEADER_SIZE + payload_length])
        
        if received_crc != calculated_crc:
            raise ValueError(
                f"CRC check failed: received 0x{received_crc:04X}, calculated 0x{calculated_crc:04X}"
            )
        
        logger.debug(
            f"Decoded packet: seq={sequence}, cmd={command}, ver={version}, "
            f"payload_len={payload_length}, crc=0x{received_crc:04X}"
        )
        
        return sequence, payload
    
    def validate_packet(self, data: bytes) -> bool:
        try:
            self.decode(data)
            return True
        except ValueError as e:
            logger.warning(f"Packet validation failed: {e}")
            return False
    
    def get_packet_info(self, data: bytes) -> dict:
        if len(data) < self.HEADER_SIZE:
            return {"error": "Packet too short"}
        
        magic, sequence, command, version, payload_length = struct.unpack(
            ">HHBBI", data[:self.HEADER_SIZE]
        )
        
        return {
            "magic": f"0x{magic:04X}",
            "sequence": sequence,
            "command": command,
            "version": version,
            "payload_length": payload_length,
            "total_length": self.HEADER_SIZE + payload_length + 2,
            "valid_magic": magic == self.MAGIC_NUMBER,
        }
