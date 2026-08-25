from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.shared.config import Settings


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, zhipu_api_key="test-key", **values)


def test_glm_resource_profile_is_the_default() -> None:
    configuration = _settings()

    profile = configuration.llm_provider_config()

    assert profile.provider == "glm"
    assert profile.runtime_profile == "resource"
    assert profile.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert profile.model == "glm-4.5-air"
    assert profile.timeout_seconds == 60.0
    assert profile.temperature == 0.0
    assert profile.max_tokens == 16_384


def test_coding_plan_profile_uses_only_its_own_configuration() -> None:
    configuration = _settings(
        glm_runtime_profile="coding_plan",
        zhipu_resource_base_url="https://resource.example.com/v1",
        zhipu_resource_chat_model="resource-model",
        zhipu_coding_base_url="https://coding.example.com/v1",
        zhipu_coding_chat_model="coding-model",
        zhipu_coding_timeout_seconds=75,
        zhipu_coding_temperature=0.3,
        zhipu_coding_max_tokens=2048,
    )

    profile = configuration.llm_provider_config()

    assert profile.runtime_profile == "coding_plan"
    assert profile.base_url == "https://coding.example.com/v1"
    assert profile.model == "coding-model"
    assert profile.timeout_seconds == 75.0
    assert profile.temperature == 0.3
    assert profile.max_tokens == 2048


def test_resource_profile_prefers_new_configuration_and_falls_back_to_legacy() -> None:
    legacy_only = _settings(
        zhipu_base_url="https://legacy.example.com/v1",
        zhipu_chat_model="legacy-model",
        zhipu_timeout_seconds=70,
        zhipu_temperature=0.2,
        zhipu_max_tokens=4096,
    )
    overridden = _settings(
        zhipu_base_url="https://legacy.example.com/v1",
        zhipu_chat_model="legacy-model",
        zhipu_timeout_seconds=70,
        zhipu_temperature=0.2,
        zhipu_max_tokens=4096,
        zhipu_resource_base_url="https://resource.example.com/v1",
        zhipu_resource_chat_model="resource-model",
        zhipu_resource_timeout_seconds=80,
        zhipu_resource_temperature=0.1,
        zhipu_resource_max_tokens=8192,
    )

    legacy_profile = legacy_only.llm_provider_config()
    new_profile = overridden.llm_provider_config()

    assert (
        legacy_profile.base_url,
        legacy_profile.model,
        legacy_profile.timeout_seconds,
        legacy_profile.temperature,
        legacy_profile.max_tokens,
    ) == ("https://legacy.example.com/v1", "legacy-model", 70.0, 0.2, 4096)
    assert (
        new_profile.base_url,
        new_profile.model,
        new_profile.timeout_seconds,
        new_profile.temperature,
        new_profile.max_tokens,
    ) == ("https://resource.example.com/v1", "resource-model", 80.0, 0.1, 8192)


def test_deepseek_ignores_glm_runtime_profile() -> None:
    configuration = _settings(
        llm_provider="deepseek",
        glm_runtime_profile="coding_plan",
        deepseek_api_key="deepseek-key",
        deepseek_base_url="https://deepseek.example.com/v1",
        deepseek_chat_model="deepseek-model",
    )

    profile = configuration.llm_provider_config()

    assert profile.provider == "deepseek"
    assert profile.runtime_profile is None
    assert profile.base_url == "https://deepseek.example.com/v1"
    assert profile.model == "deepseek-model"


def test_provider_diagnostics_exposes_glm_profile_without_starting_a_request() -> None:
    project_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "tools/llm_provider_diagnostics.py", "--help"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--glm-profile" in completed.stdout
    assert "coding_plan" in completed.stdout
