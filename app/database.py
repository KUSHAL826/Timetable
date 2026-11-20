import os
from supabase import create_client, Client
from app.config import settings

_supabase_client: Client | None = None
_supabase_admin_client: Client | None = None

def get_supabase() -> Client:
    """Returns standard client with anon key or service role key if anon missing."""
    global _supabase_client
    if _supabase_client is None:
        key = settings.SUPABASE_ANON_KEY or settings.SUPABASE_SERVICE_ROLE_KEY
        if not settings.SUPABASE_URL or not key or "YOUR_SUPABASE" in settings.SUPABASE_URL:
            # Fallback mock/local client handling if Supabase URL is not yet connected
            pass
        _supabase_client = create_client(settings.SUPABASE_URL, key)
    return _supabase_client

def get_supabase_admin() -> Client:
    """Returns elevated admin client with service role key for administrative & auth ops."""
    global _supabase_admin_client
    if _supabase_admin_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY or "YOUR_SUPABASE" in settings.SUPABASE_URL:
            pass
        _supabase_admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_admin_client
