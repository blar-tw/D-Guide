import os
import time
import collections
import collections.abc
collections.MutableMapping = collections.abc.MutableMapping
from dronekit import connect, VehicleMode, LocationGlobalRelative

# Same env vars as followpp_server (see .env.example / docs/installation.md):
#   real Pixhawk over USB : DRONE_CONNECTION=/dev/ttyACM0
#   ArduPilot SITL        : DRONE_CONNECTION=tcp:127.0.0.1:5760 (default)
CONNECTION_STRING = os.environ.get("DRONE_CONNECTION", "tcp:127.0.0.1:5760")
BAUD_RATE = int(os.environ.get("DRONE_BAUD", "57600"))

def arm_and_takeoff(vehicle, target_altitude):
    print("🔧 Arming motors...")
    vehicle.mode = VehicleMode("GUIDED")
    vehicle.armed = True

    while not vehicle.armed:
        print("⏳ Waiting for arming...")
        time.sleep(1)

    print("🚁 Taking off!")
    vehicle.simple_takeoff(target_altitude)

    # Wait until the vehicle reaches the target altitude
    while True:
        altitude = vehicle.location.global_relative_frame.alt
        print(f"📏 Altitude: {altitude:.2f} m")
        if altitude >= target_altitude * 0.95:
            print("✅ Target altitude reached")
            break
        time.sleep(1)

def main():
    try:
        print(f"🌐 Connecting to vehicle on {CONNECTION_STRING}...")
        vehicle = connect(CONNECTION_STRING, wait_ready=True, baud=BAUD_RATE)
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return

    try:
        arm_and_takeoff(vehicle, 5)  # test takeoff to 5 meters
    except Exception as e:
        print(f"❌ Takeoff failed: {e}")
    finally:
        print("🛬 Landing and closing connection...")
        vehicle.mode = VehicleMode("LAND")
        while vehicle.armed:
            time.sleep(1)
        vehicle.close()
        print("✅ Test complete.")

if __name__ == "__main__":
    main()
