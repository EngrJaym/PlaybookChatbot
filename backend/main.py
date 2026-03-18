from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.chat import router as chat_router

app = FastAPI(
    title="NDS Client Management Playbook API",
    version="1.1.0",
    description="Button-based chatbot API for the NDS Client Management Playbook",
)

# CORS – allow the React dev server and common local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/")
async def health():
    return {"status": "ok", "service": "NDS Playbook Chatbot API"}
