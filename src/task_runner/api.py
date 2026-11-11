from fastapi import FastAPI

app = FastAPI(title="Task Runner")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}