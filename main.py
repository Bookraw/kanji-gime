from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TypedDict


class Criterion(TypedDict):
    id: str
    title: str
    description: str
    weight: int | float


class Candidate(TypedDict):
    name: str
    statement: str


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CRITERIA_PATH = BASE_DIR / "criteria.json"
DEFAULT_MODEL = "gemini-2.0-flash"


class ThinkingAnimation:
    def __init__(self, message: str = "Gemini が考えています") -> None:
        self.message = message
        self._max_dots = 3
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._line_width = len(self.message) + self._max_dots

    def _run(self) -> None:
        dots = 1
        while not self._stop_event.is_set():
            suffix = "." * dots
            padding = " " * (self._max_dots - dots)
            print(f"\r{self.message}{suffix}{padding}", end="", flush=True)
            time.sleep(0.5)
            dots = 1 if dots >= self._max_dots else dots + 1

    def __enter__(self) -> "ThinkingAnimation":
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self._stop_event.set()
        self._thread.join()
        print("\r" + (" " * self._line_width) + "\r", end="", flush=True)
        print()


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def load_criteria(path: Path = CRITERIA_PATH) -> list[Criterion]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"評価基準ファイルが見つかりません: {path}") from exc
    except OSError as exc:
        raise RuntimeError(f"評価基準ファイルを読み込めませんでした: {path} ({exc})") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "criteria.json の JSON 形式が不正です。"
            f" 行 {exc.lineno} 列 {exc.colno} 付近を確認してください。"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError("criteria.json のトップレベルはオブジェクトである必要があります。")

    criteria = payload.get("criteria")
    if not isinstance(criteria, list):
        raise RuntimeError("criteria.json には `criteria` 配列が必要です。")

    validated: list[Criterion] = []
    required_fields = ("id", "title", "description", "weight")

    for index, item in enumerate(criteria):
        location = f"criteria[{index}]"

        if not isinstance(item, dict):
            raise RuntimeError(f"{location} はオブジェクトである必要があります。")

        missing_fields = [field for field in required_fields if field not in item]
        if missing_fields:
            raise RuntimeError(
                f"{location} に必須項目が不足しています: {', '.join(missing_fields)}"
            )

        criterion_id = item["id"]
        title = item["title"]
        description = item["description"]
        weight = item["weight"]

        if not isinstance(criterion_id, str) or not criterion_id.strip():
            raise RuntimeError(f"{location}.id は空でない文字列である必要があります。")
        if not isinstance(title, str) or not title.strip():
            raise RuntimeError(f"{location}.title は空でない文字列である必要があります。")
        if not isinstance(description, str) or not description.strip():
            raise RuntimeError(f"{location}.description は空でない文字列である必要があります。")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            raise RuntimeError(f"{location}.weight は数値である必要があります。")

        validated.append(
            {
                "id": criterion_id.strip(),
                "title": title.strip(),
                "description": description.strip(),
                "weight": weight,
            }
        )

    if not validated:
        raise RuntimeError("criteria.json の `criteria` 配列が空です。少なくとも1件必要です。")

    return validated


def format_criteria_for_display(criteria: list[Criterion]) -> str:
    lines = ["公開する評価基準:"]
    for item in criteria:
        lines.append(f"- {item['title']} (重み: {item['weight']})")
        lines.append(f"  説明: {item['description']}")
    return "\n".join(lines)


def format_criteria_for_llm(criteria: list[Criterion]) -> str:
    lines = ["審査に使う評価基準:"]
    for item in criteria:
        lines.append(
            f"- [{item['id']}] {item['title']} / 重み {item['weight']} / {item['description']}"
        )
    return "\n".join(lines)


