#!/usr/bin/env python3

# pyrtcm for parsing
# receive messsage with zmq subscriber
# zmq can decode the message (bytes)
# put it into an rtcm rosmsg
# publish this rtcm msg to the gps

import sys
import zmq
import rclpy
import time
from rclpy.node import Node
from rtcm_msgs.msg import Message

class RTKReceiver(Node):

    def __init__(self):
        super().__init__('rtk_receiver')

        self.declare_parameter("ip", "10.10.10.10.")
        self.declare_parameter("port", 5000)

        ip = self.get_parameter("ip").value
        port = self.get_parameter("port").value

        self.context_ = zmq.Context()
        self.socket = self.context_.socket(zmq.SUB)

        self.get_logger().info(f"Opening Socket on: {ip}:{port}")
        
        self.socket.connect(f"tcp://{ip}:{port}")
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self.pub = self.create_publisher(Message, '/rtcm', 1)

    def receive(self):
        while rclpy.ok():
            try:
                rtcm_raw = self.socket.recv(flags=zmq.NOBLOCK)
                self.get_logger().info("[RTK] Recieved corrections", once=True)

                msg = Message()
                msg.header.stamp = rospy.Time.now()
                msg.message = rtcm_raw
                self.pub.publish(msg)

            except zmq.Again:
                continue
                #print("No RTCM reading available.")
                 
            time.sleep(0.1)

        self.socket.close()
        self.context_.term()

def main(args=None) -> None:
    rclpy.init(args=args)

    node = RTKReceiver()

    node.receive()

    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
