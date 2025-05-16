from fastapi import FastAPI
from quote_generator import generate_and_save_quote_image

app = FastAPI()

@app.get("/")
def home():
    return {"status": "running", "message": "Quote generator service active."}

@app.get("/run")
def run():
    try:
        generate_and_save_quote_image()
        return {"status": "success", "message": "Quote uploaded"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
