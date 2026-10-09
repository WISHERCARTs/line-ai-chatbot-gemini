"""Loads the system prompt from a file and picks up edits without a restart."""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"
FALLBACK_PROMPT = "คุณคือแชทบอทภาษาไทยที่ตอบคำถามลูกค้าอย่างสุภาพ ลงท้ายด้วย 'ครับ'"


class PromptLoader:
    """Re-reads the prompt file whenever its modification time changes.

    If the file is missing, unreadable or empty, the last good prompt is kept,
    so a bad edit never takes the bot down.
    """

    def __init__(self, path=None, fallback: str = FALLBACK_PROMPT):
        self.path = Path(path or os.getenv("SYSTEM_PROMPT_PATH") or DEFAULT_PROMPT_PATH)
        self._text = fallback
        self._mtime_ns = None

    def get(self) -> str:
        try:
            mtime_ns = self.path.stat().st_mtime_ns
            if mtime_ns != self._mtime_ns:
                text = self.path.read_text(encoding="utf-8").strip()
                if text:
                    self._text = text
                    logger.info("Loaded system prompt from %s", self.path)
                else:
                    logger.warning("System prompt file %s is empty; keeping previous prompt", self.path)
                self._mtime_ns = mtime_ns
        except OSError as exc:
            logger.warning("Cannot read system prompt %s (%s); keeping previous prompt", self.path, exc)
        return self._text
