import os
import sys
import io
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Force standard output to UTF-8 to handle Thai characters on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Load environment variables
load_dotenv()

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

from google import genai
from google.genai import types

# Load Credentials
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("[Warning] LINE credentials are missing in .env file.")
if not GEMINI_API_KEY:
    print("[Warning] GEMINI_API_KEY is missing in .env file.")

# Initialize Line Configuration
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Initialize Gemini Client
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("[System] Gemini Client initialized successfully.")
    except Exception as e:
        print(f"[Error] Failed to initialize Gemini Client: {e}")

# Initialize FastAPI App
app = FastAPI(title="Line OA Gemini AI Chatbot")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def ask_gemini(user_query: str) -> str:
    """Sends the user's message to Gemini API with custom instructions."""
    if not gemini_client:
        return "ขออภัยครับ ระบบประมวลผล AI ขัดข้องชั่วคราว (กรุณาตั้งค่า API Key)"
    
    system_instruction = (
        "คุณคือแชทบอทอัจฉริยะภาษาไทย (Line OA Assistant) คอยตอบคำถามลูกค้าอย่างสุภาพ อ่อนน้อม ไพเราะ "
        "และเป็นกันเอง ลงท้ายด้วย 'ครับ/นะครับ' เสมอเพื่อความสุภาพ (เพราะคุณเป็นตัวแทนช่วยเหลือของคุณ Wish) "
        "ทำหน้าที่เหมือนเลขาส่วนตัวหรือแอดมินร้านค้า คอยช่วยเหลือลูกค้าในทุกปัญหาอย่างจริงใจและสร้างสรรค์"
    )
    
    try:
        print(f"[*] Calling Gemini for query: '{user_query}'")
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )
        )
        return response.text or "ขออภัยครับ ผมไม่สามารถประมวลผลข้อความนี้ได้"
    except Exception as e:
        print(f"[Error] Gemini API call failed: {e}")
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
        
    body = await request.body()
    body_str = body.decode("utf-8")
    
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        print("[Error] Invalid signature from LINE Webhook.")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"[Error] Exception in handler: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """Handles incoming text messages from LINE and replies using Gemini API."""
    user_message = event.message.text
    print(f"[Line Webhook] Received message: '{user_message}' from user: {event.source.user_id}")
    
    # Get response from AI
    reply_text = ask_gemini(user_message)
    print(f"[Line Webhook] Replying with: '{reply_text}'")
    
    # Send reply to Line
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
    except Exception as e:
        print(f"[Error] Failed to send Line reply: {e}")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    print(f"Starting Chatbot FastAPI Server on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True, loop="asyncio")
