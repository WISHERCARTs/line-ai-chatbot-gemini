import logging
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

# Load environment variables
load_dotenv()

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from google import genai
from google.genai import types

from prompt_loader import PromptLoader

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("chatbot")

# Load Credentials
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    logger.warning("LINE credentials are missing in the environment.")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is missing in the environment.")

# Initialize Line Configuration
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Initialize Gemini Client
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini client initialized.")
    except Exception:
        logger.exception("Failed to initialize Gemini client")

# System prompt, re-read from prompts/system_prompt.md whenever the file changes
prompts = PromptLoader()

# Initialize FastAPI App
app = FastAPI(title="Line OA Gemini AI Chatbot")


def ask_gemini(user_query: str) -> str:
    """Sends the user's message to Gemini API with the current system prompt."""
    if not gemini_client:
        return "ขออภัยครับ ระบบประมวลผล AI ขัดข้องชั่วคราว (กรุณาตั้งค่า API Key)"

    try:
        logger.info("Calling Gemini (query length=%d)", len(user_query))
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction=prompts.get(),
                temperature=0.7,
            ),
        )
        return response.text or "ขออภัยครับ ผมไม่สามารถประมวลผลข้อความนี้ได้"
    except Exception:
        logger.exception("Gemini API call failed")
        return "ขออภัยครับ ระบบ AI เกิดข้อผิดพลาดชั่วคราว กรุณาลองใหม่อีกครั้ง"


@app.get("/")
def read_root():
    return {"status": "running", "message": "Line OA Gemini AI Chatbot is active!"}


@app.post("/callback")
async def callback(request: Request):
    """Callback route for LINE Webhook events."""
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    body = (await request.body()).decode("utf-8", errors="replace")

    try:
        # handler.handle is synchronous and calls Gemini, so keep it off the event loop
        await run_in_threadpool(handler.handle, body, signature)
    except InvalidSignatureError:
        logger.warning("Rejected webhook with an invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        logger.exception("Unhandled error while processing webhook")
        raise HTTPException(status_code=500, detail="Internal server error")

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """Handles incoming text messages from LINE and replies using Gemini API."""
    user_message = event.message.text
    logger.info("Received text message (length=%d)", len(user_message))

    reply_text = ask_gemini(user_message)

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)],
                )
            )
    except Exception:
        logger.exception("Failed to send LINE reply")


if __name__ == "__main__":
    import uvicorn

    # Thai text on the Windows console
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    reload = os.getenv("RELOAD", "").lower() in ("1", "true", "yes")
    logger.info("Starting Chatbot FastAPI Server on http://%s:%d", host, port)
    uvicorn.run("main:app", host=host, port=port, reload=reload, loop="asyncio")
