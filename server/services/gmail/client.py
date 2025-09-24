"""Gmail client using Composio API."""

import json
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...config import get_settings
from ...logging_config import get_logger

logger = get_logger(__name__)

_CLIENT_LOCK = threading.Lock()
_CLIENT: Optional[Any] = None

_PROFILE_CACHE: Dict[str, Dict[str, Any]] = {}
_PROFILE_CACHE_LOCK = threading.Lock()
_ACTIVE_USER_ID_LOCK = threading.Lock()
_ACTIVE_USER_ID: Optional[str] = None


def _normalized(value: Optional[str]) -> str:
    return (value or "").strip()


def _set_active_gmail_user_id(user_id: Optional[str]) -> None:
    sanitized = _normalized(user_id)
    with _ACTIVE_USER_ID_LOCK:
        global _ACTIVE_USER_ID
        _ACTIVE_USER_ID = sanitized or None


def get_active_gmail_user_id() -> Optional[str]:
    with _ACTIVE_USER_ID_LOCK:
        return _ACTIVE_USER_ID


def resolve_gmail_user_id(requested_user_id: Optional[str] = None) -> Optional[str]:
    """Resolve the actual Gmail user ID to use for Composio calls.

    Maps web interface session IDs to actual Gmail connection user IDs.

    Priority:
    1. If requested_user_id is already a valid Gmail user ID, use it
    2. If requested_user_id is "web_user" or similar, look up the actual connected user ID
    3. Use active Gmail user ID if available
    4. Auto-discover any connected Gmail account
    """
    logger.info(f"🔍 Resolving Gmail user ID for request: {requested_user_id}")

    # If we have a specific user ID that's not a generic web session ID, use it
    if requested_user_id and not requested_user_id.startswith("web"):
        logger.info(f"✅ Using provided user ID directly: {requested_user_id}")
        return requested_user_id

    # Check if we have an active Gmail user ID cached
    active_id = get_active_gmail_user_id()
    if active_id:
        logger.info(f"✅ Using cached Gmail user ID: {active_id}")
        return active_id

    logger.info(f"❌ No cached Gmail user ID found for request: {requested_user_id}")

    # Quick auto-discovery attempt - no hanging loops
    try:
        logger.info("🔄 Attempting Gmail auto-discovery...")
        client = _get_composio_client()
        logger.info("🔍 Querying connected Gmail accounts...")

        # Simple query with timeout protection
        logger.info("📡 Making API call to list connected accounts...")
        items = client.connected_accounts.list(toolkit_slugs=["GMAIL"], statuses=["ACTIVE"])

        logger.info(f"📊 API response type: {type(items)}")
        logger.info(f"📊 API response: {items}")

        data = getattr(items, "data", None)
        if data is None and isinstance(items, dict):
            data = items.get("data")

        logger.info(f"📊 Extracted data: {data}")
        logger.info(f"📊 Data type: {type(data)}")

        if data and len(data) > 0:
            logger.info(f"✅ Found {len(data)} connected accounts")
            account = data[0]
            logger.info(f"📊 First account: {account}")
            logger.info(f"📊 Account type: {type(account)}")

            user_id = None

            if hasattr(account, "user_id"):
                user_id = getattr(account, "user_id", None)
                logger.info(f"📧 Got user_id from attribute: {user_id}")
            elif isinstance(account, dict):
                user_id = account.get("user_id")
                logger.info(f"📧 Got user_id from dict: {user_id}")

            if user_id:
                _set_active_gmail_user_id(user_id)
                logger.info(f"✅ Successfully resolved Gmail user ID: {user_id}")
                return user_id
            else:
                logger.warning(f"❌ No user_id found in account: {account}")
        else:
            logger.warning("❌ No Gmail connections found in response")

    except Exception as e:
        logger.error(f"❌ Gmail auto-discovery failed: {e}")
        logger.exception("Gmail auto-discovery exception details:")

    # If we can't find it quickly, just fail gracefully
    logger.warning(f"❌ Gmail user ID not available for: {requested_user_id}")
    return None


def _gmail_import_client():
    logger.info("🔄 Attempting to import Composio client...")
    try:
        from composio import Composio  # type: ignore
        logger.info("✅ Composio imported successfully")
        return Composio
    except ImportError as e:
        logger.error(f"❌ Composio not installed: {e}. Install with: pip install composio-core")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error importing Composio: {e}")
        return None


