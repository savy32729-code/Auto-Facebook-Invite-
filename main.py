import asyncio
import csv
import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


app = FastAPI(
    title="Facebook Invite Manager",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

campaigns = {}
users = []
logs = []


class CampaignRequest(BaseModel):
    target: str = Field(..., min_length=1)
    limit: int = Field(default=50, ge=1, le=500)
    message: str = ""


@app.get("/")
async def home():
    return FileResponse(INDEX_FILE)


@app.get("/api/status")
async def status():
    return {
        "success": True,
        "app": "Facebook Invite Manager",
        "version": "1.0.0"
    }


@app.get("/api/stats")
async def stats():
    invited = sum(1 for x in logs if x["status"] == "invited")
    pending = sum(1 for x in logs if x["status"] == "pending")
    failed = sum(1 for x in logs if x["status"] == "failed")

    return {
        "total": len(logs),
        "invited": invited,
        "pending": pending,
        "failed": failed
    }


@app.post("/api/users/upload")
async def upload_users(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "File name is required")

    content = await file.read()

    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        imported = []

        for row in reader:
            name = (row.get("name") or "").strip()
            facebook_id = (
                row.get("facebook_id")
                or row.get("id")
                or ""
            ).strip()

            if name or facebook_id:
                imported.append({
                    "name": name or "Facebook User",
                    "facebook_id": facebook_id
                })

        if not imported:
            raise HTTPException(
                400,
                "CSV must contain name or facebook_id"
            )

        users.clear()
        users.extend(imported)

        return {
            "success": True,
            "count": len(imported),
            "users": imported[:20]
        }

    except UnicodeDecodeError:
        raise HTTPException(
            400,
            "CSV must be UTF-8 encoded"
        )


@app.get("/api/users")
async def get_users():
    return {
        "success": True,
        "count": len(users),
        "users": users
    }


@app.post("/api/campaign/start")
async def start_campaign(data: CampaignRequest):

    if not users:
        raise HTTPException(
            400,
            "Please upload an approved/consented user list first."
        )

    campaign_id = str(uuid.uuid4())

    selected_users = users[:data.limit]

    campaigns[campaign_id] = {
        "id": campaign_id,
        "target": data.target,
        "message": data.message,
        "total": len(selected_users),
        "status": "running",
        "created_at": datetime.now().isoformat()
    }

    asyncio.create_task(
        process_campaign(
            campaign_id,
            selected_users
        )
    )

    return {
        "success": True,
        "campaign_id": campaign_id,
        "total": len(selected_users),
        "message": "Campaign started"
    }


async def process_campaign(campaign_id, selected_users):

    for user in selected_users:

        await asyncio.sleep(0.15)

        # Version 1 only records the action.
        # Real Facebook API actions belong here after
        # Meta OAuth/API permissions are configured.

        log_item = {
            "id": str(uuid.uuid4()),
            "campaign_id": campaign_id,
            "name": user["name"],
            "facebook_id": user["facebook_id"],
            "status": "pending",
            "time": datetime.now().isoformat()
        }

        logs.insert(0, log_item)

    if campaign_id in campaigns:
        campaigns[campaign_id]["status"] = "completed"


@app.get("/api/campaigns")
async def get_campaigns():
    return {
        "success": True,
        "campaigns": list(campaigns.values())
    }


@app.get("/api/logs")
async def get_logs():
    return {
        "success": True,
        "logs": logs[:200]
    }


@app.post("/api/campaign/{campaign_id}/stop")
async def stop_campaign(campaign_id: str):

    if campaign_id not in campaigns:
        raise HTTPException(404, "Campaign not found")

    campaigns[campaign_id]["status"] = "stopped"

    return {
        "success": True,
        "message": "Campaign stopped"
    }
