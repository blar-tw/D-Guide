#!/bin/bash
set -e

source /opt/ros/humble/setup.bash
if [ -f /ws/ros_ws/install/setup.bash ]; then
  source /ws/ros_ws/install/setup.bash
fi

exec "$@"
