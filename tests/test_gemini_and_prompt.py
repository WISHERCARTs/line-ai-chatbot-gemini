import os
from types import SimpleNamespace

import main
from prompt_loader import FALLBACK_PROMPT, PromptLoader


class FakeGeminiClient:
    """Records the arguments passed to generate_content."""

    def __init__(self, text="คำตอบจาก AI", error=None):
        self.calls = []
        self._text = text
        self._error = error
        self.models = SimpleNamespace(generate_content=self._generate_content)

    def _generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(text=self._text)


def write_prompt(path, text, mtime):
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))


# ---- ask_gemini ----------------------------------------------------------

def test_ask_gemini_returns_model_text(monkeypatch):
    fake = FakeGeminiClient(text="สวัสดีครับ")
    monkeypatch.setattr(main, "gemini_client", fake)

    assert main.ask_gemini("hi") == "สวัสดีครับ"
    assert fake.calls[0]["model"] == main.GEMINI_MODEL
    assert fake.calls[0]["contents"] == "hi"


def test_ask_gemini_without_client_explains_missing_key(monkeypatch):
    monkeypatch.setattr(main, "gemini_client", None)
    assert "API Key" in main.ask_gemini("hi")


def test_ask_gemini_falls_back_when_api_raises(monkeypatch):
    monkeypatch.setattr(main, "gemini_client", FakeGeminiClient(error=RuntimeError("quota")))
    assert "ข้อผิดพลาด" in main.ask_gemini("hi")


def test_ask_gemini_falls_back_on_empty_response(monkeypatch):
    monkeypatch.setattr(main, "gemini_client", FakeGeminiClient(text=""))
    assert "ไม่สามารถประมวลผล" in main.ask_gemini("hi")


# ---- prompt hot reload ---------------------------------------------------

def test_prompt_edit_is_used_without_restart(monkeypatch, tmp_path):
    prompt_file = tmp_path / "system_prompt.md"
    write_prompt(prompt_file, "prompt v1", mtime=1_000_000)
    monkeypatch.setattr(main, "prompts", PromptLoader(prompt_file))
    fake = FakeGeminiClient()
    monkeypatch.setattr(main, "gemini_client", fake)

    main.ask_gemini("hi")
    write_prompt(prompt_file, "prompt v2", mtime=2_000_000)
    main.ask_gemini("hi")

    used = [call["config"].system_instruction for call in fake.calls]
    assert used == ["prompt v1", "prompt v2"]


def test_prompt_loader_reads_file_once_until_it_changes(tmp_path):
    prompt_file = tmp_path / "p.md"
    write_prompt(prompt_file, "first", mtime=1_000_000)
    loader = PromptLoader(prompt_file)
    assert loader.get() == "first"

    # Same mtime, different content: the cached text must be returned
    prompt_file.write_text("second", encoding="utf-8")
    os.utime(prompt_file, (1_000_000, 1_000_000))
    assert loader.get() == "first"


def test_prompt_loader_uses_fallback_when_file_is_missing(tmp_path):
    loader = PromptLoader(tmp_path / "missing.md")
    assert loader.get() == FALLBACK_PROMPT


def test_prompt_loader_keeps_last_good_prompt_on_empty_edit(tmp_path):
    prompt_file = tmp_path / "p.md"
    write_prompt(prompt_file, "good prompt", mtime=1_000_000)
    loader = PromptLoader(prompt_file)
    assert loader.get() == "good prompt"

    write_prompt(prompt_file, "   \n", mtime=2_000_000)
    assert loader.get() == "good prompt"


def test_prompt_loader_keeps_last_good_prompt_when_file_disappears(tmp_path):
    prompt_file = tmp_path / "p.md"
    write_prompt(prompt_file, "good prompt", mtime=1_000_000)
    loader = PromptLoader(prompt_file)
    assert loader.get() == "good prompt"

    prompt_file.unlink()
    assert loader.get() == "good prompt"


def test_shipped_prompt_file_loads():
    loader = PromptLoader()
    prompt = loader.get()
    assert prompt != FALLBACK_PROMPT
    assert "ครับ" in prompt
