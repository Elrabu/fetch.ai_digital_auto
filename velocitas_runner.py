import sys
import logging
import threading
from bridge_agent import verdict_done_flag

from bridge_agent import (
    run_bridge_thread,
    set_velocitas_app,
    set_main_loop,
    submit_state_for_evaluation,
)

import asyncio
velocitas_main_event_loop = asyncio.new_event_loop() #setup main event loop for handling Velocitas (part of a Scheduler architecture, single Thread with coroutines)
asyncio.set_event_loop(velocitas_main_event_loop) #make this event loop the current loop so the Velocitas SDK can register on it

from velocitas_sdk.vehicle_app import VehicleApp
from vehicle import Vehicle, vehicle #import the local vehicle instance (running in SmartWiperApp)
from timing import timer
from memory_tracker import memory
memory.start_peak_sampler()

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("Runner")

class SmartWiperApp(VehicleApp): #Velocitas SmartWiper App to implement the wiper safety logic

    def __init__(self, vehicle_model_client: Vehicle): #constructor that receives the vehicle model client
        super().__init__()
        self.Vehicle = vehicle_model_client

    async def set_wiper_mode(self, mode: str): #method to set the wiper mode in the Velocitas App
        await self.Vehicle.Body.Windshield.Front.Wiping.Mode.set(mode)
        logger.info(f"[Velocitas] Wiper set to {mode}")

    async def on_start(self): #called on startup
        async def on_hood_changed(reply): #callback when the IsOpen signal changes (current state of vehicle model)
            hood_IsOpen   = reply.get(self.Vehicle.Body.Hood.IsOpen)
            hood_OpenStatus = bool(hood_IsOpen.value)

            wiping_Mode_Reply  = await self.Vehicle.Body.Windshield.Front.Wiping.Mode.get()
            speed_reply = await self.Vehicle.Speed.get()
            wiping_mode  = str(wiping_Mode_Reply.value) if wiping_Mode_Reply.value else "OFF"
            current_speed = float(speed_reply.value or 0.0)

            state = { #get current vehicle state from the method and save it into the dictionary
                "hood_is_open":       hood_OpenStatus,
                "current_wiper_mode": wiping_mode,
                "vehicle_speed":      current_speed,
            }
            logger.info(f"[Velocitas] Hood event: {state}")

            submit_state_for_evaluation(state) #call the function from "bridge_agent.py" with the current state

        await self.Vehicle.Body.Hood.IsOpen.subscribe(on_hood_changed) #when the vehicle signal IsOpen changed (e.g. on startup) then call "on_hood_changed"
        logger.info("[Velocitas] Hood listener registered.")

async def main(): 

    set_main_loop(velocitas_main_event_loop) #create reference to this main loop for the bridge thread (bridge_agent.py)

    velocitas_vehicle_app = SmartWiperApp(vehicle) 
    set_velocitas_app(velocitas_vehicle_app)

    bridge_agent_thread = threading.Thread( #create the bridge thread that runs the bridge agent
        target=run_bridge_thread, daemon=True, name="bridge"
    )
    bridge_agent_thread.start() #starts the bridge thread
    verdict_done_flag.clear() #clears the flag verdict_done_flag

    await asyncio.gather( #runs both coroutines on the main loop:
        velocitas_vehicle_app.run(), #Velocitas application coroutine
        wait_for_LLM_verdict(), #wait_for_LLM_verdict coroutine
    )

async def wait_for_LLM_verdict(): #defines the wait_for_verdict coroutine
    velocitas_loop = asyncio.get_event_loop() #gets the main loop (from velocitas_runner.py)
    await velocitas_loop.run_in_executor(None, verdict_done_flag.wait) #suspends but not blocks the wait_for_verdict coroutine
    print("[runner] Verdict received - exiting."), 

    timer.print_summary()
    memory.print_summary()

    sys.exit(0)

velocitas_main_event_loop.run_until_complete(main()) #keep the main loop (velocitas) running until completion
