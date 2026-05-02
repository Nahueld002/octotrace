"""Main FastAPI application for Octotrace web interface.

This module initializes the FastAPI application with all required routes,
static file serving, and API endpoints for the forensic tracing tool.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.web.routes import query, expand, save

app = FastAPI(
    title="Octotrace API",
    description="Forensic USDT traceability tool",
    version="0.1.0"
)

# Include all route modules
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(expand.router, prefix="/api", tags=["expand"])
app.include_router(save.router, prefix="/api", tags=["save"])

# Mount static files
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

@app.get("/")
async def read_root():
    """Serve the main index.html file."""
    return FileResponse("src/web/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)