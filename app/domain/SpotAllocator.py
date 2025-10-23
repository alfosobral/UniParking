
class SpotAllocator:
    def __init__(self):
        self._spoterr = None
        
    async def find_spot(self):
        return "A01"
    
spot_allocator: SpotAllocator | None = None