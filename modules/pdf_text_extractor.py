"""
PDF 文本提取模块
用于提取 PDF 的全文和页面上下文
"""
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional


class PDFTextExtractor:
    """PDF 文本提取器"""
    
    def __init__(self):
        """初始化文本提取器"""
        pass
    
    def extract_full_text(self, pdf_path: str, max_pages: Optional[int] = None) -> str:
        """
        提取 PDF 全文
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最大提取页数（None 表示提取所有页）
            
        Returns:
            提取的文本内容
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # 确定要提取的页数
            pages_to_extract = min(max_pages, total_pages) if max_pages else total_pages
            
            full_text = []
            
            for page_num in range(pages_to_extract):
                page = doc[page_num]
                text = page.get_text()
                
                if text.strip():
                    full_text.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
            
            doc.close()
            
            result = "\n\n".join(full_text)
            print(f"   提取了 {pages_to_extract}/{total_pages} 页，共 {len(result)} 字符")
            
            return result
            
        except Exception as e:
            print(f"   提取全文失败: {e}")
            return ""
    
    def extract_page_text(self, pdf_path: str, page_num: int) -> str:
        """
        提取指定页面的文本
        
        Args:
            pdf_path: PDF 文件路径
            page_num: 页码（从 0 开始）
            
        Returns:
            页面文本内容
        """
        try:
            doc = fitz.open(pdf_path)
            
            if page_num < 0 or page_num >= len(doc):
                doc.close()
                return ""
            
            page = doc[page_num]
            text = page.get_text()
            doc.close()
            
            return text.strip()
            
        except Exception as e:
            print(f"   提取页面 {page_num} 文本失败: {e}")
            return ""
    
    def extract_context_around_page(
        self, 
        pdf_path: str, 
        page_num: int, 
        context_pages: int = 1
    ) -> str:
        """
        提取指定页面及其前后页面的文本上下文
        
        Args:
            pdf_path: PDF 文件路径
            page_num: 目标页码（从 0 开始）
            context_pages: 前后各提取多少页（默认 1 页）
            
        Returns:
            包含上下文的文本内容
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # 计算页面范围
            start_page = max(0, page_num - context_pages)
            end_page = min(total_pages - 1, page_num + context_pages)
            
            context_text = []
            
            for p in range(start_page, end_page + 1):
                page = doc[p]
                text = page.get_text()
                
                if text.strip():
                    # 标记当前页
                    marker = " (当前页)" if p == page_num else ""
                    context_text.append(f"--- 第 {p + 1} 页{marker} ---\n{text}")
            
            doc.close()
            
            return "\n\n".join(context_text)
            
        except Exception as e:
            print(f"   提取页面上下文失败: {e}")
            return ""
    
    def extract_page_range(self, pdf_path: str, start_page: int, end_page: int) -> str:
        """
        提取指定页面范围的文本
        
        Args:
            pdf_path: PDF 文件路径
            start_page: 起始页码（从 0 开始）
            end_page: 结束页码（从 0 开始，包含）
            
        Returns:
            页面范围内的文本内容
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # 确保页码在有效范围内
            start_page = max(0, start_page)
            end_page = min(total_pages - 1, end_page)
            
            if start_page > end_page:
                doc.close()
                return ""
            
            range_text = []
            
            for page_num in range(start_page, end_page + 1):
                page = doc[page_num]
                text = page.get_text()
                
                if text.strip():
                    range_text.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
            
            doc.close()
            
            return "\n\n".join(range_text)
            
        except Exception as e:
            print(f"   提取页面范围 {start_page}-{end_page} 失败: {e}")
            return ""
    
    def get_page_count(self, pdf_path: str) -> int:
        """
        获取 PDF 总页数
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            总页数
        """
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            return page_count
        except Exception as e:
            print(f"   获取页数失败: {e}")
            return 0
