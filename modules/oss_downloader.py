"""
OSS 下载模块
从阿里云 OSS 下载 PDF 文件
"""

import oss2
from typing import Optional, List
from pathlib import Path
import tempfile


class OSSDownloader:
    """阿里云 OSS 下载器"""
    
    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        bucket_name: str,
        endpoint: str,
        cache_dir: str = None
    ):
        """初始化 OSS 下载器"""
        auth = oss2.Auth(access_key_id, access_key_secret)
        endpoint = endpoint.replace('https://', '').replace('http://', '')
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
        self.bucket_name = bucket_name
        self.cache_dir = cache_dir
        
        # 如果指定了缓存目录，确保目录存在
        if self.cache_dir:
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
            print(f"✅ OSS 下载器初始化成功")
            print(f"   Bucket: {bucket_name}")
            print(f"   缓存目录: {self.cache_dir}")
        else:
            print(f"✅ OSS 下载器初始化成功")
            print(f"   Bucket: {bucket_name}")
            print(f"   缓存目录: 系统临时目录")
    
    def download_file(self, oss_path: str, local_path: str = None) -> str:
        """
        下载单个文件
        
        Args:
            oss_path: OSS 文件路径
            local_path: 本地保存路径（可选，默认使用临时文件或缓存目录）
        
        Returns:
            本地文件路径
        """
        if local_path is None:
            if self.cache_dir:
                # 使用指定的缓存目录
                filename = Path(oss_path).name
                local_path = str(Path(self.cache_dir) / filename)
            else:
                # 使用系统临时目录
                suffix = Path(oss_path).suffix
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                local_path = temp_file.name
                temp_file.close()
        
        print(f"📥 下载文件: {oss_path}")
        
        try:
            self.bucket.get_object_to_file(oss_path, local_path)
            file_size = Path(local_path).stat().st_size
            print(f"✅ 下载成功: {local_path} ({file_size:,} bytes)")
            return local_path
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            raise
    
    def list_files(self, prefix: str = '', suffix: str = '.pdf') -> List[str]:
        """
        列出 OSS 中的文件
        
        Args:
            prefix: 文件路径前缀
            suffix: 文件后缀（默认 .pdf）
        
        Returns:
            文件路径列表
        """
        print(f"🔍 扫描 OSS 文件...")
        print(f"   前缀: {prefix or '(根目录)'}")
        print(f"   后缀: {suffix}")
        
        files = []
        for obj in oss2.ObjectIterator(self.bucket, prefix=prefix):
            if obj.key.endswith(suffix):
                files.append(obj.key)
        
        print(f"✅ 找到 {len(files)} 个文件")
        return files
    
    def get_file_info(self, oss_path: str) -> Optional[dict]:
        """获取文件信息"""
        try:
            meta = self.bucket.head_object(oss_path)
            return {
                'size': meta.content_length,
                'last_modified': meta.last_modified,
                'content_type': meta.content_type,
                'etag': meta.etag
            }
        except Exception as e:
            print(f"❌ 获取文件信息失败: {e}")
            return None
    
    def delete_file(self, oss_path: str) -> bool:
        """
        删除 OSS 文件
        
        Args:
            oss_path: OSS 文件路径
        
        Returns:
            是否删除成功
        """
        print(f"🗑️  删除 OSS 文件: {oss_path}")
        
        try:
            self.bucket.delete_object(oss_path)
            print(f"✅ 删除成功")
            return True
        except Exception as e:
            print(f"❌ 删除失败: {e}")
            return False
    
    @staticmethod
    def from_env():
        """从环境变量创建下载器"""
        import os
        from .config import Config
        
        access_key_id = os.getenv('OSS_ACCESS_KEY_ID')
        access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET')
        bucket_name = os.getenv('OSS_BUCKET_NAME')
        endpoint = os.getenv('OSS_ENDPOINT')
        cache_dir = os.getenv('OSS_CACHE_DIR', '')
        
        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            raise ValueError("OSS 配置不完整，请检查环境变量")
        
        return OSSDownloader(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            bucket_name=bucket_name,
            endpoint=endpoint,
            cache_dir=cache_dir if cache_dir else None
        )
