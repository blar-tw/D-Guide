"""DWA obstacle-avoidance flight executor for D-Guide.

Serves the same `follow_waypoints` (FollowPP) action as the simple
`followpp_server`, but instead of `simple_goto`-ing each waypoint it flies
there under closed-loop velocity control, re-planning against the live 2D
LiDAR scan every tick with the HOLO-DWA planner. Drop-in for control_node —
the action interface is unchanged.

Per waypoint:
  1. convert the GPS waypoint to a local NED goal (relative to the drone's
     current position),
  2. loop at ~10 Hz: read state → build an obstacle point cloud from the
     latest LaserScan → run dwa_core.dwa_control() → send an ArduPilot GUIDED
     velocity setpoint (SET_POSITION_TARGET_LOCAL_NED), nose turned toward the
     goal so the forward-facing LiDAR covers the travel direction,
  3. advance when within `tolerance` metres.

With no LiDAR data the planner sees no obstacles and flies straight to the
goal, so this node also works as a plain waypoint follower on a drone without
a laser scanner.

Flight stack: ArduPilot + DroneKit/MAVLink (GUIDED), matching D-Guide's
Raspberry-Pi deployment. Connection and flight params come from the
environment (see .env.example): DRONE_CONNECTION, DRONE_BAUD, CRUISE_ALTITUDE,
LIDAR_TOPIC, LIDAR_FLIP_Y, NAV_SPEED_MAX.
"""

import math
import os
import threading
import time

import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import LaserScan
from interfaces.action import FollowPP

import collections
import collections.abc
collections.MutableMapping = collections.abc.MutableMapping  # dronekit/py3.10 shim
from dronekit import connect, VehicleMode
from pymavlink import mavutil

from obstacle_avoidance import dwa_core

# Metres per degree of latitude (WGS-84 mean); longitude is scaled by cos(lat).
_M_PER_DEG_LAT = 111320.0

# SET_POSITION_TARGET_LOCAL_NED type_mask: use vx, vy, vz and yaw; ignore
# position, acceleration, force, and yaw_rate.
_VEL_YAW_TYPE_MASK = 0b0000101111000111


