#!/usr/bin/env python3
import os
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from geometry_msgs.msg import PoseStamped
from interfaces.action import FollowPP


import collections
import collections.abc
collections.MutableMapping = collections.abc.MutableMapping
from dronekit import connect, VehicleMode, LocationGlobalRelative
import time
import math


class FollowPPServer(Node):
    def __init__(self):
        super().__init__('followpp_server')

        # Flight target is configurable so the same node runs against SITL or
        # a real Pixhawk (see docs/SITL.md):
        #   ArduPilot SITL        : DRONE_CONNECTION=tcp:127.0.0.1:5760 (default)
        #   real Pixhawk over USB : DRONE_CONNECTION=/dev/ttyACM0
        self.connection_string = os.environ.get("DRONE_CONNECTION", "tcp:127.0.0.1:5760")
        self.baud = int(os.environ.get("DRONE_BAUD", "57600"))
        self.cruise_altitude = float(os.environ.get("CRUISE_ALTITUDE", "5.0"))

        self._action_server = ActionServer(
            self,
            FollowPP,
            'follow_waypoints',
            execute_callback=self.execute_callback
        )

        self.get_logger().info(
            f"✅ FollowPP Action Server ready (target: {self.connection_string})"
        )

    async def execute_callback(self, goal_handle):
        goal = goal_handle.request
        waypoints = goal.waypoints
        tolerance = goal.tolerance
        feedback = FollowPP.Feedback()
        result = FollowPP.Result()

        self.get_logger().info(f"🚀 Received {len(waypoints)} waypoints, tol={tolerance}")

        # --- Connect to flight controller (real Pixhawk or SITL) ---
        self.get_logger().info(f"🌐 Connecting to {self.connection_string}...")
        vehicle = connect(self.connection_string, wait_ready=True, baud=self.baud)
        self.get_logger().info("✅ Connected to flight controller")

        # --- Arm and take off ---
        self.arm_and_takeoff(vehicle, self.cruise_altitude)

        # --- Fly through all waypoints ---
        for i, pose in enumerate(waypoints):
            lat = pose.pose.position.x
            lon = pose.pose.position.y
            target_location = LocationGlobalRelative(lat, lon, self.cruise_altitude)

            self.get_logger().info(f"➡️ Moving to waypoint {i + 1}: ({lat:.7f}, {lon:.7f})")
            vehicle.simple_goto(target_location)

            while True:
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    result.success = False
                    result.message = "Mission canceled by client"
                    self.get_logger().warn("❌ Mission canceled by client")
                    vehicle.mode = VehicleMode("LAND")
                    vehicle.close()
                    return result

                current = vehicle.location.global_relative_frame
                distance = self.get_distance_metres(current, target_location)

                feedback.current_index = i
                feedback.distance_to_goal = distance
                goal_handle.publish_feedback(feedback)

                if distance <= tolerance:
                    self.get_logger().info(f"✅ Reached waypoint {i + 1}")
                    break

                time.sleep(1)

        # --- Land after mission ---
        self.get_logger().info("🛬 Landing...")
        vehicle.mode = VehicleMode("LAND")
        while vehicle.armed:
            time.sleep(1)
        vehicle.close()

        result.success = True
        result.message = "All waypoints reached successfully!"
        goal_handle.succeed()
        return result

    # --- DroneKit helper functions ---
    def arm_and_takeoff(self, vehicle, target_altitude):
        self.get_logger().info("🔧 Arming motors")
        vehicle.mode = VehicleMode("GUIDED")
        vehicle.armed = True

        while not vehicle.armed:
            self.get_logger().info("⏳ Waiting for arming...")
            time.sleep(1)

        self.get_logger().info("🚁 Taking off!")
        vehicle.simple_takeoff(target_altitude)

        while True:
            altitude = vehicle.location.global_relative_frame.alt
            self.get_logger().info(f"📏 Altitude: {altitude:.2f} m")
            if altitude >= target_altitude * 0.95:
                self.get_logger().info("✅ Target altitude reached")
                break
            time.sleep(1)

    @staticmethod
    def get_distance_metres(aLocation1, aLocation2):
        dlat = aLocation2.lat - aLocation1.lat
        dlong = aLocation2.lon - aLocation1.lon
        return math.sqrt((dlat * 1.113195e5)**2 + (dlong * 1.113195e5)**2)


def main(args=None):
    rclpy.init(args=args)
    node = FollowPPServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
