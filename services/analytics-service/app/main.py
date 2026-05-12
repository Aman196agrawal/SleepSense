from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import sessions, analytics, insights, lifestyle

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SleepSense — Analytics Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router,   prefix="/sessions",  tags=["Sessions"])
app.include_router(analytics.router,  prefix="/analytics", tags=["Analytics"])
app.include_router(insights.router,   prefix="/insights",  tags=["Insights"])
app.include_router(lifestyle.router,  prefix="/lifestyle", tags=["Lifestyle"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service"}
