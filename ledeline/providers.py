"""Model providers behind one call signature, so swapping models is a config change.

Only the Gemini adapter has been exercised in this repo's committed runs (free tier). The
Anthropic and OpenAI adapters follow their documented REST shapes but are unverified here and
say so in their docstrings rather than pretending otherwise.
"""
from __future__ import annotations
import json, os, time, urllib.request, urllib.error
from dataclasses import dataclass


@dataclass
class Completion:
    text: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderError(RuntimeError):
    pass


def _post(url: str, body: dict, headers: dict, timeout: int = 90) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(4 * (attempt + 1) + (10 if e.code == 429 else 0))
                continue
            raise ProviderError(f"HTTP {e.code}: {msg}")
    raise ProviderError("unreachable")


class GeminiProvider:
    """REST call to generativelanguage.googleapis.com. Auth is a ?key= query param."""
    name = "gemini"

    def __init__(self, model: str, api_key: str | None = None, thinking_budget: int | None = 0):
        self.model = model
        self.key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_KEY")
        if not self.key:
            raise ProviderError("GEMINI_API_KEY is not set")
        self.thinking_budget = thinking_budget

    def complete(self, system: str, user: str, json_mode: bool = True, temperature: float = 0.2) -> Completion:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.key}"
        gen: dict = {"temperature": temperature}
        if json_mode:
            gen["responseMimeType"] = "application/json"
        if self.thinking_budget is not None and "2.5" in self.model:
            gen["thinkingConfig"] = {"thinkingBudget": self.thinking_budget}
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": gen}
        t0 = time.time()
        r = _post(url, body, {})
        try:
            text = r["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise ProviderError(f"no text in response: {json.dumps(r)[:300]}")
        um = r.get("usageMetadata", {})
        return Completion(text, self.model, int((time.time() - t0) * 1000),
                          um.get("promptTokenCount"), um.get("candidatesTokenCount"))


class AnthropicProvider:
    """Messages API adapter. Shape follows the public docs; NOT exercised in this repo's runs."""
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")

    def complete(self, system: str, user: str, json_mode: bool = True, temperature: float = 0.2) -> Completion:
        if json_mode:
            system = system + "\n\nRespond with a single JSON object and nothing else."
        body = {"model": self.model, "max_tokens": 1024, "temperature": temperature, "system": system,
                "messages": [{"role": "user", "content": user}]}
        t0 = time.time()
        r = _post("https://api.anthropic.com/v1/messages", body,
                  {"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        text = "".join(b.get("text", "") for b in r.get("content", []))
        u = r.get("usage", {})
        return Completion(text, self.model, int((time.time() - t0) * 1000), u.get("input_tokens"), u.get("output_tokens"))


class OpenAIProvider:
    """Chat Completions adapter. Shape follows the public docs; NOT exercised in this repo's runs."""
    name = "openai"

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.key:
            raise ProviderError("OPENAI_API_KEY is not set")

    def complete(self, system: str, user: str, json_mode: bool = True, temperature: float = 0.2) -> Completion:
        body = {"model": self.model, "temperature": temperature,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        t0 = time.time()
        r = _post("https://api.openai.com/v1/chat/completions", body, {"Authorization": f"Bearer {self.key}"})
        text = r["choices"][0]["message"]["content"]
        u = r.get("usage", {})
        return Completion(text, self.model, int((time.time() - t0) * 1000), u.get("prompt_tokens"), u.get("completion_tokens"))


def make(spec: str):
    """'gemini:gemini-2.5-flash' -> provider instance. The string is the whole model config."""
    kind, _, model = spec.partition(":")
    if kind == "gemini":
        return GeminiProvider(model)
    if kind == "anthropic":
        return AnthropicProvider(model)
    if kind == "openai":
        return OpenAIProvider(model)
    raise ProviderError(f"unknown provider {kind!r}")
