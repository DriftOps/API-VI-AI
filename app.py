from fastapi import FastAPI
from routes import router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NutriX")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # em produção, troque pelo domínio real
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
