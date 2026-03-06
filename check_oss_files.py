"""
检查 OSS 文件列表
快速查看 OSS 中有哪些文件
"""

from modules import OSSDownloader


def check_oss_files():
    """检查 OSS 文件"""
    print("="*80)
    print("🔍 检查 OSS 文件")
    print("="*80)
    
    try:
        downloader = OSSDownloader.from_env()
        
        # 测试不同的路径前缀
        test_prefixes = [
            'Reports/',    # 你尝试的路径
        ]
        
        for prefix in test_prefixes:
            print(f"\n📁 检查路径: {prefix or '(根目录)'}")
            print("-"*60)
            
            try:
                files = downloader.list_files(prefix=prefix, suffix='.pdf')
                
                if files:
                    print(f"✅ 找到 {len(files)} 个 PDF 文件:")
                    for i, file in enumerate(files[:10], 1):
                        print(f"   {i}. {file}")
                    if len(files) > 10:
                        print(f"   ... 还有 {len(files) - 10} 个文件")
                else:
                    print(f"⚠️  未找到 PDF 文件")
                    
            except Exception as e:
                print(f"❌ 检查失败: {e}")
        
        # 让用户输入自定义路径
        print(f"\n" + "="*80)
        custom_prefix = input("请输入要检查的路径前缀（留空跳过）: ").strip()
        
        if custom_prefix:
            print(f"\n📁 检查自定义路径: {custom_prefix}")
            print("-"*60)
            files = downloader.list_files(prefix=custom_prefix, suffix='.pdf')
            
            if files:
                print(f"✅ 找到 {len(files)} 个 PDF 文件:")
                for i, file in enumerate(files, 1):
                    print(f"   {i}. {file}")
            else:
                print(f"⚠️  未找到 PDF 文件")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    check_oss_files()
