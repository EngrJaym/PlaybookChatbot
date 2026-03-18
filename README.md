# Playbook Chatbot

A **button-based chatbot** for navigating the **NDS Client Management Playbook**. Built with **React** (Vite) on the frontend and **FastAPI** on the backend.

Users interact entirely through predefined quick-reply buttons — no free-text input. The chatbot walks them through account setup, mapping, estimation, pricing, PSU, study types, QC checklists, and office regions.

---

## Project Structure

```
PlaybookChatbot/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── requirements.txt        # Python dependencies
│   ├── test_flow.py            # Smoke test for flow engine
│   ├── routes/
│   │   └── chat.py             # POST /api/chat endpoint
│   └── logic/
│       └── flow.py             # Loads decision tree from data/cm.json
├── data/
│   └── cm.json                 # Playbook content (nodes & buttons)
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Root component
│   │   ├── components/
│   │   │   ├── ChatButton.jsx  # Floating action button
│   │   │   ├── ChatWindow.jsx  # Chat panel container
│   │   │   ├── MessageList.jsx # Scrollable message history
│   │   │   └── OptionButtons.jsx # Quick-reply buttons
│   │   └── hooks/
│   │       └── useChat.js      # Chat state & API logic
│   └── ...
└── README.md
```

---

## Getting Started

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & npm

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

API will be running at `http://localhost:8001`. Health check: `GET /`.  
API docs: `http://localhost:8001/docs`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App will be running at `http://localhost:5173`.

---

## How It Works

1. User clicks the **💬 floating chat button** (bottom-right corner).
2. A welcome screen appears → user clicks **"Open Playbook"**.
3. The frontend sends `POST /api/chat` with `{ "node_id": "home" }`.
4. The backend loads the node from `data/cm.json` and returns a message + answer + buttons.
5. User clicks a button → frontend sends the next `node_id` → cycle repeats.
6. **"Start Over"** button in the header resets the conversation.

---

## Customising Playbook Content

Edit `data/cm.json`. Each node follows this format:

```json
{
  "id": "node-id",
  "message": "Heading shown to user",
  "answer": "Detailed content (optional)",
  "buttons": [
    { "label": "Button Label", "next": "target_node_id" }
  ]
}
```

No frontend or backend code changes are needed when adding or editing playbook content.
