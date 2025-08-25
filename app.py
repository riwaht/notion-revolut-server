from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from src.revolut.notion_revolut_connector import main as revolut_sync, exchange_token
import uvicorn
import os

app = FastAPI()

# Store the authorization code temporarily
auth_code_storage = {"code": None}

@app.get("/")
def root():
    return {"status": "Revolut–Notion Sync Server is live."}

@app.get("/callback")
async def oauth_callback(code: str = None, state: str = None):
    """Handle TrueLayer OAuth callback"""
    if code:
        # Store the code for the sync process to use
        auth_code_storage["code"] = code
        return HTMLResponse("Authorization successful! You can close this tab.")
    else:
        return JSONResponse(status_code=400, content={"error": "No authorization code received"})

@app.post("/sync")
async def sync():
    try:
        result = revolut_sync()
        return {"status": "success", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
