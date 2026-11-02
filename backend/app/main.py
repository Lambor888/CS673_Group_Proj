from fastapi import FastAPI

# Define each module's routes in app/modules/<module_name>/router.py.
# Import and register module routers here with app.include_router(...).
# Keep module endpoint handlers and business logic inside your own modules.
from app.modules.auth.router import router as auth_router
from app.modules.lobby.router import router as lobby_router
from app.modules.connections.router import router as connection_router
from app.modules.singlePlayer.router import router as singleplayer_router
from app.modules.profile.router import router as profile_router
from app.modules.rounds.router import router as rounds_router
from app.modules.multiplayer_loop.router import router as multiplayer_router
app = FastAPI(title="GeoGuessr Clone")

app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(lobby_router)
app.include_router(connection_router)
app.include_router(singleplayer_router)
app.include_router(profile_router)
app.include_router(rounds_router)
app.include_router(multiplayer_router)

