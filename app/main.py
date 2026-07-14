from fastapi import FastAPI

app = FastAPI(title="moto-hunter")


@app.get("/health")
def health():
    return {"status": "ok"}
