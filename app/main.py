from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.agent import run

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://robotics-blog-agent.vercel.app",
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Robotics Blog Agent API is running. Use POST /generate-blog"}


@app.post("/generate-blog")
def generate_blog_endpoint():
    result = run()
    return result


@app.get("/health")
def health():
    return {"status": "ok"}