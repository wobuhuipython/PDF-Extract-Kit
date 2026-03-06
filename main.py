"""
主程序 - 模块化版本
支持本地文件和 OSS 下载
"""
import os
from pathlib import Path
from modules import Config, PDFProcessor, OSSDownloader


def process_single_pdf(pdf_path: str, cleanup_temp: bool = True, skip_processed: bool = True):
    """处理单个 PDF"""
    print("="*80)
    print("📊 PDF-Extract-Kit with AI Analysis")
    print("="*80)
    
    Config.print_config()
    
    # 判断是否为 OSS 路径
    is_oss = pdf_path.startswith('oss://')
    local_pdf_path = pdf_path
    temp_file = None
    
    # 获取 PDF 文件名（用于检查是否已处理）
    if is_oss:
        pdf_name = Path(pdf_path.replace('oss://', '')).name
    else:
        pdf_name = Path(pdf_path).name
    
    # 检查是否已处理过（在下载前检查，节省时间和流量）
    if skip_processed:
        from modules import DataExporter
        temp_exporter = DataExporter.from_env()
        
        # 先获取锁，防止并发处理
        if not temp_exporter.acquire_processing_lock(pdf_name):
            print(f"⏭️  跳过（文件正在处理或已完成）: {pdf_name}")
            return {
                'success': True,
                'skipped': True,
                'message': '已处理或正在处理',
                'charts': [],
                'pdf_industry': '',
                'elapsed_time': 0,
                'timestamp': ''
            }
    
    if is_oss:
        # 从 OSS 下载
        oss_path = pdf_path.replace('oss://', '')
        print(f"\n📥 从 OSS 下载: {oss_path}")
        
        try:
            downloader = OSSDownloader.from_env()
            local_pdf_path = downloader.download_file(oss_path)
            temp_file = local_pdf_path
            print(f"📄 临时文件: {temp_file}")
        except Exception as e:
            print(f"❌ OSS 下载失败: {e}")
            return None
    else:
        # 本地文件
        if not Path(pdf_path).exists():
            print(f"❌ 文件不存在: {pdf_path}")
            return None
    
    try:
        # 传递原始 PDF 名称（而不是临时文件名）
        processor = PDFProcessor(local_pdf_path, original_name=pdf_name if is_oss else None)
        result = processor.process()
        
        if result['success']:
            print(f"\n🎉 处理完成！")
            
            # 注意：不需要手动释放锁
            # 因为数据已经上传到数据库，check_pdf_processed 会返回 true
            # 锁记录会在数据上传后自动失效（被正常记录覆盖）
            
            return result
        else:
            print(f"\n⚠️  {result.get('message', '处理失败')}")
            
            # 处理失败需要释放锁，让其他进程可以重试
            if skip_processed and is_oss:
                from modules import DataExporter
                temp_exporter = DataExporter.from_env()
                temp_exporter.release_processing_lock(pdf_name)
            
            return None
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        
        # 异常时释放锁，让其他进程可以重试
        if skip_processed and is_oss:
            try:
                from modules import DataExporter
                temp_exporter = DataExporter.from_env()
                temp_exporter.release_processing_lock(pdf_name)
            except:
                pass
        
        return None
    finally:
        # 清理本地临时文件（从 OSS 下载的文件）
        if temp_file and cleanup_temp:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    print(f"🗑️  已清理本地临时文件: {temp_file}")
            except Exception as e:
                print(f"⚠️  清理临时文件失败: {e}")


def process_folder(folder_path: str, skip_processed: bool = True, recursive: bool = True):
    """批量处理文件夹中的所有 PDF"""
    folder = Path(folder_path)
    
    if not folder.exists() or not folder.is_dir():
        print(f"❌ 文件夹不存在: {folder_path}")
        return
    
    # 查找所有 PDF 文件（支持递归）
    if recursive:
        pdf_files = list(folder.rglob("*.pdf"))  # 递归查找
    else:
        pdf_files = list(folder.glob("*.pdf"))   # 只查找当前层
    
    if not pdf_files:
        print(f"⚠️  文件夹中没有找到 PDF 文件: {folder_path}")
        return
    
    print("="*80)
    print("📊 PDF-Extract-Kit - 批量处理模式")
    print("="*80)
    print(f"📁 文件夹: {folder_path}")
    print(f"🔍 递归模式: {'是' if recursive else '否'}")
    print(f"📄 找到 {len(pdf_files)} 个 PDF 文件")
    print("="*80)
    
    Config.print_config()
    
    # 统计信息
    total_count = len(pdf_files)
    success_count = 0
    skip_count = 0
    fail_count = 0
    total_charts = 0
    
    # 处理每个 PDF
    for idx, pdf_file in enumerate(pdf_files, 1):
        # 显示相对路径
        relative_path = pdf_file.relative_to(folder)
        
        print(f"\n{'='*80}")
        print(f"[{idx}/{total_count}] 处理: {relative_path}")
        print(f"{'='*80}")
        
        try:
            # 检查是否已处理过
            if skip_processed:
                processor_temp = PDFProcessor(str(pdf_file))
                if processor_temp.data_exporter.check_pdf_processed(pdf_file.name):
                    print(f"⏭️  跳过（已处理过）: {pdf_file.name}")
                    skip_count += 1
                    continue
            
            # 处理 PDF
            processor = PDFProcessor(str(pdf_file))
            result = processor.process()
            
            if result and result['success']:
                success_count += 1
                total_charts += len(result.get('charts', []))
                print(f"✅ 成功: {pdf_file.name}")
            else:
                fail_count += 1
                print(f"❌ 失败: {pdf_file.name}")
                
        except Exception as e:
            fail_count += 1
            print(f"❌ 异常: {pdf_file.name} - {e}")
    
    # 打印总结
    print(f"\n{'='*80}")
    print("📊 批量处理完成")
    print(f"{'='*80}")
    print(f"  总文件数: {total_count}")
    print(f"  成功: {success_count}")
    print(f"  跳过: {skip_count}")
    print(f"  失败: {fail_count}")
    print(f"  提取图表总数: {total_charts}")
    print(f"{'='*80}")


