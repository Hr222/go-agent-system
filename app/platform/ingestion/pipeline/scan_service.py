from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.platform.ingestion.contracts import (
    PolicyCandidateItem,
    PolicyScanRequest,
    PolicyScanResponse,
    PolicyScanStats,
)


class PolicyIngestionService:
    """目录扫描辅助服务，不属于单文件入库步骤 1 到步骤 8 的主流水线。"""

    # TODO: 后续可将候选判定、文件名推导和文件哈希等纯逻辑抽到独立 util，
    # 让本服务只负责目录遍历、扫描编排和响应组装。

    _image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    _excluded_extensions = {".zip", ".rar", ".7z"}
    _supported_extensions = {".doc", ".docx", ".pdf", *_image_extensions}
    _excluded_keywords = {
        "身份证",
        "签字",
        "签名",
        "公章",
        "法人章",
        "印章",
        "账号",
        "密码",
        "联系方式",
        "联系",
        "logo",
        "照片",
        "截图",
        "盖章",
        "空白",
        "模板",
    }
    _scanned_keywords = {"扫描", "图片版"}

    def scan_candidates(self, request: PolicyScanRequest) -> PolicyScanResponse:
        """
        扫描目录，返回首批制度入库的候选文件列表。

        这个服务只用于候选筛选辅助，不参与 preview/ingest 的主流水线步骤编号。
        """
        root = Path(request.source_root)
        if not root.exists():
            raise FileNotFoundError(f"扫描目录不存在：{root}")
        if not root.is_dir():
            raise NotADirectoryError(f"扫描路径不是目录：{root}")

        files = sorted(path for path in root.rglob("*") if path.is_file())
        counts = Counter(path.suffix.lower() or "<none>" for path in files)
        candidates = [
            self._build_candidate(root=root, path=path)
            for path in files[: request.limit]
        ]

        stats = PolicyScanStats(
            total_files=len(files),
            included_files=sum(
                1 for item in candidates if item.recommended_action == "include"
            ),
            excluded_files=sum(
                1 for item in candidates if item.recommended_action == "exclude"
            ),
            review_files=sum(1 for item in candidates if item.recommended_action == "review"),
            by_extension=dict(sorted(counts.items())),
        )
        return PolicyScanResponse(
            source_root=str(root),
            scanned_at=datetime.now(UTC),
            stats=stats,
            candidates=candidates,
        )

    def _build_candidate(self, root: Path, path: Path) -> PolicyCandidateItem:
        """根据文件名、扩展名和规则，构造候选文件判断结果。"""
        extension = path.suffix.lower()
        relative_path = str(path.relative_to(root)) if path != root else path.name
        full_text = f"{path.name} {relative_path}"
        suspected_scanned = extension in self._image_extensions or (
            extension == ".pdf" and self._contains_keyword(full_text, self._scanned_keywords)
        )

        recommended_action = "exclude"
        parse_method = "skip"
        include_reason: str | None = None
        exclude_reason: str | None = None

        if path.stat().st_size == 0:
            recommended_action = "exclude"
            parse_method = "skip"
            exclude_reason = "空文件。"
        elif extension in self._excluded_extensions:
            recommended_action = "exclude"
            parse_method = "skip"
            exclude_reason = "图片或压缩包不在首批范围内。"
        elif self._contains_keyword(full_text, self._excluded_keywords):
            recommended_action = "exclude"
            parse_method = "skip"
            exclude_reason = "命中首批排除关键字规则。"
        elif extension not in self._supported_extensions:
            recommended_action = "exclude"
            parse_method = "skip"
            include_reason = None
            exclude_reason = "该文件类型不在首批 MVP 支持范围内。"
        elif extension == ".doc":
            recommended_action = "include"
            parse_method = "doc"
            include_reason = "旧版 Word 文件可先转换为 .docx，再继续解析。"
        elif extension in self._image_extensions:
            recommended_action = "include"
            parse_method = "ocr"
            include_reason = "图片扫描件可直接进入 OCR 流程。"
        elif suspected_scanned:
            recommended_action = "include"
            parse_method = "ocr"
            include_reason = "该 PDF 疑似扫描件，将通过 OCR 流程继续处理。"
        else:
            recommended_action = "include"
            parse_method = "direct"
            include_reason = "原生文本文件，适合纳入首批入库。"

        return PolicyCandidateItem(
            source_path=str(path),
            relative_path=relative_path,
            file_name=path.name,
            extension=extension,
            size_bytes=path.stat().st_size,
            sha256=self._file_hash(path),
            recommended_action=recommended_action,
            parse_method=parse_method,
            suspected_scanned=suspected_scanned,
            policy_name_guess=self._guess_policy_name(path.stem),
            include_reason=include_reason,
            exclude_reason=exclude_reason,
        )

    def _guess_policy_name(self, stem: str) -> str:
        """根据文件名 stem 粗略推导制度名称。"""
        cleaned = re.sub(r"^\d{6,8}", "", stem)
        cleaned = re.sub(
            r"[（(][^（）()]{0,40}(审核|盖章|空白|模板)[^（）()]{0,40}[）)]",
            "",
            cleaned,
        )
        cleaned = re.sub(r"[-_]{2,}", "-", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip(" -_") or stem

    def _contains_keyword(self, text: str, keywords: set[str]) -> bool:
        """判断文本中是否命中任一关键字。"""
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    def _file_hash(self, path: Path) -> str:
        """计算文件 SHA-256，用于候选展示和后续溯源。"""
        digest = sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
