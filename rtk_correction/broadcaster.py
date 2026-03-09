# base station broadcaster
# pyrtcm for serial connection
# read gps on basestation with pyrtcm through serial connection
# pyrtcm reads the serial connection and gives me some bytes
# the bytes i multicast it with zmq

import serial
import zmq
import rclpy
from rclpy.node import Node
from pyrtcm import RTCMReader

class Basestation(Node):
    def __init__(self):
        super().__init__("rtk_broadcaster")
        self.context_ = zmq.Context()
        self.socket = self.context_.socket(zmq.PUB)
       
        self.declare_parameter("ip", "127.0.0.1")
        self.declare_parameter("port", 7505)

        ip = self.get_parameter("ip").value
        port = self.get_parameter("port").value

        self.socket.bind(f"tcp://{ip}:{port}")

    def broadcast(self):
        with serial.Serial('/dev/ublox', 38400, timeout=3) as stream:
            rtr = RTCMReader(stream)
            self.get_logger().info("[RTK] Connected to GPS")
            while rclpy.ok():
                raw_data, parsed_data = rtr.read()
                #print(raw_data, parsed_data)
                if parsed_data is not None:
                    # Broadcast raw data
                    self.get_logger().info("[RTK] Broadcasting corrections", once=True)
                    self.socket.send(raw_data)

def main(args=None):
    rclpy.init(args=args)

    node = Basestation()

    node.broadcast()

    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