class DWANavigator(Node):
    def __init__(self):
        super().__init__('dwa_navigator')

        self.connection_string = os.environ.get("DRONE_CONNECTION", "tcp:127.0.0.1:5760")
        self.baud = int(os.environ.get("DRONE_BAUD", "57600"))
        self.cruise_altitude = float(os.environ.get("CRUISE_ALTITUDE", "5.0"))
        lidar_topic = os.environ.get("LIDAR_TOPIC", "/scan")
        # A forward-mounted 2D laser publishing a REP-103 scan (angle CCW, 0 =
        # forward) is left-handed relative to the NED/FRD body frame DWA works
        # in, so its points must be mirrored across the body axis. Verify on
        # your drone with a spin test (see docs/installation.md) and flip if
        # obstacles appear on the wrong side.
        self.lidar_flip_y = os.environ.get("LIDAR_FLIP_Y", "true").lower() == "true"

        self.cb_group = ReentrantCallbackGroup()

        # --- Planner config (tuned values from HOLO-DWA; speed capped for a
        # guide drone leading a walking user) ---
        cfg = dwa_core.Config()
        v_max = float(os.environ.get("NAV_SPEED_MAX", "1.5"))
        cfg.v_max = v_max
        cfg.vx_min, cfg.vx_max = -v_max, v_max
        cfg.vy_min, cfg.vy_max = -v_max, v_max
        cfg.a_max = 1.0
        cfg.brake_a_max = 1.0
        cfg.vx_resolution = cfg.vy_resolution = 0.1
        cfg.control_dt = 0.2
        cfg.predict_time = 3.0
        cfg.predict_dt = 0.2
        cfg.robot_radius = float(os.environ.get("ROBOT_RADIUS", "0.35"))
        cfg.goal_threshold = 0.5
        cfg.velocity_mode = "blend"
        cfg.blend_alpha = 0.5
        cfg.clearance_norm = 0.5
        cfg.clearance_lookahead = 1.5
        cfg.heading_weight = 0.3
        cfg.clearance_weight = 0.3
        cfg.velocity_weight = 0.4
        self.cfg = cfg

        self.latest_scan = None
        self.lidar_sub = self.create_subscription(
            LaserScan, lidar_topic, self._lidar_cb, 10, callback_group=self.cb_group
        )

        self.get_logger().info(f"🌐 Connecting to {self.connection_string}...")
        self.vehicle = connect(self.connection_string, wait_ready=True, baud=self.baud)
        self.get_logger().info("✅ Connected to flight controller")

        self._action_server = ActionServer(
            self,
            FollowPP,
            'follow_waypoints',
            execute_callback=self.execute_callback,
            cancel_callback=lambda _goal: CancelResponse.ACCEPT,
            callback_group=self.cb_group,
        )
        self.get_logger().info(
            f"✅ DWA navigator ready (LiDAR: {lidar_topic}, flip_y={self.lidar_flip_y})"
        )

    def _lidar_cb(self, msg: LaserScan):
        self.latest_scan = msg

    # --- state helpers ---
    def _local_ned(self):
        """Current position/velocity/yaw in the local NED frame DWA uses."""
        lf = self.vehicle.location.local_frame
        vel = self.vehicle.velocity  # [vn, ve, vd] ground frame
        yaw = self.vehicle.attitude.yaw  # radians, 0 = North
        n = lf.north if lf.north is not None else 0.0
        e = lf.east if lf.east is not None else 0.0
        vn = vel[0] if vel[0] is not None else 0.0
        ve = vel[1] if vel[1] is not None else 0.0
        return n, e, vn, ve, (yaw if yaw is not None else 0.0)

    def _goal_ned(self, target_lat, target_lon):
        """Local NED (north, east) of a GPS waypoint relative to the drone now.

        Equirectangular approximation anchored at the current position — good
        to well under a metre over the short legs between street waypoints.
        """
        loc = self.vehicle.location.global_relative_frame
        n, e, *_ = self._local_ned()
        dn = (target_lat - loc.lat) * _M_PER_DEG_LAT
        de = (target_lon - loc.lon) * _M_PER_DEG_LAT * math.cos(math.radians(loc.lat))
        return n + dn, e + de

    # --- flight primitives (ArduPilot GUIDED) ---
    def arm_and_takeoff(self, altitude):
        self.get_logger().info("🔧 Arming (GUIDED)")
        self.vehicle.mode = VehicleMode("GUIDED")
        self.vehicle.armed = True
        while not self.vehicle.armed:
            self.get_logger().info("⏳ Waiting for arming...")
            time.sleep(1)

        self.get_logger().info(f"🚁 Taking off to {altitude:.1f} m")
        self.vehicle.simple_takeoff(altitude)
        while True:
            alt = self.vehicle.location.global_relative_frame.alt or 0.0
            if alt >= altitude * 0.95:
                self.get_logger().info("✅ Reached target altitude")
                break
            time.sleep(0.5)

    def send_velocity(self, vx, vy, yaw):
        """Send an NED velocity + yaw setpoint (vz=0 holds altitude)."""
        msg = self.vehicle.message_factory.set_position_target_local_ned_encode(
            0, 0, 0,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            _VEL_YAW_TYPE_MASK,
            0, 0, 0,           # position (ignored)
            vx, vy, 0.0,       # velocity NED
            0, 0, 0,           # acceleration (ignored)
            float(yaw), 0.0,   # yaw, yaw_rate
        )
        self.vehicle.send_mavlink(msg)

    def land(self):
        self.get_logger().info("🛬 Landing")
        self.vehicle.mode = VehicleMode("LAND")

    # --- action ---
    def execute_callback(self, goal_handle):
        waypoints = goal_handle.request.waypoints
        tolerance = goal_handle.request.tolerance or self.cfg.goal_threshold
        feedback = FollowPP.Feedback()
        result = FollowPP.Result()

        self.get_logger().info(f"🚀 Received {len(waypoints)} waypoints, tol={tolerance}")
        self.arm_and_takeoff(self.cruise_altitude)

        loop_dt = 0.1  # 10 Hz control loop
        last_reached = -1

        for i, ps in enumerate(waypoints):
            pose = ps.pose if isinstance(ps, PoseStamped) else ps
            target_lat = pose.position.x
            target_lon = pose.position.y
            goal_n, goal_e = self._goal_ned(target_lat, target_lon)
            self.get_logger().info(
                f"➡️ Waypoint {i + 1}/{len(waypoints)} "
                f"(local NED goal {goal_n:+.1f}, {goal_e:+.1f})"
            )

            while True:
                if goal_handle.is_cancel_requested:
                    self.send_velocity(0.0, 0.0, self._local_ned()[4])
                    self.land()
                    goal_handle.canceled()
                    result.success = False
                    result.last_reached_index = last_reached
                    result.message = "Mission canceled by client"
                    self.get_logger().warn("❌ Mission canceled")
                    return result

                n, e, vn, ve, yaw = self._local_ned()
                dist = math.hypot(goal_n - n, goal_e - e)
                if dist <= tolerance:
                    self.get_logger().info(f"✅ Reached waypoint {i + 1}")
                    last_reached = i
                    break

                goal_yaw = math.atan2(goal_e - e, goal_n - n)
                obstacles = self._obstacle_points(n, e, yaw)
                vx, vy, ok = dwa_core.dwa_control(
                    {"x": n, "y": e, "vx": vn, "vy": ve},
                    (goal_n, goal_e), obstacles, self.cfg,
                )
                if not ok:
                    vx, vy = 0.0, 0.0  # no feasible velocity -> brake to hover
                self.send_velocity(vx, vy, goal_yaw)

                feedback.current_index = i
                feedback.distance_to_goal = float(dist)
                goal_handle.publish_feedback(feedback)
                time.sleep(loop_dt)

        self.send_velocity(0.0, 0.0, self._local_ned()[4])
        self.land()
        goal_handle.succeed()
        result.success = True
        result.last_reached_index = last_reached
        result.message = "All waypoints reached"
        return result

    def _obstacle_points(self, robot_n, robot_e, yaw):
        scan = self.latest_scan
        if scan is None:
            return np.empty((0, 2))
        return dwa_core.scan_to_world_points(
            scan.ranges, scan.angle_min, scan.angle_increment,
            scan.range_min, scan.range_max,
            robot_n, robot_e, yaw,
            stride=int(os.environ.get("LIDAR_STRIDE", "2")),
            flip_y=self.lidar_flip_y,
        )

    def destroy_node(self):
        try:
            self.vehicle.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DWANavigator()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
