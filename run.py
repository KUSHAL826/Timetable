"""
SmartTimetable AI - Server Starter
Production-ready launcher compatible with Render, cloud PaaS, and local execution.
Dynamically reads PORT and HOST environment variables without printing hardcoded credentials.
"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    # Avoid reload in production environments like Render
    reload = os.environ.get("APP_ENV", "production").lower() == "development"

    print(f"Starting SmartTimetable AI Institutional OS on {host}:{port} (reload={reload})...")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
