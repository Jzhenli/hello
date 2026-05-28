#!/usr/bin/env python
"""Test script for XNC Server Simulator"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.normpath(os.path.join(current_dir, "..", "..", "src"))
if os.path.exists(src_path):
    sys.path.insert(0, src_path)

from protocol import UDPProtocolCodec
from codec import ProtobufCodec
from generated import MessageType, apiMsg


def test_protocol_codec():
    """Test UDP protocol codec"""
    print("Testing UDPProtocolCodec...")
    
    codec = UDPProtocolCodec()
    
    test_payload = b"Hello, XAgent!"
    
    encoded = codec.encode(test_payload, sequence=1)
    print(f"  Encoded packet length: {len(encoded)} bytes")
    
    sequence, decoded = codec.decode(encoded)
    print(f"  Decoded sequence: {sequence}")
    print(f"  Decoded payload: {decoded}")
    
    assert decoded == test_payload, "Payload mismatch!"
    assert sequence == 1, "Sequence mismatch!"
    
    print("  UDPProtocolCodec test PASSED!")


def test_protobuf_codec():
    """Test Protobuf codec"""
    print("\nTesting ProtobufCodec...")
    
    prop = ProtobufCodec.create_property(pid=85, value=42.5)
    print(f"  Created property: pid={prop.pid}, value type={prop.v.type}")
    
    obj = ProtobufCodec.create_object(oid=1, properties=[prop])
    print(f"  Created object: oid={obj.oid}, properties count={len(obj.pv)}")
    
    msg = ProtobufCodec.create_message(
        uuid=1,
        cmd_id=MessageType.READ_PROPERTY,
        vd_id=100,
        objects=[obj]
    )
    print(f"  Created message: uuid={msg.uuid}, cmdID={msg.cmdID}, vdID={msg.vdID}")
    
    encoded = ProtobufCodec.encode_message(msg)
    print(f"  Encoded message length: {len(encoded)} bytes")
    
    decoded = ProtobufCodec.decode_message(encoded)
    print(f"  Decoded message: uuid={decoded.uuid}, cmdID={decoded.cmdID}")
    
    msg_dict = ProtobufCodec.message_to_dict(decoded)
    print(f"  Message as dict: {msg_dict}")
    
    assert decoded.uuid == msg.uuid, "UUID mismatch!"
    assert decoded.cmdID == msg.cmdID, "cmdID mismatch!"
    
    print("  ProtobufCodec test PASSED!")


def test_full_roundtrip():
    """Test full encoding/decoding roundtrip"""
    print("\nTesting full roundtrip...")
    
    protocol_codec = UDPProtocolCodec()
    
    msg = ProtobufCodec.create_write_property_message(
        uuid=123,
        vd_id=1,
        oid=10,
        pid=85,
        value=25.6
    )
    
    payload = ProtobufCodec.encode_message(msg)
    packet = protocol_codec.encode(payload, sequence=42)
    
    print(f"  Full packet length: {len(packet)} bytes")
    
    seq, decoded_payload = protocol_codec.decode(packet)
    decoded_msg = ProtobufCodec.decode_message(decoded_payload)
    
    print(f"  Decoded sequence: {seq}")
    print(f"  Decoded message type: {ProtobufCodec.get_message_type_name(decoded_msg.cmdID)}")
    
    msg_dict = ProtobufCodec.message_to_dict(decoded_msg)
    print(f"  Decoded message: {msg_dict}")
    
    assert seq == 42, "Sequence mismatch!"
    assert decoded_msg.uuid == 123, "UUID mismatch!"
    assert decoded_msg.vdID == 1, "vdID mismatch!"
    
    print("  Full roundtrip test PASSED!")


def main():
    print("=" * 50)
    print("XNC Server Simulator - Unit Tests")
    print("=" * 50)
    
    try:
        test_protocol_codec()
        test_protobuf_codec()
        test_full_roundtrip()
        
        print("\n" + "=" * 50)
        print("All tests PASSED!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nTest FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
