"""Gmail Tool Functions - Pure functions using Composio integration."""

from typing import Any, Dict, List, Optional

from ..logging_config import get_logger
from ..services.gmail.client import GmailClient, resolve_gmail_user_id

logger = get_logger(__name__)


async def _resolve_web_user_to_session(user_id: str) -> str:
    """Resolve web_user to actual session ID using the same logic as scheduler."""

    if user_id != "web_user":
        return user_id

    try:
        from ..services.gmail.client import get_active_gmail_user_id
        from ..services.supabase_client import get_supabase_client

        # First try Gmail cache
        gmail_user_id = get_active_gmail_user_id()
        if gmail_user_id and gmail_user_id.startswith("web-"):
            logger.info(f"📧 Using cached Gmail session: {gmail_user_id}")
            return gmail_user_id

        # Fall back to recent conversation lookup
        supabase = get_supabase_client()
        if supabase:
            result = (
                supabase
                .table('conversations')
                .select('phone_number')
                .neq('phone_number', 'web_user')
                .like('phone_number', 'web-%')
                .order('timestamp', desc=True)
                .limit(1)
                .execute()
            )

            if result.data and len(result.data) > 0:
                session_id = result.data[0]['phone_number']
                logger.info(f"📧 Mapped web_user to recent session: {session_id}")
                return session_id

        logger.warning("📧 No active session found for web_user")
        return user_id

    except Exception as e:
        logger.warning(f"📧 Failed to resolve web_user session: {e}")
        return user_id


