"""Gmail integration API endpoints."""

import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import get_settings
from ..logging_config import get_logger
from ..services.gmail.client import GmailClient, _set_active_gmail_user_id

logger = get_logger(__name__)

router = APIRouter(prefix="/gmail", tags=["gmail"])


class ConnectRequest(BaseModel):
    """Request to connect Gmail."""
    userId: str


class StatusRequest(BaseModel):
    """Request to check Gmail status."""
    userId: str
    connectionRequestId: Optional[str] = None


class DisconnectRequest(BaseModel):
    """Request to disconnect Gmail."""
    userId: str
    connectionRequestId: Optional[str] = None


@router.post("/connect")
async def connect_gmail(request: ConnectRequest) -> Dict[str, Any]:
    """Initiate Gmail connection via Composio."""

    try:
        settings = get_settings()

        if not settings.composio_api_key:
            raise HTTPException(
                status_code=400,
                detail="Composio API key not configured"
            )

        # Need auth_config_id for proper OAuth flow
        auth_config_id = settings.composio_gmail_auth_config_id
        if not auth_config_id:
            raise HTTPException(
                status_code=400,
                detail="Missing auth_config_id. Set COMPOSIO_GMAIL_AUTH_CONFIG_ID environment variable."
            )

        user_id = request.userId or f"web-{hash(request.userId)}"
        _set_active_gmail_user_id(user_id)

        try:
            from ..services.gmail.client import _get_composio_client
            client = _get_composio_client()
            req = client.connected_accounts.initiate(user_id=user_id, auth_config_id=auth_config_id)

            redirect_url = getattr(req, "redirect_url", None) or getattr(req, "redirectUrl", None)
            connection_request_id = getattr(req, "id", None)

            return {
                "ok": True,
                "redirect_url": redirect_url,
                "connection_request_id": connection_request_id,
                "user_id": user_id,
                "message": "Authorization URL generated successfully"
            }

        except Exception as exc:
            logger.error(f"Gmail connect failed for user {user_id}: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initiate Gmail connect: {str(exc)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect Gmail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/status")
async def check_gmail_status(request: StatusRequest) -> Dict[str, Any]:
    """Check Gmail connection status."""

    try:
        # Debug: Let's see what Composio returns directly
        gmail_client = GmailClient()

        if not gmail_client.is_operational:
            return {
                "ok": True,
                "connected": False,
                "status": "SERVICE_UNAVAILABLE",
                "message": "Gmail service not operational"
            }

        # Check if user has active Gmail connection using the correct API
        is_connected = await gmail_client.verify_gmail_connection(request.userId)

        if not is_connected:
            return {
                "ok": True,
                "connected": False,
                "status": "NOT_CONNECTED",
                "message": f"Gmail not connected for user {request.userId}"
            }

        # Cache this user ID as the active Gmail user for future lookups
        logger.info(f"📧 Gmail connection verified - caching user ID: {request.userId}")
        _set_active_gmail_user_id(request.userId)

        # Get profile information
        profile_data = await gmail_client.retrieve_user_profile(request.userId)
        email = profile_data.get("emailAddress", "") if profile_data else ""

        return {
            "ok": True,
            "connected": True,
            "status": "CONNECTED",
            "email": email,
            "profile": profile_data,
            "profile_source": "fetched",
            "user_id": request.userId,
            "message": f"Connected as {email}" if email else "Gmail connected"
        }

    except Exception as e:
        logger.error(f"Failed to check Gmail status: {e}")
        return {
            "ok": True,
            "connected": False,
            "status": "ERROR",
            "error": str(e)
        }


@router.post("/disconnect")
async def disconnect_gmail(request: DisconnectRequest) -> Dict[str, Any]:
    """Disconnect Gmail integration."""

    try:
        gmail_client = GmailClient()

        # Try to revoke the connection
        success = await gmail_client.disconnect_gmail_account(request.userId)

        if success:
            return {
                "ok": True,
                "message": "Gmail disconnected successfully"
            }
        else:
            return {
                "ok": True,
                "message": "Gmail connection removed (may not have been connected)"
            }

    except Exception as e:
        logger.error(f"Failed to disconnect Gmail: {e}")
        raise HTTPException(status_code=500, detail=str(e))