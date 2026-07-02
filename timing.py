import time
import logging

class PerformanceTimer:
    def __init__(self):
        self._program_start: float = time.perf_counter()  # starting time of the program is saved as a high-resolution counter
        self._startup_complete: float | None = None #placeholder variable for completed startup
        self._verdict_received: float | None = None #placeholder variable for received verdict

    def mark_startup_complete(self):
        self._startup_complete = time.perf_counter() #save current time as startup complete

    def mark_verdict_received(self):
        self._verdict_received = time.perf_counter() #save current time as verdict received

    def print_summary(self): #print the final values in milliseconds (ms)
        print("################################################################")

        startup_ms = (self._startup_complete - self._program_start) * 1000
        print(f"Startup Time: {startup_ms:>10.3f} ms")

        total_ms = (self._verdict_received - self._program_start) * 1000
        print(f"Execution time: {total_ms:>10.3f} ms")

        print("################################################################")

timer = PerformanceTimer() #register the class as a global Singleton, to be useable in the whole project
