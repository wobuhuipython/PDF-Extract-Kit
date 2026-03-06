"""
OSS 批量处理监控工具
用于查看 OSS 文件夹中哪些文件已处理，哪些待处理
"""

from pathlib import Path
from modules import OSSDownloader, DataExporter


def monitor_oss_folder(oss_prefix: str):
    """监控 OSS 文件夹的处理状态"""
    print("="*80)
    print("📊 OSS 批量处理监控")
    print("="*80)
    print(f"📁 OSS 路径: {oss_prefix}")
    print("="*80)
    
    try:
        # 初始化
        downloader = OSSDownloader.from_env()
        exporter = DataExporter.from_env()
        
        # 获取 OSS 中的所有 PDF
        print(f"\n🔍 扫描 OSS 文件...")
        pdf_files = downloader.list_files(prefix=oss_prefix, suffix='.pdf')
        
        if not pdf_files:
            print(f"⚠️  未找到 PDF 文件")
            return
        
        print(f"✅ 找到 {len(pdf_files)} 个 PDF 文件")
        
        # 检查每个文件的处理状态
        print(f"\n🔍 检查处理状态...")
        processed_files = []
        pending_files = []
        
        for oss_path in pdf_files:
            pdf_name = Path(oss_path).name
            is_processed = exporter.check_pdf_processed(pdf_name)
            
            if is_processed:
                processed_files.append(oss_path)
            else:
                pending_files.append(oss_path)
        
        # 显示统计
        print(f"\n{'='*80}")
        print("📊 处理状态统计")
        print(f"{'='*80}")
        print(f"  总文件数: {len(pdf_files)}")
        print(f"  已处理: {len(processed_files)} ({len(processed_files)/len(pdf_files)*100:.1f}%)")
        print(f"  待处理: {len(pending_files)} ({len(pending_files)/len(pdf_files)*100:.1f}%)")
        print(f"{'='*80}")
        
        # 显示待处理文件列表
        if pending_files:
            print(f"\n📋 待处理文件列表 ({len(pending_files)} 个):")
            for i, file in enumerate(pending_files, 1):
                print(f"  {i}. {file}")
        else:
            print(f"\n✅ 所有文件都已处理完成！")
        
        # 显示已处理文件（可选）
        show_processed = input(f"\n是否显示已处理文件列表？(y/n): ").strip().lower()
        if show_processed == 'y' and processed_files:
            print(f"\n✓ 已处理文件列表 ({len(processed_files)} 个):")
            for i, file in enumerate(processed_files, 1):
                print(f"  {i}. {file}")
        
        # 生成处理命令
        if pending_files:
            print(f"\n💡 建议的处理命令:")
            print(f"   python main.py --oss-folder {oss_prefix}")
        
    except Exception as e:
        print(f"❌ 监控失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python batch_oss_monitor.py <oss_prefix>")
        print("示例: python batch_oss_monitor.py public/reports/2024/")
        sys.exit(1)
    
    oss_prefix = sys.argv[1]
    monitor_oss_folder(oss_prefix)
