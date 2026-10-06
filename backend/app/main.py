from fastapi import FastAPI

app = FastAPI(title="GeoGuessr Clone")


@app.get("/health")
def health():
    return {"status": "ok"}
