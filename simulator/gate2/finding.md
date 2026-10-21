The pinned game is ce5785313b0205af8b9477423f64b0a7b7039dcd. The harness stepped 3600 frames twice on seed 1 and once on seed 2. Exit code 0.

Same seed. The canvas pixel hash was 5f53ad56 both times. Math.random was called 205205 times both times. The camera and the stepped clock matched. Playwright's PNG hash did not match. `screenshotStable` is false. The check uses the canvas buffer.

Different seed. The pixel hash was 18f5fb25. Math.random was called 205109 times. The seed reaches the simulation.

The draw count stayed unstable until `AudioContext.currentTime` followed the stepped clock. Menu music calls `Math.random` from `noise()` in `js/core/audio.js`. That audio clock is wall time.

Sprite sheet requests for the backdrop cast do not finish in this process. The picture is the menu backdrop with whatever had decoded when the stepped loop started. The pixel hash still matched.

No bot. No parity work.

Run it with `POKESURVIVOR_DIR` set to that checkout. Playwright has to be installed for `simulator/gate2`. The numbers above are in `finding.json` from the run that exited 0.
