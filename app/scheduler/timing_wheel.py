from typing import List, Any
from uuid import UUID


class WheelNode:
    def __init__(self, job_id: UUID, payload: Any = None):
        self.job_id = job_id
        self.payload = payload
        

class TimingWheel:
    def __init__(self, slots: int = 3600):
        self.slots = slots
        self.wheel: List[List[WheelNode]]  = [[] for _ in range(slots)]
        self.current_index = 0
        
    def schedule(self, job: WheelNode, delay_ticks: int):
        target_index = (self.current_index + delay_ticks) % self.slots
        self.wheel[target_index].append(job)
        
    def tick(self):
        job_to_run = self.wheel[self.current_index]
        self.wheel[self.current_index] = []
        self.current_index = (self.current_index + 1) % self.slots
        
        return job_to_run