"""Speech-to-text node.

Provides the `process_voice_command` Trigger service that the wake-word node
calls once it hears the wake word. On each trigger this node:

  1. records a few seconds of microphone audio,
  2. transcribes it with Google Cloud Speech-to-Text,
  3. publishes the transcript on `command_text` (picked up by llm_node),
  4. returns success + the transcript to the caller.

So the full voice chain is:

    ww_node (wake word) --Trigger--> stt_node --command_text--> llm_node
        --parsed_command--> control_node --> flight

Config (see .env.example):
    GOOGLE_APPLICATION_CREDENTIALS  path to the GCP service-account JSON
    STT_LANGUAGE                    BCP-47 code, default zh-TW
    STT_RECORD_SECONDS              capture length, default 5
    PVRECORDER_DEVICE_INDEX / MIC_DEVICE_INDEX   mic index (-1 = default)
"""

import os

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger

RATE = 16000
CHANNELS = 1
CHUNK = 1024


class SpeechToTextNode(Node):
    def __init__(self):
        super().__init__('stt_node')

        self.language = os.environ.get("STT_LANGUAGE", "zh-TW")
        self.record_seconds = float(os.environ.get("STT_RECORD_SECONDS", "5"))
        self.device_index = int(
            os.environ.get("MIC_DEVICE_INDEX",
                           os.environ.get("PVRECORDER_DEVICE_INDEX", "-1"))
        )

        # Speech client is created lazily on first use so the node still
        # starts (and reports a clear error) when credentials are missing.
        self._speech = None
        self._speech_error = None
        try:
            from google.cloud import speech_v1 as speech
            if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                raise RuntimeError(
                    "GOOGLE_APPLICATION_CREDENTIALS not set (path to the GCP "
                    "service-account JSON)"
                )
            self._speech = speech.SpeechClient()
            self._speech_module = speech
            self.get_logger().info(f"🗣️ Google STT ready (lang={self.language})")
        except Exception as e:  # ImportError or missing credentials
            self._speech_error = str(e)
            self.get_logger().warn(
                f"STT backend unavailable ({e}); the service will return an error "
                "until google-cloud-speech and credentials are configured."
            )

        self.pub = self.create_publisher(String, 'command_text', 10)
        self.srv = self.create_service(
            Trigger, 'process_voice_command', self.on_trigger
        )
        self.get_logger().info("✅ STT service ready on process_voice_command")

    def on_trigger(self, request, response):
        if self._speech is None:
            response.success = False
            response.message = f"STT unavailable: {self._speech_error}"
            self.get_logger().error(response.message)
            return response

        try:
            audio_bytes = self._record()
            transcript = self._transcribe(audio_bytes)
        except Exception as e:
            response.success = False
            response.message = f"STT failed: {e}"
            self.get_logger().error(response.message)
            return response

        if not transcript:
            response.success = False
            response.message = "No speech recognized"
            self.get_logger().warn(response.message)
            return response

        msg = String()
        msg.data = transcript
        self.pub.publish(msg)
        self.get_logger().info(f"📤 Transcript: {transcript}")

        response.success = True
        response.message = transcript
        return response

    def _record(self) -> bytes:
        """Capture `record_seconds` of mono 16 kHz PCM from the microphone."""
        import pyaudio

        p = pyaudio.PyAudio()
        kwargs = dict(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        if self.device_index >= 0:
            kwargs["input_device_index"] = self.device_index

        stream = p.open(**kwargs)
        self.get_logger().info(f"🎙️ Recording {self.record_seconds:.0f}s...")
        frames = [
            stream.read(CHUNK, exception_on_overflow=False)
            for _ in range(int(RATE / CHUNK * self.record_seconds))
        ]
        stream.stop_stream()
        stream.close()
        p.terminate()
        return b"".join(frames)

    def _transcribe(self, audio_bytes: bytes) -> str:
        speech = self._speech_module
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code=self.language,
            audio_channel_count=CHANNELS,
        )
        result = self._speech.recognize(config=config, audio=audio)
        for r in result.results:
            return r.alternatives[0].transcript.strip()
        return ""


def main(args=None):
    rclpy.init(args=args)
    node = SpeechToTextNode()
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
