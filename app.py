from fastapi import FastAPI
from routes import router

app = FastAPI(title="NutriX")

# Incluir rotas
app.include_router(router)