def collect_candidates() -> list[Candidate]:
    print("代表候補の入力を始めます。候補名を空欄で入力すると終了します。")
    candidates: list[Candidate] = []

    while True:
        name = input("\n候補名: ").strip()
        if not name:
            break

        statement = input("意気込み: ").strip()
        while not statement:
            print("意気込みは空にできません。もう一度入力してください。")
            statement = input("意気込み: ").strip()

        candidates.append({"name": name, "statement": statement})
        print(f"現在 {len(candidates)} 件の候補を受け付けました。")

    if not candidates:
        raise RuntimeError("候補が1件も入力されていません。少なくとも1件は入力してください。")

    return candidates


def format_candidates_for_llm(candidates: list[Candidate]) -> str:
    lines = ["候補者一覧:"]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(f"{index}. 候補名: {candidate['name']}")
        lines.append(f"   意気込み: {candidate['statement']}")
    return "\n".join(lines)


def build_llm_prompt(candidates: list[Candidate], criteria: list[Criterion]) -> str:
    return "\n\n".join(
        [
            "あなたは研究室や班の代表候補を選ぶ審査役です。",
            "候補者の意気込みを読み、評価基準に沿って最も適した代表候補を1名だけ選んでください。",
            "出力は必ず JSON オブジェクト1つだけにしてください。余計な説明や Markdown は不要です。",
            (
                'JSON の形式: '
                '{"selected_candidate":"候補名","reason":"選出理由","runner_up_comment":"次点へのコメント"}'
            ),
            format_candidates_for_llm(candidates),
            format_criteria_for_llm(criteria),
        ]
    )


def extract_text_from_gemini_response(payload: dict) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini API の応答に候補テキストが含まれていません。")

    content = candidates[0].get("content")
    if not isinstance(content, dict):
        raise RuntimeError("Gemini API の応答形式が想定と異なります。")

    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Gemini API の応答に本文が含まれていません。")

    text_fragments = [part.get("text", "") for part in parts if isinstance(part, dict)]
    text = "\n".join(fragment for fragment in text_fragments if fragment).strip()
    if not text:
        raise RuntimeError("Gemini API の応答本文が空でした。")
    return text


def parse_llm_json(text: str) -> dict[str, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "LLM の返答を JSON として解釈できませんでした。"
            f" 生テキスト: {text}"
        ) from exc

    required_keys = ("selected_candidate", "reason", "runner_up_comment")
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise RuntimeError(
            "LLM の返答 JSON に必要な項目が不足しています: " + ", ".join(missing)
        )

    result: dict[str, str] = {}
    for key in required_keys:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"LLM の返答 JSON の `{key}` は空でない文字列である必要があります。")
        result[key] = value.strip()
    return result


def call_gemini(prompt: str, api_key: str, model: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "Gemini API の呼び出しに失敗しました。"
            f" HTTP {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Gemini API に接続できませんでした。ネットワーク設定や API エンドポイントを確認してください。"
        ) from exc
    except TimeoutError as exc:
        raise RuntimeError("Gemini API の呼び出しがタイムアウトしました。") from exc

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini API の応答 JSON を解析できませんでした。") from exc

    return extract_text_from_gemini_response(payload)


def get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"環境変数 `{name}` が設定されていません。.env またはシステム環境変数を確認してください。"
        )
    return value


def main() -> int:
    try:
        load_dotenv()
        criteria = load_criteria()
        candidates = collect_candidates()
        print("\n入力完了しました。隠していた評価基準を表示します。\n")
        print(format_criteria_for_display(criteria))

        prompt = build_llm_prompt(candidates, criteria)
        print("\n----- LLM に送る最終プロンプト -----")
        print(prompt)
        print("----- ここまで -----\n")

        api_key = get_required_env("GEMINI_API_KEY")
        model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        with ThinkingAnimation():
            raw_response = call_gemini(prompt, api_key, model)
        result = parse_llm_json(raw_response)
    except RuntimeError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n入力を中断しました。", file=sys.stderr)
        return 130

    print("判定結果")
    print(f"選出候補: {result['selected_candidate']}")
    print(f"理由: {result['reason']}")
    print(f"次点へのコメント: {result['runner_up_comment']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
