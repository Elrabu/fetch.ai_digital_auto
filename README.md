# fetch.ai_digital_auto
 An autonomous vehicle safety bridge that connects the Velocitas SDK with a Fetch.ai agent safety evaluator on Agentverse that stops
 wipers automatically when the hood is open.

## Hierarchy
```
 ├── fetch.ai_digital_auto <- local Langgraph agents
 ├── SmartWiperApp <- Velocitas Runtime 
```
## Requirements

| Tool                    | Version | Purpose                                                                 |
|-------------------------|---------|-------------------------------------------------------------------------|
| Ubuntu / WSL2           | 24.04+  | Host OS                                                                 |
| Python                  | 3.12+   | Velocitas SDK & uAgents runtime                                         |
| Docker                  | 24+     | KUKSA Data Broker container                                             |
| Agentverse Account      | —       | Agentverse API key ([agentverse.ai](https://agentverse.ai))             |

## Velocitas Runtime Setup (SmartWiperApp)
this creates the Velocitas-Runtime (Kuksa Databroker, MQTT, Mock-Service) that is used by the "vehicle" model inside "SmartWiperAgents"

### 1. Clone the template repo
```
git clone https://github.com/eclipse-velocitas/vehicle-app-python-template.git SmartWiperApp
cd SmartWiperApp
```

### 2. pull the packages declared in .velocitas.json
```
velocitas init
```

### 3. Sync devcontainer / scripts / workflows
```
velocitas sync
```

### 4. Start Velocitas Runtime
```
velocitas exec runtime-local up
```

## Setup Agentverse agent 

### 1. create an Agentverse Account

1. Go to [agentverse.ai](https://agentverse.ai)
2. Click **Sign Up** and create an account
3. Verify your email and log in

### 2. create a New Agent
if you already have agents active in the agentverse create agents by clicking on **Launch new Agent** 
<img width="1345" height="215" alt="image" src="https://github.com/user-attachments/assets/650a7254-4a7a-4778-83fa-57ab59ebfcf0" />

if this is the first agent:

1. In the left sidebar click **Agents**
2. Click **+ New Agent**
3. Choose **Blank Agent**
4. Name it something like `smartwiper-safety-xyz` (There can not be two agent with the same name)
5. Click **Create**

### 2. Get the ASI:One API key

you will need this API key for the agent that will be hosted in the agenverse

1. Go to [asi1.ai](https://asi1.ai)
2. Click **Sign Up** in the top right corner
3. Register with your email or Google account
4. Verify your email and log in
5. click on your e-mail in the bottom left corner, select **Developer** Button or go to this link: [https://asi1.ai/developer](https://asi1.ai/developer)
6. click **create new key**
7. save API key so that you can access it later (e.g. in a txt file)


### 3. create a new secret for the ASI:One API key

1. Go to **Agent Secrets** in the bottom left corner under the **Build** Tab

 <img width="1371" height="279" alt="image" src="https://github.com/user-attachments/assets/95be7574-8aaa-4647-8255-01e6be1e3a3a" />

2. click **New Secret** and enter the ASI:one API key with the name ```ASI1_API_KEY```
3. the secret is automatically used by the agentverse agent


### 4. paste the Safety Agent Code into ```agent.py```

```
import json
import os
import re

import httpx
from uagents import Context, Model


# ── Message Models (UNCHANGED — must match bridge_agent.py) ──────────────────
class WiperStateMsg(Model):
    hood_is_open:       bool
    current_wiper_mode: str
    vehicle_speed:      float

class SafetyResponseMsg(Model):
    risk_level:         str
    assessment:         str
    recommended_action: str


# ── ASI:One config ───────────────────────────────────────────────────────────
ASI1_URL   = "https://api.asi1.ai/v1/chat/completions"
ASI1_MODEL = "asi1-mini"
ASI1_KEY   = os.environ.get("ASI1_API_KEY", "").strip()

SYSTEM_PROMPT = (
    "You are a windshield wiper safety reasoner. "
    "Given hood_is_open (bool), current_wiper_mode (OFF|SLOW|MEDIUM|FAST), "
    "and vehicle_speed (km/h, float), return STRICT JSON of the form: "
    '{"risk_level":"LOW|MEDIUM|HIGH",'
    '"recommended_action":"STOP_WIPER|KEEP_WIPER|REDUCE_WIPER",'
    '"assessment":"<one short sentence>"} '
    "and NOTHING else. Heuristics: "
    "hood open with wipers active => STOP_WIPER/HIGH; "
    "hood open with wipers OFF => KEEP_WIPER/MEDIUM; "
    "speed > 130 km/h with FAST wipers => REDUCE_WIPER/MEDIUM; "
    "otherwise KEEP_WIPER/LOW."
)

VALID_RISK   = {"LOW", "MEDIUM", "HIGH"}
VALID_ACTION = {"STOP_WIPER", "KEEP_WIPER", "REDUCE_WIPER"}
_JSON_RE     = re.compile(r"\{.*\}", re.DOTALL)


# ── ASI:One call ─────────────────────────────────────────────────────────────
async def _llm_reason(msg: WiperStateMsg, ctx: Context) -> dict:
    if not ASI1_KEY:
        raise RuntimeError("ASI1_API_KEY secret is not set on Agentverse.")

    user = (
        f"hood_is_open={msg.hood_is_open}, "
        f"current_wiper_mode={msg.current_wiper_mode}, "
        f"vehicle_speed={msg.vehicle_speed}"
    )
    payload = {
        "model": ASI1_MODEL,
        "temperature": 0,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {ASI1_KEY}",
        "Content-Type":  "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(ASI1_URL, json=payload, headers=headers)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]

    ctx.logger.info(f"[asi1] raw reply: {text!r}")

    m = _JSON_RE.search(text)
    if not m:
        raise ValueError(f"LLM produced no JSON object: {text!r}")
    return json.loads(m.group(0))


# ── Hard safety policy (overrides LLM) ───────────────────────────────────────
def _apply_safety_policy(msg: WiperStateMsg, llm: dict) -> SafetyResponseMsg:
    # Rule 1: hood open + wipers active => unconditional stop
    if msg.hood_is_open and msg.current_wiper_mode.upper() != "OFF":
        return SafetyResponseMsg(
            risk_level="HIGH",
            assessment=(
                "Hood is open while wipers are active — mechanical collision "
                "risk (policy override of LLM)."
            ),
            recommended_action="STOP_WIPER",
        )

    risk   = llm.get("risk_level")
    action = llm.get("recommended_action")
    reason = str(llm.get("assessment", ""))[:240]

    if risk not in VALID_RISK or action not in VALID_ACTION:
        return SafetyResponseMsg(
            risk_level="HIGH",
            assessment=f"LLM verdict invalid ({llm!r}); failing safe.",
            recommended_action="STOP_WIPER",
        )

    return SafetyResponseMsg(
        risk_level=risk,
        assessment=reason,
        recommended_action=action,
    )


# ── Startup ──────────────────────────────────────────────────────────────────
@agent.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info(f"Safety Agent (ASI:One-backed) started: {ctx.address}")
    if not ASI1_KEY:
        ctx.logger.warning(
            "ASI1_API_KEY secret is missing — every request will fail safe."
        )
    ctx.logger.info("Ready to receive WiperStateMsg messages.")


# ── Message Handler ──────────────────────────────────────────────────────────
@agent.on_message(model=WiperStateMsg)
async def handle_wiper_state(ctx: Context, sender: str, msg: WiperStateMsg):
    ctx.logger.info(
        f"Received from {sender[:16]}…: hood={msg.hood_is_open}, "
        f"mode={msg.current_wiper_mode}, speed={msg.vehicle_speed}"
    )

    try:
        llm_verdict = await _llm_reason(msg, ctx)
        ctx.logger.info(f"[asi1] proposed: {llm_verdict}")
    except Exception as e:
        ctx.logger.exception(f"LLM call failed; failing safe: {e}")
        await ctx.send(sender, SafetyResponseMsg(
            risk_level="HIGH",
            assessment=f"LLM unavailable ({type(e).__name__}); failing safe.",
            recommended_action="STOP_WIPER",
        ))
        return

    final = _apply_safety_policy(msg, llm_verdict)
    ctx.logger.info(
        f"Final verdict → {final.risk_level} / {final.recommended_action}"
    )
    await ctx.send(sender, final)

```
### 4. copy the Agent Address
At the top of the agent page you will see a string starting with ```agent1q...```

1. save the agent address so that you can access it later (e.g. in a txt file)
2. open the file from the repository: ```fetch.ai_digital_auto/bridge_agent.py```
3. paste it in line 26 ```SAFETY_AGENT_ADDRESS = "agent1q...```

```
SAFETY_AGENT_ADDRESS = "agent1q..."
```

### 5. start the agent
Click the **Start** button in the top right of the editor

## fetch.ai_digital_auto Setup

clone the repo first:
```
git clone https://github.com/Elrabu/fetch.ai_digital_auto.git
```

### 1. Create & Activate Virtual Environment
```
python3.12 -m venv .venv
source .venv/bin/activate   
```

### 2. Install Dependencies
```
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```
cp .env.example .env
```

content:
```
AGENTVERSE_API_KEY=YOUR_AGENTVERSE_API_KEY
```

### 4. Update local agent seed

in the file ```bridge_agent.py``` in line 66 update the seed so you can create a new agent:
```
seed="YOUR_CUSTOM_SEED_PHRASE_HERE",
```


### 5. export vehicle module
in the virtual environment
```
export PYTHONPATH="/your/path/to/the/project/SmartWiperApp/gen/vehicle_model:$PYTHONPATH"
```

### 6.  Run the agents
```
python velocitas_runner.py
```

## Setup Mailbox
When running the local bridge agent for the first time, it will print:
```
INFO: Agent inspector available at:
https://agentverse.ai/inspect/?uri=http://127.0.0.1:8000&address=agent1q...
```

1. open the URL in the browser
2. if not signed in, sign in to agentverse
3. click **Connect**
4. Select **Mailbox** and click confirm

## KUKSA client setup
to change the standart values of the Velociats Runtime while is is running, install the KUKSA client:
```
pip install kuksa-client
```

start the KUKSA client:
```
kuksa-client grpc://127.0.0.1:55555
```

to change the standart values use this:
```
setValue Vehicle.Speed 0
setValue Vehicle.Body.Windshield.Front.Wiping.Mode "MEDIUM"
setValue Vehicle.Body.Hood.IsOpen true
```


