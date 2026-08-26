from __future__ import annotations

import subprocess
from pathlib import Path

from app.platform.ingestion.contracts import FormatNormalizationResult, RegisteredFileInfo


class PolicyFormatNormalizer:
    """把旧版 `.doc` 标准化为 `.docx`。"""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def normalize(self, registered_file: RegisteredFileInfo) -> FormatNormalizationResult:
        """
        步骤 3：把旧版 Word 文档转换成 `.docx` 派生文件。

        原始文件不会被覆盖，只会生成一个标准化副本，
        这样后续解析阶段始终面对统一格式。
        """
        if registered_file.extension != ".doc":
            return FormatNormalizationResult(
                status="skipped",
                source_path=registered_file.source_path,
                normalized_path=registered_file.source_path,
                output_extension=registered_file.extension,
                converter="none",
                message="只有旧版 .doc 文件才需要格式归一化。",
            )

        source_path = Path(registered_file.source_path)
        output_dir = (self.workspace_root / "normalized" / registered_file.sha256[:12]).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (output_dir / f"{source_path.stem}.docx").resolve()

        if output_path.exists():
            return FormatNormalizationResult(
                status="success",
                source_path=registered_file.source_path,
                normalized_path=str(output_path),
                output_extension=".docx",
                converter="powershell-word-com",
                message="已复用现有的归一化 .docx 文件。",
            )

        try:
            self._convert_via_word_com(source_path=source_path, output_path=output_path)
        except Exception as exc:
            return FormatNormalizationResult(
                status="failed",
                source_path=registered_file.source_path,
                normalized_path=str(output_path),
                output_extension=".docx",
                converter="powershell-word-com",
                message=str(exc),
            )

        return FormatNormalizationResult(
            status="success",
            source_path=registered_file.source_path,
            normalized_path=str(output_path),
            output_extension=".docx",
            converter="powershell-word-com",
            message="已将旧版 .doc 转换为归一化 .docx 文件。",
        )

    def _convert_via_word_com(self, *, source_path: Path, output_path: Path) -> None:
        """
        在 Windows 上通过本机 Microsoft Word COM 自动化执行格式转换。

        这里单独封装成适配层，后续如果改用 LibreOffice，
        只需要替换这一层实现。
        """
        script = f"""
$ErrorActionPreference = 'Stop'
$source = '{str(source_path).replace("'", "''")}'
$target = '{str(output_path).replace("'", "''")}'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$document = $word.Documents.Open($source)
$document.SaveAs([ref] $target, [ref] 16)
$document.Close()
$word.Quit()
""".strip()
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "未知转换错误。"
            raise RuntimeError(f"将 .doc 转换为 .docx 失败：{stderr}")
