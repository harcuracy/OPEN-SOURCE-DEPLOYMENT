import logging
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from waitress import serve

from config import Config
from routes import api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GATEWAY] %(levelname)s: %(message)s"
)
logger = logging.getLogger("gateway")

app = Flask(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[Config.RATE_LIMIT],
    storage_uri="memory://"
)

app.register_blueprint(api)

if __name__ == "__main__":
    logger.info("Starting API Gateway microservice on port %d...", Config.PORT)
    logger.info("LLM downstream URL: %s", Config.LLM_SERVICE_URL)
    logger.info("TTS downstream URL: %s", Config.TTS_SERVICE_URL)
    logger.info("STT downstream URL: %s", Config.STT_SERVICE_URL)
    serve(app, host="0.0.0.0", port=Config.PORT)
