import base64
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import main

SECRET = "test-channel-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def text_event_body(text: str = "สวัสดี", reply_token: str = "reply-token") -> bytes:
    payload = {
        "destination": "U0000000000000000000000000000000",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": 1700000000000,
                "source": {"type": "user", "userId": "U1111111111111111111111111111111"},
                "webhookEventId": "01TESTEVENT",
                "deliveryContext": {"isRedelivery": False},
                "replyToken": reply_token,
                "message": {"type": "text", "id": "1", "text": text, "quoteToken": "quote"},
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def sticker_event_body() -> bytes:
    payload = {
        "destination": "U0000000000000000000000000000000",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": 1700000000000,
                "source": {"type": "user", "userId": "U1111111111111111111111111111111"},
                "webhookEventId": "01TESTSTICKER",
                "deliveryContext": {"isRedelivery": False},
                "replyToken": "reply-token",
                "message": {
                    "type": "sticker",
                    "id": "2",
                    "quoteToken": "quote",
                    "packageId": "1",
                    "stickerId": "1",
                    "stickerResourceType": "STATIC",
                },
            }
        ],
    }
    return json.dumps(payload).encode("utf-8")


class FakeApiClient:
    def __init__(self, configuration):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeMessagingApi:
    sent = []

    def __init__(self, api_client):
        pass

    def reply_message_with_http_info(self, request):
        FakeMessagingApi.sent.append(request)


@pytest.fixture
def client(monkeypatch):
    FakeMessagingApi.sent = []
    monkeypatch.setattr(main, "ApiClient", FakeApiClient)
    monkeypatch.setattr(main, "MessagingApi", FakeMessagingApi)
    monkeypatch.setattr(main, "ask_gemini", lambda text: f"echo: {text}")
    return TestClient(main.app)


def post(client, body: bytes, signature):
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Line-Signature"] = signature
    return client.post("/callback", content=body, headers=headers)


def test_root_reports_running(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_missing_signature_is_rejected(client):
    response = post(client, text_event_body(), None)
    assert response.status_code == 400
    assert FakeMessagingApi.sent == []


def test_invalid_signature_is_rejected(client):
    response = post(client, text_event_body(), sign(text_event_body(), secret="wrong-secret"))
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid signature"
    assert FakeMessagingApi.sent == []


def test_tampered_body_is_rejected(client):
    signature = sign(text_event_body("original"))
    response = post(client, text_event_body("tampered"), signature)
    assert response.status_code == 400
    assert FakeMessagingApi.sent == []


def test_valid_text_message_gets_a_reply(client):
    body = text_event_body("สวัสดี", reply_token="abc123")
    response = post(client, body, sign(body))

    assert response.status_code == 200
    assert len(FakeMessagingApi.sent) == 1
    reply = FakeMessagingApi.sent[0]
    assert reply.reply_token == "abc123"
    assert reply.messages[0].text == "echo: สวัสดี"


def test_non_text_message_is_ignored(client):
    body = sticker_event_body()
    response = post(client, body, sign(body))

    assert response.status_code == 200
    assert FakeMessagingApi.sent == []


def test_line_reply_failure_does_not_fail_the_webhook(client, monkeypatch):
    class BrokenMessagingApi(FakeMessagingApi):
        def reply_message_with_http_info(self, request):
            raise RuntimeError("LINE is down")

    monkeypatch.setattr(main, "MessagingApi", BrokenMessagingApi)
    body = text_event_body()
    response = post(client, body, sign(body))

    # LINE should not keep redelivering because our reply call failed
    assert response.status_code == 200
