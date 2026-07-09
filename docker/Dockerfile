# D-Guide core navigation stack on ROS 2 Humble.
# Voice packages build too, but audio I/O needs host devices; run the voice
# nodes natively if you want the mic pipeline.
#
# Build from the repo root:
#   docker build -f docker/Dockerfile -t d-guide .
# Or simply:
#   docker compose -f docker/docker-compose.yml up --build

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Core Python deps only (path planning + flight control). Audio deps from
# requirements.txt (pyaudio, pvrecorder) need portaudio and a microphone,
# which containers usually lack.
RUN pip3 install --no-cache-dir \
    googlemaps \
    requests \
    dronekit \
    pymavlink

WORKDIR /ws/ros_ws
COPY ros_ws/src ./src
COPY ros_ws/bringup.sh ./
COPY ros_ws/scripts ./scripts

RUN /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build"

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash"]
