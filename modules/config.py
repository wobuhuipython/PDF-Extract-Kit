"""
配置管理模块
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """配置类"""
    
    # OpenAI API 配置
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'qwen-vl-max')
    
    # 阿里云 OSS 配置
    OSS_ACCESS_KEY_ID = os.getenv('OSS_ACCESS_KEY_ID', '')
    OSS_ACCESS_KEY_SECRET = os.getenv('OSS_ACCESS_KEY_SECRET', '')
    OSS_BUCKET_NAME = os.getenv('OSS_BUCKET_NAME', '')
    OSS_ENDPOINT = os.getenv('OSS_ENDPOINT', '')
    OSS_FOLDER_PATH = os.getenv('OSS_FOLDER_PATH', 'public/charts/')
    OSS_DOMAIN = os.getenv('OSS_DOMAIN', '')
    
    # NocoDB 配置
    NOCODB_API_URL = os.getenv('NOCODB_API_URL', '')
    NOCODB_API_TOKEN = os.getenv('NOCODB_API_TOKEN', '')
    NOCODB_TABLE_ID = os.getenv('NOCODB_TABLE_ID', '')
    NOCODB_BASE_ID = os.getenv('NOCODB_BASE_ID', '')
    
    # PDF-Extract-Kit 模型配置
    LAYOUT_MODEL_PATH = os.getenv('LAYOUT_MODEL_PATH', 
        '/home/root123/文档/liang/PDF-Extract-Kit/models/opendatalab/pdf-extract-kit-1/models/Layout/YOLO/doclayout_yolo_ft.pt')
    
    # 提取配置
    MIN_CONFIDENCE = float(os.getenv('MIN_CONFIDENCE', '0.5'))
    CAPTION_DISTANCE = int(os.getenv('CAPTION_DISTANCE', '200'))
    SAVE_LOCAL_IMAGES = os.getenv('SAVE_LOCAL_IMAGES', 'false').lower() == 'true'
    
    # PDF 文本提取配置
    EXTRACT_FULL_TEXT = os.getenv('EXTRACT_FULL_TEXT', 'true').lower() == 'true'
    MAX_TEXT_PAGES = int(os.getenv('MAX_TEXT_PAGES', '0'))  # 0 表示提取所有页
    
    # 输出配置
    OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'outputs/pdf_extract_ai')
    
    # OSS 下载缓存配置
    OSS_CACHE_DIR = os.getenv('OSS_CACHE_DIR', '')  # 留空则使用系统临时目录
    
    @classmethod
    def print_config(cls):
        """打印配置信息"""
        print("="*80)
        print("配置信息")
        print("="*80)
        print(f"OpenAI API: {cls.OPENAI_BASE_URL}")
        print(f"OpenAI Model: {cls.OPENAI_MODEL}")
        print(f"OSS: {'已配置' if cls.OSS_ACCESS_KEY_ID else '未配置'}")
        print(f"NocoDB: {'已配置' if cls.NOCODB_API_URL else '未配置'}")
        print(f"布局模型: {cls.LAYOUT_MODEL_PATH}")
        print(f"最小置信度: {cls.MIN_CONFIDENCE}")
        print(f"标题距离: {cls.CAPTION_DISTANCE}")
        print(f"保存本地: {cls.SAVE_LOCAL_IMAGES}")
        print("="*80)
