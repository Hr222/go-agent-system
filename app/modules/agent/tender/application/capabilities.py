from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True, frozen=True)
class TenderCapabilityDescriptor:
    """Tender Agent 对外可发现的能力描述。"""

    name: str
    version: str
    description: str


class TenderCapabilityRegistry:
    """维护已实现的 Tender Agent 能力，不承担能力执行。"""

    def __init__(self, capabilities: Iterable[TenderCapabilityDescriptor] = ()) -> None:
        self._capabilities: dict[str, TenderCapabilityDescriptor] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: TenderCapabilityDescriptor) -> None:
        if capability.name in self._capabilities:
            raise ValueError(f"Tender 能力已注册：{capability.name}")
        self._capabilities[capability.name] = capability

    def list_available(self) -> tuple[TenderCapabilityDescriptor, ...]:
        return tuple(self._capabilities.values())

    def get(self, name: str) -> TenderCapabilityDescriptor:
        try:
            return self._capabilities[name]
        except KeyError as exc:
            raise KeyError(f"Tender 能力不存在：{name}") from exc


V1_GENERATE_SKELETON_CAPABILITY = TenderCapabilityDescriptor(
    name="tender.generate_bid_skeleton",
    version="v1",
    description="读取招标文件并生成一份或多份可填写的投标骨架文件。",
)

V1_EXTRACT_FORMAT_SECTION_CAPABILITY = TenderCapabilityDescriptor(
    name="tender.extract_bid_format_section",
    version="v1",
    description="Copy a confirmed bid-format range from the source DOCX as a standard resource.",
)

V1_VERIFY_EXTRACTION_BOUNDARY_CAPABILITY = TenderCapabilityDescriptor(
    name="tender.verify_extraction_boundary",
    version="v1",
    description="Return source context around candidate extraction boundaries for Agent review.",
)

V1_TENDER_CAPABILITIES = (
    V1_GENERATE_SKELETON_CAPABILITY,
    V1_EXTRACT_FORMAT_SECTION_CAPABILITY,
    V1_VERIFY_EXTRACTION_BOUNDARY_CAPABILITY,
)


V2_FILL_CONTENT_CAPABILITY_NAME = "tender.fill_bid_content"
