from modelscope import snapshot_download
import os

os.makedirs('./models', exist_ok=True)

print("从ModelScope下载模型...")
snapshot_download(
    model_id='opendatalab/pdf-extract-kit-1.0',
    cache_dir='./models'
)
print("下载完成！")