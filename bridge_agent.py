import asyncio
import logging
import queue
import threading
from typing import Optional

bridge_agent_event_loop = asyncio.new_event_loop()  # create new event Loop for bridge agent (part of a Scheduler architecture, single Thread with coroutines)
asyncio.set_event_loop(bridge_agent_event_loop) #set the bridge loop as the event loop so every new uagent registers on this loop

from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low
from timing import timer
from memory_tracker import memory

logger = logging.getLogger("Bridge") #set up logging
logging.getLogger("uagents.registration").setLevel(logging.ERROR)

verdict_done_flag = threading.Event() #creates a new boolean flag that can be set in the code

SAFETY_AGENT_ADDRESS = "agent1q25d7k7xddjh45xk5uqx0l3c9pav3m2l7zwc77fncfy52fsks0ya22z7g3h" #set Agentverse agent address

velocitas_vehicle_state_queue: queue.Queue = queue.Queue() #create Queue to receive Velocitas dictionaries (current vehicle sensor state)
velocitas_vehicle_app = None #reference to velocitas will be set here at runtime
velocitas_app_main_loop: Optional[asyncio.AbstractEventLoop] = None

class WiperStateMsg(Model): #setup message schema for outbound messages from bridge to safety agent 
    hood_is_open:       bool
    current_wiper_mode: str
    vehicle_speed:      float

class SafetyResponseMsg(Model): #setup inbound message schema for messages by the safety agent
    risk_level:          str  # LOW | MEDIUM | HIGH
    assessment:          str
    recommended_action:  str  # STOP_WIPER | KEEP_WIPER | REDUCE_WIPER

def set_velocitas_app(app): #setter to inject the Velocitas app instance from the runner (connection of uAgents to Velocitas code)
    global velocitas_vehicle_app
    velocitas_vehicle_app = app

def set_main_loop(loop: asyncio.AbstractEventLoop): #setter to inject the Velocitas main event loop (connection of uAgents to Velocitas code)
    global velocitas_app_main_loop
    velocitas_app_main_loop = loop

def submit_state_for_evaluation(state: dict): #enqueue the vehicle state dictionary
    velocitas_vehicle_state_queue.put(state)
    logger.info(f"[Bridge] Event enqueued: {state}")

async def _run_on_main(velocitas_coroutine): # allows bridge agent loop to safely trigger Velocitas actions in the main loop
    velocitas_runner_loop = asyncio.run_coroutine_threadsafe(velocitas_coroutine, velocitas_app_main_loop) #submits coroutine to the main loop
    return await bridge_agent_event_loop.run_in_executor(None, velocitas_runner_loop.result) # wait for results without blocking the bridge loop

bridge_agent = Agent( #set up the bridge uAgent and define its properties (name, seed, mailbox, network)
    name="smartwiper_bridge",
    seed="smartwiper_bridge_seed_v2",
    mailbox=True,
    network="testnet",
)

fund_agent_if_low(bridge_agent.wallet.address())

@bridge_agent.on_message(model=SafetyResponseMsg) #triggers when a message of type "SafetyResponseMsg" arrives
async def on_safety_response(ctx: Context, sender: str, msg: SafetyResponseMsg): # function to trigger the corresponding Vehicle App action

    timer.mark_verdict_received()

    logger.info(f"[Bridge] <- Safety response: {msg.risk_level} / {msg.recommended_action}")
    print(f"  verdict={msg.risk_level}  action={msg.recommended_action}")

    if msg.recommended_action == "STOP_WIPER":
        await _run_on_main(velocitas_vehicle_app.set_wiper_mode("OFF"))
    elif msg.recommended_action == "REDUCE_WIPER":
        await _run_on_main(velocitas_vehicle_app.set_wiper_mode("SLOW"))
    else:
        logger.info("[Bridge] No wiper change needed.")

    verdict_done_flag.set() #set the flag verdict_done_flag

agent_context: Optional[Context] = None #placeholder to hold agent context on startup

@bridge_agent.on_event("startup") #on startup, provides the agent with the Fetch.ai context, so that it doesnt need global references
async def on_startup(ctx: Context): #on startup the agent receives the agent context
    global agent_context
    agent_context = ctx

    timer.mark_startup_complete()

    ctx.logger.info("[Bridge] Startup: launching event consumer.")
    asyncio.ensure_future(vehicle_queue_consumer()) #schedules the "vehicle_queue_consumer" coroutine as a background task on the current event loop

async def vehicle_queue_consumer(): #coroutine that drains the queue (vehicle state) and forwards it
    logger.info("[Bridge] Event forwarder online — target=%s", SAFETY_AGENT_ADDRESS[:16] + "…")

    while True:
        try: #trys to pull a queued event
            state = velocitas_vehicle_state_queue.get_nowait()
        except queue.Empty: #if nothing is currently queued, retry
            await asyncio.sleep(0.1)
            continue

        print(f"\n=== BRIDGE: Processing event: {state}") #prints the current state
        msg = WiperStateMsg( #map the respective field from the dictionary to the message
            hood_is_open=state["hood_is_open"],
            current_wiper_mode=state["current_wiper_mode"],
            vehicle_speed=state["vehicle_speed"],
        )

        logger.info(f"[Bridge] -> Agentverse safety agent")

        await agent_context.send(SAFETY_AGENT_ADDRESS, msg) #sends the message to the safety agent in the agentverse

def run_bridge_thread(): #thread entry point that runs the bridge agent on its own event loop
    bridge_agent_event_loop.run_until_complete(bridge_agent.run_async()) #own bridge event loop to run alongside the Velocitas thread
