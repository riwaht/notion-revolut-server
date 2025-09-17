from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from src.revolut.notion_revolut_connector import main as revolut_sync, exchange_token
from src.notion.notion_utils import retry_failed_transactions
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
    """Sync new transactions from Revolut to Notion"""
    try:
        result = revolut_sync()
        return {"status": "success", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/retry-failed")
async def retry_failed():
    """Retry all previously failed transactions"""
    try:
        print("🔄 Manual retry triggered via API")
        retry_failed_transactions()
        return {"status": "success", "message": "Failed transaction retry completed"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "service": "Revolut–Notion Sync Server",
        "features": {
            "retry_mechanism": "enabled",
            "error_logging": "enabled", 
            "graceful_degradation": "enabled"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
