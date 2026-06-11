from fastapi import APIRouter

router = APIRouter()



@router.get("/stream")
async def event_stream():
    ...