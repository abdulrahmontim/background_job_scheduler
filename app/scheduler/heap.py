from datetime import datetime
from uuid import UUID


class JobNode:
    
    def __init__(self, job_id: UUID, effective_priority: int, scheduled_at: datetime):
        self.job_id = job_id
        self.effective_priority = effective_priority
        self.scheduled_at = scheduled_at
        
        
    def __lt__(self, other: "JobNode"):
        if self.effective_priority != other.effective_priority:
            return self.effective_priority < other.effective_priority
    
        if self.scheduled_at != other.scheduled_at:
            return self.scheduled_at < other.scheduled_at

        return str(self.job_id) < str(other.job_id)
    
    def __repr__(self) -> str:
        return f"JobNode: {self.job_id} | Priority: {self.effective_priority}"
    
    
    
class MinHeap:
    def __init__(self) -> None:
        self._heap: list[JobNode] = []
        
    def push(self, node: "JobNode"):
        self._heap.append(node)
        self._bubble_up(len(self._heap) - 1)
        
    def pop(self):
        if not self._heap:
            return None
        if len(self._heap) == 1:
            return self._heap.pop()
        
        root=self._heap[0]
        self._heap[0] = self._heap.pop()
        self._bubble_down(0)
        
        return root
    
    def _bubble_up(self, index: int):
        parent_index = (index - 1) // 2
        
        if index > 0 and self._heap[index] < self._heap[parent_index]:
            self._heap[index], self._heap[parent_index] = self._heap[parent_index], self._heap[index]
            self._bubble_up(parent_index)
            
    def _bubble_down(self, index: int):
        smallest = index
        left_child = 2 * index + 1
        right_child = 2 * index + 2
        
        if left_child < len(self._heap) and self._heap[left_child] < self._heap[smallest]:
            smallest = left_child
            
        if right_child < len(self._heap) and self._heap[right_child] < self._heap[smallest]:
            smallest = right_child
            
        if smallest != index:
            self._heap[index], self._heap[smallest] = self._heap[smallest], self._heap[index]
            self._bubble_down(smallest)
            
    def peek(self):
        return self._heap[0] if self._heap else None
    
    def __len__(self):
        return len(self._heap)
    
        