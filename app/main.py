import os
import time
import random
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Prometheus Metrics Definition
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "status_code"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency in seconds",
    ["endpoint"]
)
INCIDENT_COUNT = Counter(
    "platform_incidents_total",
    "Total simulated or logged platform incidents",
    ["severity", "component"]
)

# App Initialization
app = FastAPI(
    title="DevOps Pulse Operations Platform",
    description="Miniature production-grade DevOps Operations Engine",
    version="1.0.0"
)

# Setup path for templates & static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir)


# Middleware for request telemetry
@app.middleware("http")
async def prometheus_telemetry_middleware(request: Request, call_next):
    start_time = time.time()
    endpoint = request.url.path

    # Process request
    response = await call_next(request)

    # Record telemetry
    process_time = time.time() - start_time
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(process_time)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code
    ).inc()

    return response


# In-Memory Incident Store (for demo purposes)
incidents_db = [
    {
        "id": "INC-001",
        "title": "Database Read Latency Spike",
        "severity": "medium",
        "component": "rds-postgres",
        "status": "resolved",
        "timestamp": "2026-09-13 07:45:00 UTC"
    }
]


class IncidentPayload(BaseModel):
    title: str
    severity: str  # low, medium, high, critical
    component: str
    description: Optional[str] = "Manual incident created during live demo"


class ChaosPayload(BaseModel):
    duration_seconds: float = 2.0
    error_rate: float = 0.5  # 50% failure rate simulation


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Renders the live DevOps Pulse Operations Dashboard UI
    """
    env_name = os.getenv("ENVIRONMENT", "dev").upper()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "environment": env_name,
            "incidents": incidents_db,
            "app_version": os.getenv("APP_VERSION", "1.0.0-git-sha")
        }
    )


@app.get("/health")
async def health_check():
    """
    ALB Health check endpoint
    """
    return {
        "status": "healthy",
        "service": "devops-pulse-monolith",
        "environment": os.getenv("ENVIRONMENT", "dev"),
        "version": os.getenv("APP_VERSION", "1.0.0")
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus Scrape Endpoint
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/status")
async def get_status():
    """
    System status summary
    """
    return {
        "status": "OPERATIONAL",
        "uptime": "99.99%",
        "services": {
            "api_gateway": "healthy",
            "database": "healthy",
            "cache": "healthy",
            "worker_queue": "healthy"
        },
        "environment": os.getenv("ENVIRONMENT", "dev")
    }


@app.get("/api/v1/incidents")
async def list_incidents():
    """
    List all recorded incidents
    """
    return {"incidents": incidents_db}


@app.post("/api/v1/incidents", status_code=status.HTTP_201_CREATED)
async def create_incident(payload: IncidentPayload):
    """
    TASK-101 Feature: Add Incident Reporting API Endpoint
    Creates an incident entry and pushes metrics to Prometheus.
    """
    new_inc = {
        "id": f"INC-00{len(incidents_db) + 1}",
        "title": payload.title,
        "severity": payload.severity,
        "component": payload.component,
        "status": "active",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    }
    incidents_db.insert(0, new_inc)
    INCIDENT_COUNT.labels(severity=payload.severity, component=payload.component).inc()
    return {"message": "Incident logged successfully", "incident": new_inc}


@app.post("/api/v1/chaos/trigger")
async def trigger_chaos(payload: ChaosPayload):
    """
    TASK-101 Feature: Chaos Simulation Engine
    Simulates latency or artificial HTTP 500 server errors for live demo metric visualization.
    """
    # Simulate high latency
    time.sleep(min(payload.duration_seconds, 5.0))

    if random.random() < payload.error_rate:
        INCIDENT_COUNT.labels(severity="high", component="chaos-engine").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chaos Simulation: Artificial Service Degradation Injected!"
        )

    return {
        "status": "SIMULATION_COMPLETED",
        "latency_injected_seconds": payload.duration_seconds,
        "result": "System survived chaos injection!"
    }
