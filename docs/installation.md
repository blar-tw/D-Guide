# Installation & Deployment (real hardware)

D-Guide is designed to run on a real drone: a **Raspberry Pi companion
computer** running ROS 2 + this workspace, talking to a **Pixhawk (ArduPilot)**
flight controller over MAVLink (DroneKit), with a **2D LiDAR** for obstacle
avoidance. This guide covers bringing that up. A SITL section at the end lets
you rehearse the whole pipeline on a laptop before flying.

> ⚠️ **Flight safety.** Always test with props off first, then in a wide open
> area with a safety pilot on the RC transmitter ready to flip out of GUIDED
> mode. Obstacle avoidance is a backup, not a guarantee.

## Hardware

| Part | Notes |
|---|---|
| Flight controller | Pixhawk-family, **ArduPilot** (Copter). GUIDED mode + velocity control used for avoidance. |
| Companion computer | Raspberry Pi 4/5 (Ubuntu 22.04 + ROS 2 Humble). Runs this workspace. |
| FC ↔ Pi link | USB (`/dev/ttyACM0`) or a serial UART (`/dev/serial0`, 921600). |
| 2D LiDAR | Forward-mounted (e.g. RPLIDAR A1/A2/S1). Publishes `sensor_msgs/LaserScan`. |
| GPS + compass | Required — the mission flies GPS waypoints. |
| Mic (optional) | USB microphone on the Pi for the voice front-end. |

## 1. Companion computer software

```bash
# ROS 2 Humble — https://docs.ros.org/en/humble/Installation.html
sudo apt install ros-humble-ros-base python3-colcon-common-extensions

# LiDAR driver (example: RPLIDAR)
sudo apt install ros-humble-rplidar-ros

# Python deps for D-Guide
cd ~/D-Guide
pip install -r requirements.txt
```

## 2. ArduPilot setup (one time)

Flash ArduPilot Copter to the Pixhawk (via Mission Planner / QGroundControl)
and set the parameters that let a companion computer command GUIDED velocity
without an RC override killing it mid-flight:

| Parameter | Value | Why |
|---|---|---|
| `SYSID_MYGCS` | `255` | Accept commands from the companion (MAVLink sysid 255). |
| `GUID_OPTIONS` | allow velocity/yaw | Permit `SET_POSITION_TARGET_LOCAL_NED`. |
| `WPNAV_SPEED` | ≈ your `NAV_SPEED_MAX` | Keep autopilot speed sane for a guide drone. |

Tune arming checks / failsafes per your airframe. Verify you can arm and take
off in GUIDED from a ground station before involving D-Guide.

## 3. Wire up secrets & config

```bash
cd ~/D-Guide
cp .env.example .env
```

Edit `.env` for the real drone:

```bash
# Path planning (required)
GOOGLE_MAPS_API_KEY=...

# Flight controller link — real Pixhawk over USB:
DRONE_CONNECTION=/dev/ttyACM0
DRONE_BAUD=921600          # 115200 for USB CDC; 921600 for a fast UART
CRUISE_ALTITUDE=5.0        # metres AGL
NAV_SPEED_MAX=1.5          # m/s — walking pace for a guide drone

# LiDAR
LIDAR_TOPIC=/scan          # topic your LiDAR driver publishes
LIDAR_FLIP_Y=true          # see the spin test in step 5
ROBOT_RADIUS=0.35          # planner keep-out; >= half the airframe width

# Voice (optional)
PICOVOICE_ACCESS_KEY=...
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/api_key.json
STT_LANGUAGE=zh-TW
```

## 4. Start the LiDAR

Launch your laser driver so it publishes `LaserScan` on `LIDAR_TOPIC`:

```bash
ros2 launch rplidar_ros rplidar.launch.py     # example for RPLIDAR
ros2 topic hz /scan                            # confirm it's publishing
```

## 5. Verify the LiDAR frame (important, do once)

The planner works in the drone's NED/FRD body frame; a standard `LaserScan`
is left-handed relative to it, so `LIDAR_FLIP_Y=true` is the default. Confirm
it on your mount: place an obstacle clearly on the drone's **right**, run the
navigator, and check the `nearest_threat` angle — a right-side obstacle should
read as such. If left/right are swapped, flip `LIDAR_FLIP_Y`.

## 6. Fly the mission

```bash
cd ~/D-Guide/ros_ws
./bringup.sh
```

This builds, then starts the path planner, the **DWA avoidance flight
executor**, the LLM command bridge, and the control node. At the prompt:

```
Enter origin: <a start address>
Enter destination: <a destination>
```

The path planner fetches walking directions, the navigator arms, takes off,
and flies each waypoint under closed-loop velocity control — steering around
whatever the LiDAR sees — then lands.

- **No-avoidance fallback** (bring-up / no LiDAR): `FLIGHT_EXECUTOR=simple ./bringup.sh`
  uses plain `simple_goto`.
- **Voice commands**: in another terminal, `./voice.sh` starts the wake-word +
  speech-to-text front-end (needs a mic and the Picovoice/Google keys).

## 7. Voice demo (optional)

```bash
cd ~/D-Guide/ros_ws
./voice.sh          # alongside a running ./bringup.sh
```

Say the wake word → speak a command ("take me to the train station") → it is
transcribed, parsed to a destination, and flown.

---

## Rehearsing in SITL (no hardware)

You can exercise the entire pipeline against ArduPilot SITL on a laptop first.

```bash
# Install and launch ArduCopter SITL
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y && . ~/.profile
cd ArduCopter
../Tools/autotest/sim_vehicle.py -v ArduCopter --out=tcpin:0.0.0.0:5760
```

Point D-Guide at it in `.env`:

```bash
DRONE_CONNECTION=tcp:127.0.0.1:5760
DRONE_BAUD=57600
```

SITL has no LiDAR, so the navigator flies straight to each waypoint (empty
obstacle set) — enough to validate the arm → takeoff → waypoint → land flow
and the GPS-to-local conversion. For avoidance testing with a simulated laser,
the companion **[HOLO-DWA](https://github.com/blar-tw/HOLO-DWA)** project runs
the same planner in PX4 SITL + Gazebo with a simulated 2D LiDAR.

```bash
cd ros_ws
./bringup.sh
# Enter origin / destination at the prompt
```
