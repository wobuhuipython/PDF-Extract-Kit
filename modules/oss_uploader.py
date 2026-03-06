"""
OSS 上传模块
负责图片上传到阿里云 OSS
"""

import os
from typing import Optional, Dict
from pathlib import Path

try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False
    print("⚠️  oss2 未安装，OSS 功能不可用")


class OSSUploader:
    """阿里云 OSS 上传器"""
    
    def __init__(self, config: Optional[Dict[str, str]] = None):
        """初始化 OSS 上传器"""
        self.config = config or {}
        self.bucket = None
        self.enabled = False
        
        if config and OSS_AVAILABLE:
            self._init_bucket()
    
    def _init_bucket(self):
        """初始化 OSS Bucket"""
        try:
            auth = oss2.Auth(
                self.config['access_key_id'],
                self.config['access_key_secret']
            )
            
            endpoint = self.config['endpoint'].replace('https://', '').replace('http://', '')
            
            self.bucket = oss2.Bucket(
                auth,
                endpoint,
                self.config['bucket_name']
            )
            
            self.bucket.get_bucket_info()
            self.enabled = True
            
            print(f"✅ OSS 连接成功: {self.config['bucket_name']}")
            
        except Exception as e:
            print(f"❌ OSS 初始化失败: {e}")
            self.enabled = False
    
    def upload(self, file_data: bytes, filename: str, folder: str = None) -> Optional[str]:
        """上传文件到 OSS"""
        if not self.enabled:
            return None
        
        try:
            base_folder = self.config.get('folder_path', 'reports/')
            if base_folder and not base_folder.endswith('/'):
                base_folder += '/'
            
            if folder:
                if not folder.endswith('/'):
                    folder += '/'
                oss_key = f"{base_folder}{folder}{filename}"
            else:
                oss_key = f"{base_folder}{filename}"
            
            self.bucket.put_object(oss_key, file_data)
            url = self._generate_url(oss_key)
            
            return url
            
        except Exception as e:
            print(f"⚠️  OSS 上传失败 ({filename}): {e}")
            return None
    
    def _generate_url(self, oss_key: str) -> str:
        """生成访问 URL"""
        if self.config.get('domain'):
            return f"{self.config['domain']}/{oss_key}"
        else:
            bucket_name = self.config['bucket_name']
            endpoint = self.config['endpoint'].replace('https://', '').replace('http://', '')
            return f"https://{bucket_name}.{endpoint}/{oss_key}"
    
    def is_enabled(self) -> bool:
        """检查 OSS 是否可用"""
        return self.enabled
    
    @staticmethod
    def from_env():
        """从环境变量创建 OSS 上传器"""
        if not os.getenv('OSS_ACCESS_KEY_ID'):
            return OSSUploader(None)
        
        config = {
            'access_key_id': os.getenv('OSS_ACCESS_KEY_ID'),
            'access_key_secret': os.getenv('OSS_ACCESS_KEY_SECRET'),
            'bucket_name': os.getenv('OSS_BUCKET_NAME'),
            'endpoint': os.getenv('OSS_ENDPOINT'),
            'folder_path': os.getenv('OSS_FOLDER_PATH', 'public/charts/'),
            'domain': os.getenv('OSS_DOMAIN', ''),
        }
        
        return OSSUploader(config)
