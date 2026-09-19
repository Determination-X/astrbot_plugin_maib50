"""Persistent, instance-local song aliases and moderation requests."""

import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path


class AliasError(ValueError):
    """A user-correctable alias or request error."""


def normalize_title(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("〜", "~").replace("～", "~")
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = normalized.replace("“", '"').replace("”", '"')
    normalized = normalized.replace("？", "?").replace("！", "!")
    normalized = normalized.replace("　", " ")
    normalized = normalized.replace("✪", "")
    return re.sub(r"\s+", " ", normalized).strip()


def alias_key(text: str) -> str:
    return normalize_title(text).casefold()


class AliasManager:
    """Read once; use an O(1) in-memory index for lookups and atomic JSON writes."""

    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "title_aliases.json"
        self.requests_path = data_dir / "alias_requests.json"

        if not self.path.exists():
            self._save(self.path, {})
        raw = self._read(self.path)
        if not isinstance(raw, dict):
            raise AliasError(f"{self.path} 必须是 JSON 对象。")

        self._aliases: dict[str, str] = {}
        self._index: dict[str, str] = {}
        for alias, title in raw.items():
            self._validate_pair(alias, title)
            key = alias_key(alias)
            if key in self._index:
                raise AliasError(f"别名文件存在规范化冲突：{alias} / {self._index[key]}")
            self._aliases[alias] = title
            self._index[key] = alias

        self._requests: list[dict] = []
        self._next_id = 1
        if self.requests_path.exists():
            requests = self._read(self.requests_path)
            if not isinstance(requests, dict):
                raise AliasError("alias_requests.json 格式错误。")
            pending = requests.get("pending")
            next_id = requests.get("next_id")
            if not isinstance(pending, list) or type(next_id) is not int or next_id < 1:
                raise AliasError("alias_requests.json 格式错误。")
            used_ids: set[int] = set()
            for req in pending:
                if not isinstance(req, dict) or type(req.get("id")) is not int:
                    raise AliasError("alias_requests.json 内含无效申请。")
                self._validate_pair(req.get("alias"), req.get("title"))
                if req["id"] in used_ids or req["id"] < 1:
                    raise AliasError("alias_requests.json 内含重复或无效编号。")
                used_ids.add(req["id"])
            if used_ids and next_id <= max(used_ids):
                raise AliasError("alias_requests.json 的 next_id 不正确。")
            self._requests = pending
            self._next_id = next_id

    @staticmethod
    def _read(path: Path):
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AliasError(f"读取 {path} 失败，请检查文件：{exc}") from exc

    @staticmethod
    def _save(path: Path, payload) -> None:
        """Replace on success only; do not truncate a working instance file."""
        name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as file:
                name = file.name
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def _validate_pair(alias: str, title: str) -> None:
        if not isinstance(alias, str) or not 1 <= len(alias.strip()) <= 64:
            raise AliasError("别名长度必须在 1–64 字符之间。")
        if not alias_key(alias):
            raise AliasError("别名规范化后不能为空。")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 300:
            raise AliasError("目标曲名长度必须在 1–300 字符之间。")

    def get_title(self, alias: str) -> str | None:
        original = self._index.get(alias_key(alias))
        return self._aliases.get(original) if original is not None else None

    def add(self, alias: str, title: str) -> None:
        self._validate_pair(alias, title)
        key = alias_key(alias)
        if key in self._index:
            existing = self._index[key]
            raise AliasError(f"别名「{existing}」已指向「{self._aliases[existing]}」。")
        updated = {**self._aliases, alias: title}
        self._save(self.path, updated)
        self._aliases = updated
        self._index[key] = alias

    def delete(self, alias: str) -> str:
        original = self._index.get(alias_key(alias))
        if original is None:
            raise AliasError("没有这个别名。")
        updated = dict(self._aliases)
        title = updated.pop(original)
        self._save(self.path, updated)
        self._aliases = updated
        del self._index[alias_key(original)]
        return title

    def list_aliases(self, keyword: str = "") -> list[tuple[str, str]]:
        key = alias_key(keyword)
        return sorted(
            ((alias, title) for alias, title in self._aliases.items()
             if not key or key in alias_key(alias) or key in alias_key(title)),
            key=lambda item: alias_key(item[0]),
        )

    def submit(self, alias: str, title: str, platform: str, sender: str) -> int:
        self._validate_pair(alias, title)
        key = alias_key(alias)
        if key in self._index:
            original = self._index[key]
            raise AliasError(f"别名「{original}」已指向「{self._aliases[original]}」。")
        for req in self._requests:
            if alias_key(req["alias"]) == key:
                raise AliasError(f"相同别名已有待审申请 #{req['id']}。")
        if len(self._requests) >= 1000:
            raise AliasError("待审队列已满，请联系管理员。")
        request = {
            "id": self._next_id,
            "alias": alias,
            "title": title,
            "platform": str(platform),
            "sender": str(sender),
        }
        updated = [*self._requests, request]
        self._save(self.requests_path, {
            "next_id": self._next_id + 1, "pending": updated,
        })
        self._requests = updated
        self._next_id += 1
        return request["id"]

    def pending(self) -> list[dict]:
        return [dict(request) for request in self._requests]

    def get_request(self, request_id: int) -> dict:
        for request in self._requests:
            if request["id"] == request_id:
                return dict(request)
        raise AliasError(f"待审申请 #{request_id} 不存在。")

    def _remove_request(self, request_id: int) -> None:
        updated = [req for req in self._requests if req["id"] != request_id]
        self._save(self.requests_path, {
            "next_id": self._next_id, "pending": updated,
        })
        self._requests = updated

    def approve(self, request_id: int) -> dict:
        request = self.get_request(request_id)
        self.add(request["alias"], request["title"])
        self._remove_request(request_id)
        return request

    def reject(self, request_id: int) -> dict:
        request = self.get_request(request_id)
        self._remove_request(request_id)
        return request
