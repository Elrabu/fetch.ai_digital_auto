import logging
import os
import time
import threading
import psutil

class MemoryTracker:
    def __init__(self): 
        self._process = psutil.Process(os.getpid()) #get the psutil handle for the current process
        self._peak_mb: float = self._current_rss_mb() #get the current RSS values as a starting point

    def _current_rss_mb(self) -> float:
        return self._process.memory_info().rss / (1024 * 1024) #calculate current RSS value in mb

    def _update_peak(self):
        current = self._current_rss_mb() #check current memory usage
        if current > self._peak_mb: #set current value variable if current value is higher than the peak
            self._peak_mb = current #update peak value

    def start_peak_sampler(self, interval_s: float = 0.25): #start periodic thread sampling
        def _sample():
            while True:
                self._update_peak() #measure peak through the corresponding function
                time.sleep(interval_s)
        threading.Thread(target=_sample, daemon=True, name="memory-sampler").start() #start new thread and mae sure that it is stopped on program end

    def print_summary(self): #print the peak memory usage value
        """Gibt nur den Peak-Speicher aus."""
        self._update_peak()
        print("################################################################")
        print(f"Peak Memory (RSS): {self._peak_mb:>10.2f} MB")
        print("################################################################")

memory = MemoryTracker() # register the class as a global Singleton, so that it can be used in the whole project
