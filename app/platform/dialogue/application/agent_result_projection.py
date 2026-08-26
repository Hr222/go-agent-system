from __future__ import annotations

from collections.abc import Mapping

_HIDDEN_KEYS = frozenset(
    {
        "provider",
        "provider_response",
        "permissions",
        "stack",
        "traceback",
        "base64",
        "content_base64",
    }
)


class AgentResultProjector:
    """把 Agent 结果压缩成可持久化、可展示的白名单 JSON。"""

    def project(self, output: Mapping[str, object], *, call_id: str) -> dict[str, object]:
        artifacts = output.get("artifacts")
        if isinstance(artifacts, list) and any(isinstance(item, Mapping) for item in artifacts):
            projected: dict[str, object] = {}
            analysis = output.get("analysis")
            if isinstance(analysis, Mapping):
                projected["analysis"] = self._analysis(analysis)
            projected["artifacts"] = [
                self._artifact(item, call_id=call_id, index=index)
                for index, item in enumerate(artifacts)
                if isinstance(item, Mapping)
            ]
            return projected

        artifact = output.get("artifact")
        if isinstance(artifact, Mapping):
            return {"artifact": self._artifact(artifact, call_id=call_id, index=0)}

        safe = self._value(output)
        return safe if isinstance(safe, dict) and safe else {"result": safe}

    def _analysis(self, analysis: Mapping[str, object]) -> dict[str, object]:
        allowed = (
            "status",
            "package_type",
            "summary",
            "format_start_block_id",
            "format_end_block_id",
        )
        return {
            key: self._value(analysis[key])
            for key in allowed
            if key in analysis and self._value(analysis[key]) is not None
        }

    def _artifact(
        self,
        artifact: Mapping[str, object],
        *,
        call_id: str,
        index: int,
    ) -> dict[str, object]:
        size = artifact.get("size")
        if size is None:
            content = artifact.get("content")
            if isinstance(content, Mapping) and content.get("__agent_bytes__") is True:
                size = content.get("size")
        if isinstance(size, Mapping) and size.get("__agent_bytes__") is True:
            size = size.get("size")
        metadata: dict[str, object] = {
            "file_name": self._text(artifact.get("file_name"), default=f"artifact-{index}"),
            "media_type": self._text(
                artifact.get("media_type"),
                default="application/octet-stream",
            ),
            "size": size if isinstance(size, int) and size >= 0 else 0,
            "resource_id": self._text(
                artifact.get("resource_id"),
                default=f"agent-artifact:{call_id}:{index}",
            ),
        }
        return metadata

    def _value(self, value: object, *, key: str | None = None) -> object:
        if key in _HIDDEN_KEYS:
            return None
        if isinstance(value, Mapping):
            result: dict[str, object] = {}
            for raw_key, raw_value in value.items():
                item_key = str(raw_key)
                if item_key in _HIDDEN_KEYS or item_key == "__agent_bytes__":
                    continue
                safe = self._value(raw_value, key=item_key)
                if safe is not None:
                    result[item_key] = safe
            return result
        if isinstance(value, list):
            return [safe for item in value if (safe := self._value(item)) is not None]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return None

    @staticmethod
    def _text(value: object, *, default: str) -> str:
        return value.strip() if isinstance(value, str) and value.strip() else default


__all__ = ["AgentResultProjector"]
