from uagents import Model
from typing import Literal

class SafetyRequest(Model):
    hood_is_open: bool
    current_wiper_mode: str
    vehicle_speed: float
    request_id: str


class SafetyResponse(Model):
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    assessment: str
    recommended_action: Literal["STOP_WIPER", "KEEP_WIPER", "REDUCE_WIPER"]
    request_id: str