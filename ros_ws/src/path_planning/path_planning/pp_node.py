import os
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, PoseArray
from interfaces.srv import GetWaypoints  # your custom service
import googlemaps


class PathPlannerService(Node):
    def __init__(self):
        super().__init__('path_planner_service')

        # Load API key from environment variable
        self.api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            self.get_logger().error("❌ GOOGLE_MAPS_API_KEY not set. Service cannot run.")
            raise RuntimeError("API key not set")

        # Create the service
        self.srv = self.create_service(GetWaypoints, 'get_waypoints', self.plan_path_callback)
        self.get_logger().info("✅ Path Planner Service ready: get_waypoints")

    def plan_path_callback(self, request, response):
        origin = request.origin
        destination = request.destination
        self.get_logger().info(f"📩 Received path request: {origin} → {destination}")

        gmaps = googlemaps.Client(key=self.api_key)
        directions = gmaps.directions(origin, destination, mode="walking")
        pose_array = PoseArray()
        pose_array.header.frame_id = "map"
        pose_array.header.stamp = self.get_clock().now().to_msg()

        if directions:
            steps = directions[0]['legs'][0]['steps']
            for step in steps:
                lat = step['end_location']['lat']
                lng = step['end_location']['lng']
                pose = Pose()
                pose.position.x = lat
                pose.position.y = lng
                pose.position.z = 0.0
                pose_array.poses.append(pose)

            self.get_logger().info(f"✅ Found {len(pose_array.poses)} waypoints")
        else:
            self.get_logger().warn("❌ No path found. Returning empty waypoint list.")

        response.waypoints = pose_array
        return response


def main(args=None):
    rclpy.init(args=args)
    try:
        node = PathPlannerService()
    except RuntimeError:
        # Missing configuration: the error was already logged above
        rclpy.shutdown()
        raise SystemExit(1)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
