# Flying D-Guide in SITL (Software-In-The-Loop)

You can run the full D-Guide mission pipeline — address input, Google Maps
waypoint planning, takeoff, waypoint following, landing — **without any
hardware**, against a simulated flight controller.

The flight nodes speak MAVLink via DroneKit, so **ArduPilot SITL is the
recommended simulator** (best DroneKit compatibility). A PX4 alternative is
described at the end.

## 1. Install ArduPilot SITL

```bash
# Clone ArduPilot (once)
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot

# Install prerequisites (Ubuntu)
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```

No build is required for SITL when using `sim_vehicle.py`; it compiles the
copter firmware on first run.

## 2. Start the simulated drone

```bash
cd ardupilot/ArduCopter
# Spawn a quadcopter; -L lets you pick a start location if you have one defined
../Tools/autotest/sim_vehicle.py -v ArduCopter --out=tcpin:0.0.0.0:5760
```

Wait until you see `EKF3 IMU0 is using GPS` (GPS lock) — arming fails before
that. The simulator now accepts a MAVLink connection on `tcp:127.0.0.1:5760`.

> **Tip:** pick a start location near your test route so the Google Maps
> waypoints are reachable, e.g.
> `sim_vehicle.py -v ArduCopter -l 24.902079,121.042178,100,0 --out=tcpin:0.0.0.0:5760`

## 3. Point D-Guide at the simulator

`tcp:127.0.0.1:5760` is already the default `DRONE_CONNECTION`, so with SITL
running locally you need no extra configuration. To be explicit, set it in
`.env`:

```bash
DRONE_CONNECTION=tcp:127.0.0.1:5760
CRUISE_ALTITUDE=5.0
```

(For a real Pixhawk over USB use `DRONE_CONNECTION=/dev/ttyACM0` and
`DRONE_BAUD=57600`.)

## 4. Smoke test: takeoff and land

```bash
cd ros_ws
set -a; source ../.env; set +a
python3 scripts/flight_test.py
```

Expected output: connect → arm → climb to 5 m → land.

## 5. Full mission

```bash
cd ros_ws
./bringup.sh
```

Then at the `Enter origin:` prompt, type a start address, then a destination.
The pipeline requests walking directions from Google Maps, converts each step
into a waypoint, and the simulated drone takes off, follows every waypoint,
and lands.

Watch progress either in the node logs (`Waypoint i | distance: ...`) or in
the SITL console/map.

## PX4 SITL alternative

If you prefer PX4 (e.g. you already have `~/PX4-Autopilot`):

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500        # PX4 v1.14+, Gazebo
```

PX4 exposes MAVLink for offboard APIs on UDP port 14540, so point DroneKit at:

```bash
DRONE_CONNECTION=udpin:0.0.0.0:14540
```

Caveats: DroneKit's mode/arming helpers are ArduPilot-flavored; with PX4 some
operations (notably `simple_takeoff` in GUIDED mode) need adaptation, which is
why ArduPilot SITL is the supported demo path.
