"""
PDF 文本提取模块
提取 PDF 的文本内容用于 AI 分析
"""
import fitz  # PyMuPDF
from typing import Dict, List
from pathlib import Path


class PDFTextExtractor:
    """PDF 文本提取器"""
    
    def __init__(self):
        """初始化"""
        pass
    
    def extract_full_text(self, pdf_path: str, max_pages: int = None) -> str:
        """
        提取 PDF 的完整文本
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最多提取的页数（None 表示提取所有页）
            
        Returns:
            提取的文本内容
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # 如果指定了 max_pages，则限制；否则提取所有页
            pages_to_extract = min(total_pages, max_pages) if max_pages else total_pages
            
            print(f"   提取 {pages_to_extract}/{total_pages} 页...")
            
            full_text = []
            for page_num in range(pages_to_extract):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    full_text.append(f"=== 第 {page_num + 1} 页 ===\n{text}")
            
            doc.close()
            
            result = "\n\n".join(full_text)
            
            print(f"   提取了 {len(result)} 字符")
            
            return result
            
        except Exception as e:
            print(f"   ⚠️  提取文本失败: {e}")
            return ""
    
    def extract_page_text(self, pdf_path: str, page_num: int) -> str:
        """
        提取指定页面的文本
        
        Args:
            pdf_path: PDF 文件路径
            page_num: 页码（从1开始）
            
        Returns:
            页面文本
        """
        try:
            doc = fitz.open(pdf_path)
            
            if page_num < 1 or page_num > len(doc):
                doc.close()
                return ""
            
            page = doc[page_num - 1]
            text = page.get_text()
            doc.close()
            
            return text.strip()
            
        except Exception as e:
            print(f"   ⚠️  提取页面文本失败: {e}")
            return ""
    
    def extract_context_around_page(
        self, 
        pdf_path: str, 
        page_num: int, 
        context_pages: int = 1
    ) -> str:
        """
        提取图表所在页面及其前后页面的文本（提供上下文）
        
        Args:
            pdf_path: PDF 文件路径
            page_num: 图表所在页码
            context_pages: 前后各提取几页
            
        Returns:
            上下文文本
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # 确定提取范围
            start_page = max(1, page_num - context_pages)
            end_page = min(total_pages, page_num + context_pages)
            
            context_text = []
            for p in range(start_page, end_page + 1):
                page = doc[p - 1]
                text = page.get_text()
                if text.strip():
                    marker = " [图表所在页] " if p == page_num else ""
                    context_text.append(f"=== 第 {p} 页{marker} ===\n{text}")
            
            doc.close()
            
            result = "\n\n".join(context_text)
            
            # 限制长度
            max_length = 5000
            if len(result) > max_length:
                result = result[:max_length] + "\n\n...(上下文过长，已截断)"
            
            return result
            
        except Exception as e:
            print(f"   ⚠️  提取上下文失败: {e}")
            return ""
    
    def get_pdf_summary(self, pdf_path: str) -> Dict[str, str]:
        """
        获取 PDF 摘要信息
        
        Returns:
            包含标题、作者、主题等信息的字典
        """
        try:
            doc = fitz.open(pdf_path)
            metadata = doc.metadata
            
            # 提取前几页文本作为摘要
            first_pages_text = []
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    first_pages_text.append(text)
            
            doc.close()
            
            summary_text = "\n\n".join(first_pages_text)
            if len(summary_text) > 2000:
                summary_text = summary_text[:2000] + "..."
            
            return {
                'title': metadata.get('title', ''),
                'author': metadata.get('author', ''),
                'subject': metadata.get('subject', ''),
                'keywords': metadata.get('keywords', ''),
                'first_pages': summary_text
            }
            
        except Exception as e:
            print(f"   ⚠️  获取摘要失败: {e}")
            return {
                'title': '',
                'author': '',
                'subject': '',
                'keywords': '',
                'first_pages': ''
            }