async def fetch_emails(user_id: str, query: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
    """Fetch emails from Gmail using Composio integration."""

    try:
        client = GmailClient()

        if not client.is_operational:
            raise RuntimeError("Gmail service is not operational")

        # Resolve web_user to actual session ID
        actual_user_id = await _resolve_web_user_to_session(user_id)

        # Resolve the actual Gmail user ID
        resolved_user_id = resolve_gmail_user_id(actual_user_id)
        if not resolved_user_id:
            raise RuntimeError(f"No connected account found for user {user_id} (resolved to {actual_user_id})")

        # Verify connection first
        if not await client.verify_gmail_connection(resolved_user_id):
            raise RuntimeError(f"Gmail not connected for user {resolved_user_id}")

        # Fetch emails using the search function
        emails = await client.search_emails(query or "in:inbox", max_results, resolved_user_id)

        logger.info(f"Fetched {len(emails)} emails for user {resolved_user_id} with query: {query}")
        return emails

    except Exception as e:
        logger.error(f"Failed to fetch emails for user {user_id}: {e}")
        raise RuntimeError(f"Gmail fetch failed: {str(e)}")


async def search_emails(user_id: str, query: str) -> List[Dict[str, Any]]:
    """Search emails in Gmail."""

    try:
        client = GmailClient()

        if not client.is_operational:
            raise RuntimeError("Gmail service is not operational")

        # For web_user, try to resolve to actual Gmail session first
        actual_user_id = user_id
        if user_id == "web_user":
            # Try to get active Gmail user ID
            from ..services.gmail.client import get_active_gmail_user_id
            gmail_user_id = get_active_gmail_user_id()
            if gmail_user_id:
                actual_user_id = gmail_user_id
                logger.info(f"📧 Mapped web_user to Gmail session: {gmail_user_id}")

        # Resolve the actual Gmail user ID
        resolved_user_id = resolve_gmail_user_id(actual_user_id)
        if not resolved_user_id:
            raise RuntimeError(f"No connected account found for user {user_id}")

        # Verify connection
        if not await client.verify_gmail_connection(resolved_user_id):
            raise RuntimeError(f"Gmail not connected for user {resolved_user_id}")

        # Search emails
        results = await client.search_emails(query, 20, resolved_user_id)  # Default to 20 results

        logger.info(f"Found {len(results)} emails for search query: {query}")
        return results

    except Exception as e:
        logger.error(f"Failed to search emails: {e}")
        raise RuntimeError(f"Gmail search failed: {str(e)}")


async def send_email(user_id: str, to: str, subject: str, body: str, cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None, is_html: bool = False) -> Dict[str, Any]:
    """Send an email via Gmail."""

    try:
        client = GmailClient()

        if not client.is_operational:
            raise RuntimeError("Gmail service is not operational")

        # Resolve web_user to actual session ID
        actual_user_id = await _resolve_web_user_to_session(user_id)

        # Resolve the actual Gmail user ID
        resolved_user_id = resolve_gmail_user_id(actual_user_id)
        if not resolved_user_id:
            raise RuntimeError(f"No connected account found for user {user_id} (resolved to {actual_user_id})")

        # Verify connection
        if not await client.verify_gmail_connection(resolved_user_id):
            raise RuntimeError(f"Gmail not connected for user {resolved_user_id}")

        # Send email using the client
        result = await client.send_email(
            to=to,
            subject=subject,
            body=body,
            user_id=resolved_user_id,
            cc=cc,
            bcc=bcc,
            is_html=is_html
        )

        logger.info(f"Email sent successfully to {to}")
        return result

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise RuntimeError(f"Gmail send failed: {str(e)}")


async def get_profile(user_id: str) -> Dict[str, Any]:
    """Get Gmail profile information."""

    try:
        client = GmailClient()

        if not client.is_operational:
            raise RuntimeError("Gmail service is not operational")

        # Resolve web_user to actual session ID
        actual_user_id = await _resolve_web_user_to_session(user_id)

        # Resolve the actual Gmail user ID
        resolved_user_id = resolve_gmail_user_id(actual_user_id)
        if not resolved_user_id:
            raise RuntimeError(f"No connected account found for user {user_id} (resolved to {actual_user_id})")

        # Verify connection
        if not await client.verify_gmail_connection(resolved_user_id):
            raise RuntimeError(f"Gmail not connected for user {resolved_user_id}")

        # Get profile
        profile = await client.retrieve_user_profile(resolved_user_id)

        if not profile:
            raise RuntimeError("Could not retrieve Gmail profile")

        logger.info(f"Retrieved Gmail profile for user {user_id}")
        return profile

    except Exception as e:
        logger.error(f"Failed to get Gmail profile: {e}")
        raise RuntimeError(f"Gmail profile retrieval failed: {str(e)}")


async def check_recent_emails(user_id: str, since_hours: int = 24) -> List[Dict[str, Any]]:
    """Check for recent unread emails."""

    try:
        client = GmailClient()

        if not client.is_operational:
            raise RuntimeError("Gmail service is not operational")

        # Resolve web_user to actual session ID
        actual_user_id = await _resolve_web_user_to_session(user_id)

        # Resolve the actual Gmail user ID
        resolved_user_id = resolve_gmail_user_id(actual_user_id)
        if not resolved_user_id:
            raise RuntimeError(f"No connected account found for user {user_id} (resolved to {actual_user_id})")

        # Verify connection
        if not await client.verify_gmail_connection(resolved_user_id):
            raise RuntimeError(f"Gmail not connected for user {resolved_user_id}")

        # Get recent unread emails
        emails = await client.get_recent_unread_emails(since_hours, resolved_user_id)

        logger.info(f"Found {len(emails)} recent unread emails for user {user_id}")
        return emails

    except Exception as e:
        logger.error(f"Failed to check recent emails: {e}")
        raise RuntimeError(f"Gmail recent check failed: {str(e)}")


async def get_email_content(user_id: str, email_id: str) -> Dict[str, Any]:
    """Get full content of a specific email."""

    try:
        client = GmailClient()

        if not client.is_operational:
            raise RuntimeError("Gmail service is not operational")

        # Resolve web_user to actual session ID
        actual_user_id = await _resolve_web_user_to_session(user_id)

        # Resolve the actual Gmail user ID
        resolved_user_id = resolve_gmail_user_id(actual_user_id)
        if not resolved_user_id:
            raise RuntimeError(f"No connected account found for user {user_id} (resolved to {actual_user_id})")

        # Verify connection
        if not await client.verify_gmail_connection(resolved_user_id):
            raise RuntimeError(f"Gmail not connected for user {resolved_user_id}")

        # Get email content using the client
        email_data = await client.get_email_by_id(email_id, resolved_user_id)

        if not email_data:
            raise RuntimeError(f"Could not retrieve email with ID {email_id}")

        logger.info(f"Retrieved email content for ID {email_id}")
        return email_data

    except Exception as e:
        logger.error(f"Failed to get email content: {e}")
        raise RuntimeError(f"Gmail content retrieval failed: {str(e)}")


# Tool function registry for discovery
GMAIL_TOOLS = {
    "fetch_emails": fetch_emails,
    "search_emails": search_emails,
    "send_email": send_email,
    "get_profile": get_profile,
    "check_recent_emails": check_recent_emails,
    "get_email_content": get_email_content,
}