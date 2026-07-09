# Images

Media assets referenced by the docs and the root README.

Wanted here (see the README roadmap):

- `demo.gif` — a SITL mission recording: enter a destination, watch takeoff →
  waypoint following → landing. Suggested capture: run `./bringup.sh` next to
  the SITL map view, record with Peek/OBS/SimpleScreenRecorder, convert with
  `ffmpeg -i demo.mkv -vf "fps=10,scale=800:-1" demo.gif`.
- `architecture.png` — optional rendered export of the Mermaid diagrams
  (GitHub renders the Mermaid source in the docs natively, so this is only
  needed for slides or places without Mermaid support).
