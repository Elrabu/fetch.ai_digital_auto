import logging
import os
import time
import threading
import psutil

logger = logging.getLogger("Memory")

class MemoryTracker:
    def __init__(self):
        self._process = psutil.Process(os.getpid())
        self._peak_mb: float = self._current_rss_mb()

    def _current_rss_mb(self) -> float:
        return self._process.memory_info().rss / (1024 * 1024)

    def _update_peak(self):
        current = self._current_rss_mb()
        if current > self._peak_mb:
            self._peak_mb = current

    def start_peak_sampler(self, interval_s: float = 0.25):
        def _sample():
            while True:
                self._update_peak()
                time.sleep(interval_s)
        threading.Thread(target=_sample, daemon=True, name="mem-sampler").start()

    def print_summary(self):
        """Gibt nur den Peak-Speicher aus."""
        self._update_peak()
        print("################################################################")
        print(f"Peak Memory (RSS): {self._peak_mb:>10.2f} MB")
        print("################################################################")

memory = MemoryTracker()