def process_oss_folder(oss_prefix: str, skip_processed: bool = True):
    """批量处理 OSS 中的所有 PDF - 边扫描边处理"""
    from modules import DataExporter
    
    print("="*80)
    print("📊 PDF-Extract-Kit - OSS 批量处理模式")
    print("="*80)
    print(f"📁 OSS 路径: {oss_prefix}")
    print(f"🔍 跳过已处理: {'是' if skip_processed else '否'}")
    print(f"💡 模式: 边扫描边处理（实时检查）")
    print("="*80)
    
    Config.print_config()
    
    try:
        downloader = OSSDownloader.from_env()
        exporter = DataExporter.from_env() if skip_processed else None
        
        print(f"\n🔍 开始扫描 OSS 文件...")
        print(f"   前缀: {oss_prefix or '(根目录)'}")
        
        # 统计信息
        total_count = 0
        success_count = 0
        skip_count = 0
        fail_count = 0
        total_charts = 0
        
        # 使用迭代器边扫描边处理
        import oss2
        for obj in oss2.ObjectIterator(downloader.bucket, prefix=oss_prefix):
            # 只处理 PDF 文件
            if not obj.key.endswith('.pdf'):
                continue
            
            total_count += 1
            oss_path = obj.key
            pdf_name = Path(oss_path).name
            
            print(f"\n{'='*80}")
            print(f"[{total_count}] 发现文件: {oss_path}")
            print(f"{'='*80}")
            
            try:
                # 实时检查是否已处理
                if skip_processed and exporter:
                    if exporter.check_pdf_processed(pdf_name):
                        print(f"⏭️  跳过（数据库中已存在）: {pdf_name}")
                        skip_count += 1
                        continue
                
                # 立即处理
                result = process_single_pdf(
                    f"oss://{oss_path}", 
                    cleanup_temp=True,
                    skip_processed=False  # 已经检查过了，不需要再检查
                )
                
                if result:
                    if result.get('skipped'):
                        skip_count += 1
                        print(f"⏭️  跳过: {pdf_name}")
                    elif result['success']:
                        success_count += 1
                        total_charts += len(result.get('charts', []))
                        print(f"✅ 成功: {pdf_name}")
                    else:
                        fail_count += 1
                        print(f"❌ 失败: {pdf_name}")
                else:
                    fail_count += 1
                    print(f"❌ 失败: {pdf_name}")
                    
            except Exception as e:
                fail_count += 1
                print(f"❌ 异常: {pdf_name} - {e}")
                import traceback
                traceback.print_exc()
        
        # 打印总结
        print(f"\n{'='*80}")
        print("📊 OSS 批量处理完成")
        print(f"{'='*80}")
        print(f"  总文件数: {total_count}")
        print(f"  成功: {success_count}")
        print(f"  跳过: {skip_count}")
        print(f"  失败: {fail_count}")
        print(f"  提取图表总数: {total_charts}")
        print(f"{'='*80}")
        
        if total_count == 0:
            print(f"\n⚠️  提示: OSS 路径 '{oss_prefix}' 中没有找到 PDF 文件")
            print(f"   请检查路径是否正确，或运行 'python check_oss_files.py' 查看可用文件")
        
    except Exception as e:
        print(f"❌ OSS 批量处理失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PDF Extract with AI Analysis')
    parser.add_argument('--pdf', help='PDF 文件路径（单个文件，支持 oss:// 前缀）')
    parser.add_argument('--folder', help='PDF 文件夹路径（批量处理本地文件）')
    parser.add_argument('--oss-folder', help='OSS 文件夹路径（批量处理 OSS 文件）')
    parser.add_argument('--no-skip', action='store_true', help='不跳过已处理的文件')
    parser.add_argument('--no-recursive', action='store_true', help='不递归子文件夹（仅处理当前层）')
    
    args = parser.parse_args()
    
    # 检查参数
    if not args.pdf and not args.folder and not args.oss_folder:
        parser.error("请指定 --pdf、--folder 或 --oss-folder 参数")
    
    # 单文件模式
    if args.pdf:
        skip_processed = not args.no_skip
        result = process_single_pdf(args.pdf, skip_processed=skip_processed)
        
        if result:
            if result.get('skipped'):
                print(f"\n⏭️  文件已跳过（数据库中已存在）")
            else:
                print(f"\n统计信息:")
                print(f"  图表数量: {len(result['charts'])}")
                print(f"  PDF 行业: {result['pdf_industry']}")
                print(f"  处理时间: {result['elapsed_time']:.2f}秒")
    
    # 本地批量模式
    elif args.folder:
        skip_processed = not args.no_skip
        recursive = not args.no_recursive
        process_folder(args.folder, skip_processed=skip_processed, recursive=recursive)
    
    # OSS 批量模式
    elif args.oss_folder:
        skip_processed = not args.no_skip
        process_oss_folder(args.oss_folder, skip_processed=skip_processed)


if __name__ == '__main__':
    main()
