"""
Revolut to Notion Sync Server - FastAPI application.
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from src.notion.notion_utils import retry_failed_transactions
from src.revolut.revolut_connector import RevolutConnector

app = FastAPI(title="Revolut to Notion Sync")

# Store authorization code temporarily
auth_code_storage = {"code": None}


@app.get("/")
def root():
    return {"status": "Revolut to Notion Sync Server is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Revolut to Notion Sync",
    }


@app.get("/callback")
async def oauth_callback(code: str = None, state: str = None):
    """Handle TrueLayer OAuth callback."""
    if code:
        auth_code_storage["code"] = code
        return HTMLResponse("Authorization successful! You can close this tab.")
    return JSONResponse(status_code=400, content={"error": "No authorization code received"})


@app.get("/auth")
async def get_auth_url():
    """Get OAuth authorization URL."""
    try:
        connector = RevolutConnector()
        auth_url = connector.get_auth_url()
        return {"auth_url": auth_url, "message": "Visit this URL to authorize"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/exchange")
async def exchange_token():
    """Exchange authorization code for access token."""
    code = auth_code_storage["code"]
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code. Complete OAuth flow first.")

    try:
        connector = RevolutConnector()
        connector.exchange_token(code)
        auth_code_storage["code"] = None
        return {"status": "success", "message": "Token exchanged successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync")
async def sync():
    """Sync transactions from Revolut to Notion."""
    try:
        connector = RevolutConnector()
        result = connector.sync_transactions()
        return {"status": "success", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/retry-failed")
async def retry_failed():
    """Retry failed transactions."""
    try:
        retry_failed_transactions()
        return {"status": "success", "message": "Retry completed"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
