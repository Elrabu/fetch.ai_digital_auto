import time
import logging

class PerformanceTimer:
    def __init__(self):
        self._program_start: float = time.perf_counter()  # t=0 Referenzpunkt
        self._startup_complete: float | None = None
        self._verdict_received: float | None = None

    def mark_startup_complete(self):
        self._startup_complete = time.perf_counter()

    def mark_verdict_received(self):
        self._verdict_received = time.perf_counter()

    def print_summary(self):
        print("################################################################")

        startup_ms = (self._startup_complete - self._program_start) * 1000
        print(f"Startup Time: {startup_ms:>10.3f} ms")

        total_ms = (self._verdict_received - self._program_start) * 1000
        print(f"Execution time: {total_ms:>10.3f} ms")
        print("################################################################")

timer = PerformanceTimer()
