import os
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger  # standard empty request/response with success + message
from ament_index_python.packages import get_package_share_directory

import pvporcupine
import pvrecorder

class WakeWordNode(Node):
    def __init__(self):
        super().__init__('wake_word_node')

        # Setup Porcupine (access key from environment; see .env / .env.example)
        access_key = os.environ.get("PICOVOICE_ACCESS_KEY")
        if not access_key:
            raise RuntimeError("PICOVOICE_ACCESS_KEY not set. Copy .env.example to .env, fill it, then: source .env")
        # Wake-word model is installed to the package share dir by setup.py;
        # WW_MODEL_PATH overrides it (e.g. to test a new .ppn without rebuilding)
        model_path = os.environ.get(
            "WW_MODEL_PATH",
            os.path.join(get_package_share_directory('voice_mod'), 'ww.ppn')
        )
        self.porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[model_path]
        )

        # Microphone index differs per machine; list devices with:
        #   python3 -c "import pvrecorder; print(pvrecorder.PvRecorder.get_available_devices())"
        device_index = int(os.environ.get("PVRECORDER_DEVICE_INDEX", "-1"))
        self.recorder = pvrecorder.PvRecorder(device_index=device_index, frame_length=self.porcupine.frame_length)

        # Service client for triggering voice interaction
        self.cli = self.create_client(Trigger, 'process_voice_command')

        self.get_logger().info("Starting wake word listener...")
        self.recorder.start()
        self.timer = self.create_timer(0.01, self.detect_loop)
        self.calling = False

    def detect_loop(self):
        if self.calling:
            return  # pause detection during processing

        try:
            pcm = self.recorder.read()
            keyword_index = self.porcupine.process(pcm)
            if keyword_index >= 0:
                self.get_logger().info("Wake word detected!")
                self.calling = True
                self.recorder.stop()

                # Wait for service to be available
                if not self.cli.wait_for_service(timeout_sec=15.0):
                    self.get_logger().error("Voice command service not available")
                    self.recorder.start()
                    self.calling = False
                    return

                # Create request
                req = Trigger.Request()
                future = self.cli.call_async(req)
                future.add_done_callback(self.on_response)

        except Exception as e:
            self.get_logger().error(f"Error in wake detection: {e}")

    def on_response(self, future):
        try:
            response = future.result()
            if response.success:
                self.get_logger().info(f"Service success: {response.message}")
            else:
                self.get_logger().warn(f"Service failed: {response.message}")
        except Exception as e:
            self.get_logger().error(f"Service call failed: {e}")

        # Resume detection
        self.recorder.start()
        self.calling = False

    def destroy_node(self):
        if self.recorder.is_recording:
            self.recorder.stop()
        self.porcupine.delete()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = WakeWordNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
