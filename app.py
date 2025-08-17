from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from notion_revolut_connector import main as revolut_sync
import uvicorn
import os

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Revolut–Notion Sync Server is live."}

@app.post("/sync")
async def sync():
    try:
        result = revolut_sync()
        return {"status": "success", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
