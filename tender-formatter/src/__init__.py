"""
投标格式提取与DOCX生成系统
主包初始化文件
"""

__version__ = "1.2.0"
__author__ = "Tender Formatter Team"

from src.core.processor import TenderProcessor
from src.generators.docx_generator import DocxGenerator  
from src.extractors.format_extractor import FormatExtractor

__all__ = [
    "TenderProcessor",
    "DocxGenerator", 
    "FormatExtractor",
]