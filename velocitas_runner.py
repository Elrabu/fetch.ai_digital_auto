# velocitas_runner.py
import sys
import logging
import threading
from bridge_agent import verdict_done

# ── 1. Import bridge FIRST so it claims its own event loop ───────────────────
from bridge_agent import (
    run_bridge_thread,
    set_velocitas_app,
    set_main_loop,
    submit_state_for_evaluation,
)

# ── 2. Restore a fresh main loop for Velocitas / gRPC ────────────────────────
import asyncio
_main_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_main_loop)

from velocitas_sdk.vehicle_app import VehicleApp
from vehicle import Vehicle, vehicle

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("Runner")

# ── Velocitas App ─────────────────────────────────────────────────────────────
class SmartWiperApp(VehicleApp):

    def __init__(self, vehicle_client: Vehicle):
        super().__init__()
        self.Vehicle = vehicle_client

    async def set_wiper_mode(self, mode: str):
        await self.Vehicle.Body.Windshield.Front.Wiping.Mode.set(mode)
        logger.info(f"[Velocitas] Wiper set to {mode}")

    async def on_start(self):

        async def on_hood_changed(reply):
            hood_dp   = reply.get(self.Vehicle.Body.Hood.IsOpen)
            hood_open = bool(hood_dp.value)

            mode_reply  = await self.Vehicle.Body.Windshield.Front.Wiping.Mode.get()
            speed_reply = await self.Vehicle.Speed.get()
            mode  = str(mode_reply.value) if mode_reply.value else "OFF"
            speed = float(speed_reply.value or 0.0)

            state = {
                "hood_is_open":       hood_open,
                "current_wiper_mode": mode,
                "vehicle_speed":      speed,
            }
            logger.info(f"[Velocitas] Hood event → {state}")
            submit_state_for_evaluation(state)

        await self.Vehicle.Body.Hood.IsOpen.subscribe(on_hood_changed)
        logger.info("[Velocitas] Hood listener registered.")

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    # Register main loop with bridge (for cross-loop SDK calls)
    set_main_loop(_main_loop)

    # Create and register Velocitas app
    app = SmartWiperApp(vehicle)
    set_velocitas_app(app)

    # Start bridge daemon thread (runs on its own loop)
    bridge_thread = threading.Thread(
        target=run_bridge_thread, daemon=True, name="bridge"
    )
    bridge_thread.start()

    verdict_done.clear()

    await asyncio.gather(
        app.run(),
        _wait_for_verdict(),
    )

async def _wait_for_verdict():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, verdict_done.wait)  # blocks executor, not event loop
    print("[runner] Verdict received — exiting.")
    sys.exit(0)

if __name__ == "__main__":
    _main_loop.run_until_complete(main())
