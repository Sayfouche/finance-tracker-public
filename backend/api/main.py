from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.database import init_db
from db.seed import run_seed
from db.database import SessionLocal
from api.routes import accounts, transactions, categories, members, patrimony
from api.routes import agents
from api.routes import category_groups
from api.routes import simulator

app = FastAPI(title="Finance Tracker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3100",
        "http://localhost:3101",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3100",
        "http://127.0.0.1:3101",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()


app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(categories.router)
app.include_router(category_groups.router)
app.include_router(members.router)
app.include_router(patrimony.router)
app.include_router(agents.router)
app.include_router(simulator.router)


@app.get("/health")
def health():
    return {"status": "ok"}
