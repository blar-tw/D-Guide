# Images

Media assets referenced by the docs and the root README.

Wanted here (see the README roadmap):

- `demo.gif` — a SITL mission recording: enter a destination, watch takeoff →
  waypoint following → landing. Suggested capture: run `./bringup.sh` next to
  the SITL map view, record with Peek/OBS/SimpleScreenRecorder, convert with
  `ffmpeg -i demo.mkv -vf "fps=10,scale=800:-1" demo.gif`.
- `architecture.png` — the system architecture overview shown at the top of
  the root README's Architecture section (your own hand-made diagram). The
  Mermaid source below it stays as the precise node/topic reference.
- `hardware.png` — the drone hardware overview shown in the root README's
  Hardware section (X500 V2 frame + Pi + Pixhawk + LiDAR/camera).
