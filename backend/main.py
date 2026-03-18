import logging
import config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.chat import router as chat_router

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NDS Client Management Playbook API",
    version="1.1.0",
    description=(
        "Button-based chatbot API for the NDS Client Management Playbook."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.on_event("startup")
async def _startup():
    logger.info("=" * 56)
    logger.info("  NDS Playbook Chatbot API — startup")
    logger.info("=" * 56)
    logger.info(f"  APP_ENV              : {config.APP_ENV}")
    logger.info(f"  DATA_SOURCE          : {config.DATA_SOURCE}")
    logger.info(f"  MAINTENANCE_MODE     : {config.MAINTENANCE_MODE}")
    logger.info(f"  ENABLE_CHAT          : {config.ENABLE_CHAT}")
    logger.info(f"  ENABLE_RELOAD        : {config.ENABLE_RELOAD}")
    logger.info(f"  ENABLE_DEBUG_ENDPOINTS: {config.ENABLE_DEBUG_ENDPOINTS}")
    logger.info(f"  ENABLE_META_ENDPOINT : {config.ENABLE_META_ENDPOINT}")
    logger.info(f"  SA credentials       : {'✓ found' if config.SA_FILE.exists() else '✗ MISSING'}")
    logger.info("=" * 56)


@app.get("/")
async def health():
    from logic.flow import get_source, get_all_node_ids
    return {
        "status":           "ok" if not config.MAINTENANCE_MODE else "maintenance",
        "service":          "NDS Playbook Chatbot API",
        "app_env":          config.APP_ENV,
        "data_source_mode": config.DATA_SOURCE,
        "playbook_source":  get_source(),
        "node_count":       len(get_all_node_ids()),
        "maintenance":      config.MAINTENANCE_MODE,
        "features": {
            "chat":             config.ENABLE_CHAT,
            "reload":           config.ENABLE_RELOAD,
            "debug_endpoints":  config.ENABLE_DEBUG_ENDPOINTS,
            "meta_endpoint":    config.ENABLE_META_ENDPOINT,
        },
    }
