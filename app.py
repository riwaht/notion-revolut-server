from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from src.revolut.notion_revolut_connector import main as revolut_sync, exchange_token
from src.bnp.bnp_notion_connector import main as bnp_sync
import uvicorn
import os
import asyncio

app = FastAPI()

# Store the authorization codes temporarily
auth_code_storage = {"code": None}
bnp_auth_code_storage = {"code": None}

@app.get("/")
def root():
    return {"status": "Multi-Bank Notion Sync Server is live.", "supported_banks": ["Revolut", "BNP Paribas"]}

@app.get("/callback")
async def oauth_callback(code: str = None, state: str = None):
    """Handle TrueLayer OAuth callback for Revolut"""
    if code:
        # Store the code for the sync process to use
        auth_code_storage["code"] = code
        return HTMLResponse("Revolut authorization successful! You can close this tab.")
    else:
        return JSONResponse(status_code=400, content={"error": "No authorization code received"})

@app.get("/callback/bnp")
async def bnp_oauth_callback(code: str = None, state: str = None):
    """Handle BNP Paribas OAuth callback"""
    if code:
        # Store the code for the BNP sync process to use
        bnp_auth_code_storage["code"] = code
        return HTMLResponse("BNP Paribas authorization successful! You can close this tab.")
    else:
        return JSONResponse(status_code=400, content={"error": "No authorization code received"})

@app.post("/sync/revolut")
async def sync_revolut():
    """Sync Revolut transactions only"""
    try:
        result = revolut_sync()
        return {"status": "success", "bank": "revolut", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "bank": "revolut", "message": str(e)})

@app.post("/sync/bnp")
async def sync_bnp():
    """Sync BNP Paribas transactions only"""
    try:
        result = bnp_sync()
        return {"status": "success", "bank": "bnp", "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "bank": "bnp", "message": str(e)})

@app.post("/sync")
async def sync_all():
    """Sync both Revolut and BNP Paribas transactions"""
    results = {"revolut": None, "bnp": None}
    errors = []
    
    # Sync Revolut
    try:
        print("🔄 Starting Revolut sync...")
        results["revolut"] = revolut_sync()
        print("✅ Revolut sync completed")
    except Exception as e:
        error_msg = f"Revolut sync failed: {str(e)}"
        errors.append(error_msg)
        print(f"❌ {error_msg}")
    
    # Sync BNP Paribas
    try:
        print("🔄 Starting BNP Paribas sync...")
        results["bnp"] = bnp_sync()
        print("✅ BNP Paribas sync completed")
    except Exception as e:
        error_msg = f"BNP Paribas sync failed: {str(e)}"
        errors.append(error_msg)
        print(f"❌ {error_msg}")
    
    if errors:
        return JSONResponse(
            status_code=207,  # Multi-Status
            content={
                "status": "partial_success" if results["revolut"] or results["bnp"] else "error",
                "results": results,
                "errors": errors
            }
        )
    else:
        return {"status": "success", "results": results}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