def _get_composio_client():
    global _CLIENT
    logger.info("🔄 Getting Composio client...")

    if _CLIENT is not None:
        logger.info("✅ Using cached Composio client")
        return _CLIENT

    with _CLIENT_LOCK:
        if _CLIENT is None:
            logger.info("🔄 Initializing new Composio client...")
            settings = get_settings()
            Composio = _gmail_import_client()

            if Composio is None:
                logger.error("❌ Composio library not available")
                raise RuntimeError("Composio library not available")

            api_key = settings.composio_api_key
            logger.info(f"🔑 Composio API key {'configured' if api_key else 'not configured'}")

            try:
                if api_key:
                    logger.info("🔄 Creating Composio client with API key...")
                    _CLIENT = Composio(api_key=api_key)
                else:
                    logger.info("🔄 Creating Composio client without API key...")
                    _CLIENT = Composio()
                logger.info("✅ Composio client created successfully")
            except TypeError as exc:
                logger.error(f"❌ Composio SDK version issue: {exc}")
                if api_key:
                    raise RuntimeError(
                        "Installed Composio SDK does not accept the api_key argument; upgrade the SDK or remove COMPOSIO_API_KEY."
                    ) from exc
                logger.info("🔄 Retrying without API key...")
                _CLIENT = Composio()
            except Exception as exc:
                logger.error(f"❌ Failed to create Composio client: {exc}")
                raise

    logger.info("✅ Composio client ready")
    return _CLIENT


def _normalize_tool_response(response: Any) -> Dict[str, Any]:
    """Normalize Composio tool response."""
    if isinstance(response, dict):
        return response

    # Try to extract data from response object
    try:
        if hasattr(response, 'data'):
            return response.data if isinstance(response.data, dict) else {"data": response.data}
        elif hasattr(response, '__dict__'):
            return response.__dict__
        else:
            return {"result": str(response)}
    except Exception:
        return {"result": str(response)}


