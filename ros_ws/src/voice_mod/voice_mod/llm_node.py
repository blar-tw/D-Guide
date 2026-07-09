"""LLM command-parsing node.

Turns free-form text commands (typed or transcribed by the STT pipeline)
into a structured navigation intent, published as JSON on `parsed_command`:

    {"action": "navigate", "origin": "...", "destination": "...", "message": null}

Backends:
  - Claude API (Messages API + structured output) when ANTHROPIC_API_KEY is set
    and the `anthropic` package is installed.
  - Offline rule-based parser otherwise, so the pipeline stays testable
    without any API key.

Try it:
    ros2 run voice_mod llm_node
    ros2 topic pub --once /command_text std_msgs/String \
        "{data: 'take me from Hukou Station to the city library'}"
    ros2 topic echo /parsed_command
"""

import json
import os
import re

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# JSON schema shared by both backends; with the Claude backend it is enforced
# server-side via structured outputs.
COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["navigate", "clarify", "unsupported"],
        },
        "origin": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "destination": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "message": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "required": ["action", "origin", "destination", "message"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You parse voice commands for D-Guide, a guide drone that leads a walking "
    "user along real streets. Extract the navigation intent from the user's "
    "command.\n"
    "- action=navigate when a destination is clearly requested. Put the "
    "street address or place name in `destination`, and in `origin` if a "
    "starting point is given, else null.\n"
    "- action=clarify when the command is about navigating but too vague; "
    "put a short follow-up question in `message`.\n"
    "- action=unsupported for anything else (weather, chit-chat, camera, "
    "...); put a short reason in `message`.\n"
    "Keep place names in the user's language. Do not invent places."
)


class ClaudeParser:
    """Parses commands with the Claude API using structured outputs."""

    def __init__(self, logger):
        import anthropic  # imported lazily so the mock works without it

        self._client = anthropic.Anthropic()
        self._model = os.environ.get("LLM_MODEL", "claude-opus-4-8")
        self._logger = logger

    def parse(self, text: str) -> dict:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            output_config={
                "format": {"type": "json_schema", "schema": COMMAND_SCHEMA}
            },
            messages=[{"role": "user", "content": text}],
        )
        if response.stop_reason == "refusal":
            return {
                "action": "unsupported",
                "origin": None,
                "destination": None,
                "message": "Request declined by the model.",
            }
        reply = next(b.text for b in response.content if b.type == "text")
        return json.loads(reply)


class MockParser:
    """Offline rule-based fallback: handles 'from X to Y' / 'go to Y'."""

    FROM_TO = re.compile(
        r"\bfrom\s+(?P<origin>.+?)\s+to\s+(?P<dest>.+)", re.IGNORECASE
    )
    TO_ONLY = re.compile(
        r"\b(?:go|take me|navigate|bring me|fly)\s+(?:to\s+)?(?P<dest>.+)",
        re.IGNORECASE,
    )

    def parse(self, text: str) -> dict:
        text = text.strip().rstrip(".!?")
        m = self.FROM_TO.search(text)
        if m:
            return {
                "action": "navigate",
                "origin": m.group("origin").strip(),
                "destination": m.group("dest").strip(),
                "message": None,
            }
        m = self.TO_ONLY.search(text)
        if m:
            return {
                "action": "navigate",
                "origin": None,
                "destination": m.group("dest").strip(),
                "message": None,
            }
        return {
            "action": "clarify",
            "origin": None,
            "destination": None,
            "message": "Please say where you want to go, e.g. "
            "'take me from A to B'.",
        }


class LLMCommandParser(Node):
    def __init__(self):
        super().__init__('llm_command_parser')

        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                self.parser = ClaudeParser(self.get_logger())
                self.get_logger().info("🧠 Using Claude API backend")
            except ImportError:
                self.parser = MockParser()
                self.get_logger().warn(
                    "anthropic package not installed (pip install anthropic); "
                    "using offline rule-based parser"
                )
        else:
            self.parser = MockParser()
            self.get_logger().info(
                "ANTHROPIC_API_KEY not set; using offline rule-based parser"
            )

        self.sub = self.create_subscription(
            String, 'command_text', self.on_command, 10
        )
        self.pub = self.create_publisher(String, 'parsed_command', 10)
        self.get_logger().info("✅ LLM command parser ready on /command_text")

    def on_command(self, msg: String):
        text = msg.data.strip()
        if not text:
            return
        self.get_logger().info(f"📩 Command: {text}")
        try:
            result = self.parser.parse(text)
        except Exception as e:
            self.get_logger().error(f"🚨 Parse failed ({e}); falling back to rules")
            result = MockParser().parse(text)

        # A default origin lets "take me to X" work without a stated start
        if result.get("action") == "navigate" and not result.get("origin"):
            default_origin = os.environ.get("DEFAULT_ORIGIN")
            if default_origin:
                result["origin"] = default_origin
            else:
                result = {
                    "action": "clarify",
                    "origin": None,
                    "destination": result.get("destination"),
                    "message": "Where are you starting from? "
                    "(or set DEFAULT_ORIGIN in .env)",
                }

        out = String()
        out.data = json.dumps(result, ensure_ascii=False)
        self.pub.publish(out)
        self.get_logger().info(f"📤 Parsed: {out.data}")


def main(args=None):
    rclpy.init(args=args)
    node = LLMCommandParser()
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
