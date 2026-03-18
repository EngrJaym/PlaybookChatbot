# Playbook Chatbot

A **button-based chatbot** for navigating a company playbook. Built with **React** (Vite) on the frontend and **FastAPI** on the backend.

Users interact entirely through predefined quick-reply buttons — no free-text input. The chatbot walks them through company policies, procedures, guidelines, and FAQs.

---

## Project Structure

```
PlaybookChatbot/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── requirements.txt        # Python dependencies
│   ├── routes/
│   │   └── chat.py             # POST /api/chat endpoint
│   └── logic/
│       └── flow.py             # Decision-tree playbook content
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
uvicorn main:app --reload --port 8000
```

API will be running at `http://localhost:8000`. Health check: `GET /`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App will be running at `http://localhost:5173`.

---

## How It Works

1. User clicks the **floating chat button** (bottom-right corner).
2. A welcome screen appears → user clicks **"Start Chatting"**.
3. The frontend sends `POST /api/chat` with `{ "node_id": "root" }`.
4. The backend looks up the node in the decision tree and returns a message + buttons.
5. User clicks a button → frontend sends the next `node_id` → cycle repeats.
6. **"Restart"** button in the header resets the conversation.

---

## Customising Playbook Content

Edit `backend/logic/flow.py` — the `FLOW` dictionary. Each node follows this format:

```python
"node_id": {
    "message": "Bot message text",
    "buttons": [
        {"label": "Button Label", "next": "target_node_id"},
    ],
    "is_end": False,  # True for terminal/leaf nodes
}
```

No frontend changes are needed when adding or editing playbook content.