def execute_gmail_tool(
    tool_name: str,
    composio_user_id: str,
    *,
    arguments: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a Gmail tool via Composio."""
    logger.info(f"🔧 Executing Gmail tool: {tool_name}")
    logger.info(f"📧 Composio user ID: {composio_user_id}")
    logger.info(f"📝 Raw arguments: {arguments}")

    prepared_arguments: Dict[str, Any] = {}
    if isinstance(arguments, dict):
        for key, value in arguments.items():
            if value is not None:
                prepared_arguments[key] = value

    prepared_arguments.setdefault("user_id", "me")
    logger.info(f"✅ Prepared arguments: {prepared_arguments}")

    try:
        logger.info("🔄 Getting Composio client for tool execution...")
        client = _get_composio_client()

        logger.info(f"🔄 Executing tool {tool_name} with Composio...")
        logger.info(f"🔧 Tool execution details:")
        logger.info(f"  - Tool: {tool_name}")
        logger.info(f"  - User ID: {composio_user_id}")
        logger.info(f"  - Arguments: {prepared_arguments}")

        result = client.client.tools.execute(
            tool_name,
            user_id=composio_user_id,
            arguments=prepared_arguments,
        )

        logger.info(f"✅ Tool execution completed successfully")
        logger.info(f"📊 Raw result type: {type(result)}")
        logger.info(f"📊 Raw result: {result}")

        normalized_result = _normalize_tool_response(result)
        logger.info(f"📊 Normalized result: {normalized_result}")

        return normalized_result

    except Exception as exc:
        logger.error(f"❌ Gmail tool execution failed: {exc}")
        logger.exception(
            "Gmail tool execution failed",
            extra={"tool": tool_name, "user_id": composio_user_id, "arguments": prepared_arguments},
        )
        raise RuntimeError(f"{tool_name} invocation failed: {exc}") from exc


class GmailClient:
    """Gmail client using Composio API."""

    def __init__(self):
        self.settings = get_settings()
        self.is_operational = self._check_operational()

    def _check_operational(self) -> bool:
        """Check if Gmail client is operational."""
        try:
            _get_composio_client()
            return True
        except Exception as e:
            logger.warning(f"Gmail client not operational: {e}")
            return False

    async def verify_gmail_connection(self, user_id: Optional[str] = None) -> bool:
        """Verify Gmail connection for user."""
        if not self.is_operational:
            return False

        try:
            # Resolve the actual Gmail user ID
            composio_user_id = resolve_gmail_user_id(user_id)
            if not composio_user_id:
                logger.warning(f"No Gmail user ID could be resolved for {user_id}")
                return False

            # Try to execute a simple Gmail operation
            result = execute_gmail_tool(
                "GMAIL_GET_PROFILE",
                composio_user_id,
                arguments={}
            )
            logger.info(f"Gmail connection verified for Composio user ID: {composio_user_id}")
            return bool(result)
        except Exception as e:
            logger.warning(f"Gmail connection verification failed for {user_id}: {e}")
            return False

    async def retrieve_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get Gmail user profile."""
        if not self.is_operational:
            return None

        try:
            # Resolve the actual Gmail user ID
            composio_user_id = resolve_gmail_user_id(user_id)
            if not composio_user_id:
                logger.warning(f"No Gmail user ID could be resolved for {user_id}")
                return None

            result = execute_gmail_tool(
                "GMAIL_GET_PROFILE",
                composio_user_id,
                arguments={}
            )
            return result
        except Exception as e:
            logger.error(f"Failed to get Gmail profile for {user_id}: {e}")
            return None

    async def search_emails(self, query: str, max_results: int = 10, user_id: str = "web_user") -> List[Dict[str, Any]]:
        """Search for emails."""
        if not self.is_operational:
            return []

        try:
            # Resolve the actual Gmail user ID
            composio_user_id = resolve_gmail_user_id(user_id)
            if not composio_user_id:
                logger.warning(f"No Gmail user ID could be resolved for {user_id}")
                return []

            result = execute_gmail_tool(
                "GMAIL_FETCH_EMAILS",
                composio_user_id,
                arguments={
                    "query": query,
                    "max_results": max_results,
                    "include_payload": True,
                    "verbose": True
                }
            )

            # Extract messages from result
            if isinstance(result, dict):
                if "data" in result and isinstance(result["data"], dict):
                    messages = result["data"].get("messages", [])
                elif "messages" in result:
                    messages = result["messages"]
                else:
                    messages = []
            elif isinstance(result, list):
                messages = result
            else:
                messages = []

            return messages

        except Exception as e:
            logger.error(f"Failed to search emails for {user_id}: {e}")
            return []

    async def get_recent_unread_emails(self, since_hours: int = 24, user_id: str = "web_user") -> List[Dict[str, Any]]:
        """Get recent unread emails."""
        if not self.is_operational:
            return []

        try:
            # Resolve the actual Gmail user ID
            composio_user_id = resolve_gmail_user_id(user_id)
            if not composio_user_id:
                logger.warning(f"No Gmail user ID could be resolved for {user_id}")
                return []

            # Build query for recent unread emails
            query = f"is:unread newer_than:{since_hours}h"

            result = execute_gmail_tool(
                "GMAIL_FETCH_EMAILS",
                composio_user_id,
                arguments={
                    "query": query,
                    "max_results": 20,
                    "include_payload": True,
                    "verbose": True
                }
            )

            # Extract messages from result
            if isinstance(result, dict):
                if "data" in result and isinstance(result["data"], dict):
                    messages = result["data"].get("messages", [])
                elif "messages" in result:
                    messages = result["messages"]
                else:
                    messages = []
            elif isinstance(result, list):
                messages = result
            else:
                messages = []

            return messages

        except Exception as e:
            logger.error(f"Failed to get recent unread emails for {user_id}: {e}")
            return []

    async def send_email(self, to: str, subject: str, body: str, user_id: str = "web_user", cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None, is_html: bool = False) -> Dict[str, Any]:
        """Send an email via Gmail."""
        if not self.is_operational:
            raise RuntimeError("Gmail service is not operational")

        try:
            # Resolve the actual Gmail user ID
            composio_user_id = resolve_gmail_user_id(user_id)
            if not composio_user_id:
                raise RuntimeError(f"No Gmail user ID could be resolved for {user_id}")

            # Prepare arguments for GMAIL_SEND_EMAIL
            arguments = {
                "recipient_email": to,
                "subject": subject,
                "body": body,
                "is_html": is_html
            }

            # Add optional parameters if provided
            if cc:
                arguments["cc"] = cc
            if bcc:
                arguments["bcc"] = bcc

            result = execute_gmail_tool(
                "GMAIL_SEND_EMAIL",
                composio_user_id,
                arguments=arguments
            )

            logger.info(f"Email sent successfully to {to}")
            return result

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            raise RuntimeError(f"Gmail send failed: {str(e)}")

    async def get_email_by_id(self, message_id: str, user_id: str = "web_user") -> Optional[Dict[str, Any]]:
        """Get a specific email by its message ID."""
        if not self.is_operational:
            return None

        try:
            # Resolve the actual Gmail user ID
            composio_user_id = resolve_gmail_user_id(user_id)
            if not composio_user_id:
                logger.warning(f"No Gmail user ID could be resolved for {user_id}")
                return None

            result = execute_gmail_tool(
                "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
                composio_user_id,
                arguments={
                    "message_id": message_id,
                    "format": "full"
                }
            )

            # Extract message data
            if isinstance(result, dict):
                if "data" in result:
                    return result["data"]
                else:
                    return result
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to get email {message_id} for {user_id}: {e}")
            return None

    async def initiate_gmail_auth(self, user_id: str) -> Optional[str]:
        """Initiate Gmail authentication and return auth URL."""
        if not self.is_operational:
            return None

        try:
            client = _get_composio_client()
            # This would typically involve Composio's auth flow
            # Implementation depends on your Composio setup
            logger.info(f"Initiating Gmail auth for user {user_id}")
            return f"https://composio.dev/auth/gmail?user_id={user_id}"
        except Exception as e:
            logger.error(f"Failed to initiate Gmail auth for {user_id}: {e}")
            return None

    async def disconnect_gmail_account(self, user_id: str) -> bool:
        """Disconnect Gmail account."""
        try:
            logger.info(f"Disconnecting Gmail for user {user_id}")
            # Implementation would depend on Composio's disconnect method
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect Gmail for {user_id}: {e}")
            return False