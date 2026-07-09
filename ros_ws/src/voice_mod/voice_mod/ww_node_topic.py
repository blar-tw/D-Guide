import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty
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
        self.publisher_ = self.create_publisher(Empty, 'wake_detected', 10)

        self.get_logger().info("Starting wake word listener...")
        self.recorder.start()

        # 定時 callback 處理音訊
        self.timer = self.create_timer(0.01, self.detect_loop)

    def detect_loop(self):
        try:
            pcm = self.recorder.read()
            keyword_index = self.porcupine.process(pcm)
            if keyword_index >= 0:
                self.get_logger().info("Wake word detected!")
                self.publisher_.publish(Empty())
        except Exception as e:
            self.get_logger().error(f"Error in wake detection: {e}")

    def destroy_node(self):
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
