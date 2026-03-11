"""
NocoDB PDF 获取模块
从 NocoDB 数据库获取 PDF 的 OSS URL 并下载
"""

import requests
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
import urllib.request


class NocoDBPDFFetcher:
    """从 NocoDB 获取 PDF 文件"""
    
    def __init__(
        self,
        api_url: str,
        api_token: str,
        table_id: str,
        cache_dir: str = None
    ):
        """初始化 NocoDB PDF 获取器"""
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.table_id = table_id
        self.cache_dir = cache_dir
        
        if self.cache_dir:
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
            print(f"✅ NocoDB PDF 获取器初始化成功")
            print(f"   API: {self.api_url}")
            print(f"   缓存目录: {self.cache_dir}")
        else:
            print(f"✅ NocoDB PDF 获取器初始化成功")
            print(f"   API: {self.api_url}")
            print(f"   缓存目录: 系统临时目录")
    
    def get_pdf_records(
        self, 
        limit: int = 100,
        offset: int = 0,
        where_clause: str = None
    ) -> List[Dict]:
        """
        从 NocoDB 获取 PDF 记录列表
        
        Args:
            limit: 返回记录数量限制
            offset: 偏移量（用于分页）
            where_clause: 过滤条件，例如 "(status,eq,pending)"
        
        Returns:
            PDF 记录列表
        """
        endpoint = f"{self.api_url}/api/v2/tables/{self.table_id}/records"
        
        headers = {
            'xc-token': self.api_token,
            'Content-Type': 'application/json'
        }
        
        params = {
            'limit': limit,
            'offset': offset
        }
        
        if where_clause:
            params['where'] = where_clause
        
        try:
            response = requests.get(
                endpoint,
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('list', []) or data.get('records', [])
                return records
            else:
                print(f"❌ 获取记录失败: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ 获取记录异常: {e}")
            return []
    
    def download_pdf_from_url(
        self, 
        pdf_url: str, 
        pdf_name: str = None,
        local_path: str = None
    ) -> Optional[str]:
        """
        从 URL 下载 PDF 文件
        
        Args:
            pdf_url: PDF 文件的 URL
            pdf_name: PDF 文件名（用于保存）
            local_path: 本地保存路径（可选）
        
        Returns:
            本地文件路径，失败返回 None
        """
        if not pdf_url:
            print(f"❌ PDF URL 为空")
            return None
        
        # 确定本地保存路径
        if local_path is None:
            if self.cache_dir:
                # 使用缓存目录
                if pdf_name:
                    local_path = str(Path(self.cache_dir) / pdf_name)
                else:
                    # 从 URL 提取文件名
                    filename = Path(pdf_url.split('?')[0]).name
                    local_path = str(Path(self.cache_dir) / filename)
            else:
                # 使用临时文件
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                local_path = temp_file.name
                temp_file.close()
        
        print(f"📥 下载 PDF: {pdf_url}")
        
        try:
            # 下载文件（支持重定向）
            urllib.request.urlretrieve(pdf_url, local_path)
            
            file_size = Path(local_path).stat().st_size
            print(f"✅ 下载成功: {local_path} ({file_size:,} bytes)")
            
            # 验证文件是否为有效的 PDF
            if not self._is_valid_pdf(local_path):
                print(f"⚠️  警告: 下载的文件可能不是有效的 PDF")
            
            return local_path
            
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            # 清理失败的文件
            if Path(local_path).exists():
                Path(local_path).unlink()
            return None
    
    def _is_valid_pdf(self, file_path: str) -> bool:
        """检查文件是否为有效的 PDF"""
        try:
            # 检查文件头
            with open(file_path, 'rb') as f:
                header = f.read(5)
                if header != b'%PDF-':
                    return False
            
            # 尝试用 PyPDF2 验证
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path, strict=False)
                page_count = len(reader.pages)
                
                if page_count == 0:
                    print(f"   ⚠️  PDF 没有页面")
                    return False
                
                print(f"   ✅ PDF 验证通过: {page_count} 页")
                return True
                
            except ImportError:
                # PyPDF2 未安装，只检查文件头
                return True
            except Exception as e:
                print(f"   ⚠️  PDF 验证警告: {e}")
                # 即使验证失败，也返回 True，让后续处理决定
                return True
                
        except Exception as e:
            print(f"   ❌ 文件读取失败: {e}")
            return False
    
    def get_unprocessed_pdfs(
        self,
        oss_url_field: str = 'oss_url',
        status_field: str = 'status',
        pending_status: str = 'pending',
        limit: int = 100
    ) -> List[Dict]:
        """
        获取未处理的 PDF 记录
        
        Args:
            oss_url_field: OSS URL 字段名
            status_field: 状态字段名
            pending_status: 待处理状态值
            limit: 返回记录数量限制
        
        Returns:
            未处理的 PDF 记录列表
        """
        print(f"🔍 查询未处理的 PDF 记录...")
        
        # 构建过滤条件
        where_clause = f"({status_field},eq,{pending_status})"
        
        records = self.get_pdf_records(
            limit=limit,
            where_clause=where_clause
        )
        
        # 过滤出有 OSS URL 的记录
        valid_records = []
        for record in records:
            if record.get(oss_url_field):
                valid_records.append(record)
        
        print(f"✅ 找到 {len(valid_records)} 条未处理的 PDF 记录")
        return valid_records
    
    def update_record_status(
        self,
        record_id: str,
        status: str,
        status_field: str = 'status'
    ) -> bool:
        """
        更新记录状态
        
        Args:
            record_id: 记录 ID
            status: 新状态
            status_field: 状态字段名
        
        Returns:
            是否更新成功
        """
        endpoint = f"{self.api_url}/api/v2/tables/{self.table_id}/records"
        
        headers = {
            'xc-token': self.api_token,
            'Content-Type': 'application/json'
        }
        
        data = {
            status_field: status
        }
        
        try:
            response = requests.patch(
                f"{endpoint}/{record_id}",
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ 更新状态成功: {record_id} -> {status}")
                return True
            else:
                print(f"❌ 更新状态失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 更新状态异常: {e}")
            return False
    
    @staticmethod
    def from_env(cache_dir: str = None):
        """从环境变量创建获取器"""
        import os
        
        api_url = os.getenv('NOCODB_API_URL')
        api_token = os.getenv('NOCODB_API_TOKEN')
        table_id = os.getenv('NOCODB_PDF_TABLE_ID') or os.getenv('NOCODB_TABLE_ID')
        
        if not all([api_url, api_token, table_id]):
            raise ValueError("NocoDB 配置不完整，请检查环境变量")
        
        if cache_dir is None:
            cache_dir = os.getenv('OSS_CACHE_DIR', '')
        
        return NocoDBPDFFetcher(
            api_url=api_url,
            api_token=api_token,
            table_id=table_id,
            cache_dir=cache_dir if cache_dir else None
        )
