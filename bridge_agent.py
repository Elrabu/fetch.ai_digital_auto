# bridge_agent.py
import asyncio
import logging
import queue
import threading
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# ── Create bridge loop FIRST, before Agent() is constructed ──────────────────
_bridge_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_bridge_loop)

from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low

logger = logging.getLogger("Bridge")
logging.getLogger("uagents.registration").setLevel(logging.ERROR)

verdict_done = threading.Event()

# ── Configuration ─────────────────────────────────────────────────────────────
SAFETY_AGENT_ADDRESS = "YOUR_AGENTVERSE_AGENT_ADDRESS"

# ── Shared state ──────────────────────────────────────────────────────────────
_event_queue: queue.Queue = queue.Queue()
_velocitas_app = None
_main_loop: Optional[asyncio.AbstractEventLoop] = None

# ── Models ────────────────────────────────────────────────────────────────────
class WiperStateMsg(Model):
    hood_is_open:       bool
    current_wiper_mode: str
    vehicle_speed:      float

class SafetyResponseMsg(Model):
    risk_level:          str  # LOW | MEDIUM | HIGH
    assessment:          str
    recommended_action:  str  # STOP_WIPER | KEEP_WIPER | REDUCE_WIPER

# ── Setters called from velocitas_runner.py ───────────────────────────────────
def set_velocitas_app(app):
    global _velocitas_app
    _velocitas_app = app

def set_main_loop(loop: asyncio.AbstractEventLoop):
    global _main_loop
    _main_loop = loop

def submit_state_for_evaluation(state: dict):
    _event_queue.put(state)
    logger.info(f"[Bridge] Event enqueued: {state}")

# ── Helpers ───────────────────────────────────────────────────────────────────
async def _run_on_main(coro):
    """Schedule a Velocitas SDK coroutine on the main event loop and await result."""
    fut = asyncio.run_coroutine_threadsafe(coro, _main_loop)
    return await _bridge_loop.run_in_executor(None, fut.result)

# ── Bridge agent ──────────────────────────────────────────────────────────────
bridge_agent = Agent(
    name="smartwiper_bridge",
    seed="YOUR_CUSTOM_SEED_PHRASE_HERE",
    mailbox=True,
    network="testnet",
)

fund_agent_if_low(bridge_agent.wallet.address())

# ── Message handlers ──────────────────────────────────────────────────────────
@bridge_agent.on_message(model=SafetyResponseMsg)
async def on_safety_response(ctx: Context, sender: str, msg: SafetyResponseMsg):
    logger.info(f"[Bridge] <- Safety response: {msg.risk_level} / {msg.recommended_action}")
    print(f"  verdict={msg.risk_level}  action={msg.recommended_action}")

    if msg.recommended_action == "STOP_WIPER":
        await _run_on_main(_velocitas_app.set_wiper_mode("OFF"))
    elif msg.recommended_action == "REDUCE_WIPER":
        await _run_on_main(_velocitas_app.set_wiper_mode("SLOW"))
    else:
        logger.info("[Bridge] No wiper change needed.")
    verdict_done.set() 

_agent_ctx: Optional[Context] = None

@bridge_agent.on_event("startup")
async def on_startup(ctx: Context):
    global _agent_ctx
    _agent_ctx = ctx
    ctx.logger.info("[Bridge] Startup: launching event consumer.")
    asyncio.ensure_future(_event_consumer())

async def _event_consumer():
    logger.info("[Bridge] Event forwarder online — target=%s", SAFETY_AGENT_ADDRESS[:16] + "…")

    while True:
        try:
            state = _event_queue.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.1)
            continue

        print(f"\n=== BRIDGE: Processing event: {state}")
        msg = WiperStateMsg(
            hood_is_open=state["hood_is_open"],
            current_wiper_mode=state["current_wiper_mode"],
            vehicle_speed=state["vehicle_speed"],
        )

        if _agent_ctx is None:
            logger.error("[Bridge] Context not ready yet, dropping event.")
            continue

        logger.info(f"[Bridge] -> Agentverse safety agent")
        await _agent_ctx.send(SAFETY_AGENT_ADDRESS, msg)

# ── Thread entry point ────────────────────────────────────────────────────────
def run_bridge_thread():
    """Run the bridge agent on its own pre-created event loop."""
    _bridge_loop.run_until_complete(bridge_agent.run_async())
