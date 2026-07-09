import json

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from interfaces.srv import GetWaypoints
from interfaces.action import FollowPP
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
import threading


class ControlNode(Node):
    def __init__(self):
        super().__init__('control_node')

        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )

        # 1️⃣ Service Client
        self.cli = self.create_client(GetWaypoints, 'get_waypoints')
        while not self.cli.wait_for_service(timeout_sec=4.0):
            self.get_logger().info('⏳ Waiting for get_waypoints service...')

        # 2️⃣ Action Client
        self.action_client = ActionClient(self, FollowPP, 'follow_waypoints')

        # 3️⃣ Parsed voice/LLM commands (published by voice_mod llm_node)
        self.cmd_sub = self.create_subscription(
            String, 'parsed_command', self.parsed_command_cb, 10
        )
        self.get_logger().info("✅ Control Node ready")

        # 🧵 Start interactive input
        threading.Thread(target=self.user_input_thread, daemon=True).start()

    def parsed_command_cb(self, msg: String):
        """Handle structured commands from the LLM parser."""
        try:
            cmd = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn(f"⚠️ Ignoring malformed parsed_command: {msg.data}")
            return

        if cmd.get("action") == "navigate" and cmd.get("origin") and cmd.get("destination"):
            self.get_logger().info(
                f"🗣️ Voice command: {cmd['origin']} → {cmd['destination']}"
            )
            self.request_path_async(cmd["origin"], cmd["destination"])
        else:
            self.get_logger().info(f"🗣️ Command needs follow-up: {msg.data}")

    def user_input_thread(self):
        """Interactive terminal input"""
        while rclpy.ok():
            try:
                origin = input("\nEnter origin: ").strip()
                if origin.lower() == "exit":
                    self.get_logger().info("🛑 Exiting command loop...")
                    self.request_shutdown()
                    break

                destination = input("Enter destination: ").strip()
                if not origin or not destination:
                    print("⚠️  Both origin and destination are required.")
                    continue

                origin_log = self.sanitize_for_log(origin)
                destination_log = self.sanitize_for_log(destination)
                self.get_logger().info(
                    f"📍 Requesting path from '{origin_log}' to '{destination_log}'"
                )
                self.request_path_async(origin, destination)

            except (EOFError, KeyboardInterrupt):
                self.get_logger().info("🛑 Input interrupted.")
                self.request_shutdown()
                break

    def request_shutdown(self):
        """Shutdown helper to avoid double shutdown crashes."""
        if rclpy.ok():
            self.get_logger().info("🧹 Shutting down rclpy context...")
            rclpy.shutdown()

    @staticmethod
    def sanitize_for_log(text):
        """Ensure log messages use valid UTF-8 strings."""
        if isinstance(text, str):
            return text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        return str(text)

    def request_path_async(self, origin, destination):
        """Asynchronous non-blocking service call"""
        req = GetWaypoints.Request()
        req.origin = origin
        req.destination = destination
        future = self.cli.call_async(req)
        future.add_done_callback(self.path_response_cb)

    def path_response_cb(self, future):
        """Called when path service responds"""
        try:
            response = future.result()
            if not response or not response.waypoints:
                self.get_logger().warn("❌ No waypoints received.")
                return
            self.get_logger().info("✅ Waypoints received, sending to action server...")
            self.send_action(response.waypoints)
        except Exception as e:
            self.get_logger().error(f"🚨 Service call failed: {e}")

    def send_action(self, waypoints, tolerance=0.5):
        if not self.action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('❌ Action server not available!')
            return

        goal_msg = FollowPP.Goal()
        goal_msg.waypoints = []

        for p in waypoints.poses:
            ps = PoseStamped()
            ps.header.frame_id = getattr(waypoints, "header", None) and waypoints.header.frame_id or "map"
            ps.header.stamp = self.get_clock().now().to_msg()
            ps.pose = p.pose if isinstance(p, PoseStamped) else p
            goal_msg.waypoints.append(ps)

        goal_msg.tolerance = tolerance

        send_goal_future = self.action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_cb
        )
        send_goal_future.add_done_callback(self.goal_response_cb)

    def goal_response_cb(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("🚫 Goal rejected by server")
            return

        self.get_logger().info("🚀 Goal accepted, waiting for result...")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_cb)

    def result_cb(self, future):
        try:
            result = future.result().result
            self.get_logger().info(f"🎯 Result: success={result.success}, msg={result.message}")
        except Exception as e:
            self.get_logger().error(f"🚨 Error getting result: {e}")

    def feedback_cb(self, feedback_msg):
        fb = feedback_msg.feedback
        self.get_logger().info(f"📡 Waypoint {fb.current_index} | distance: {fb.distance_to_goal:.2f}")


def main(args=None):
    rclpy.init(args=args)
    node = ControlNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("🛑 Shutting down...")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

# 24.902079, 121.042178
# Hukuo Station
