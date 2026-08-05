from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.agent import run

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/generate-blog")
def generate_blog_endpoint():
    result = run()
    return result


@app.get("/health")
def health():
    return {"status": "ok"}