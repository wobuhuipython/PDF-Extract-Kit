"""
从 NocoDB 批量处理 PDF
从数据库的 oss_url 字段获取 PDF 链接并处理
"""

import sys
import argparse
from pathlib import Path
from modules import NocoDBPDFFetcher, PDFProcessor, DataExporter


def process_nocodb_pdfs(
    oss_url_field: str = 'oss_url',
    status_field: str = 'status',
    pending_status: str = 'pending',
    processing_status: str = 'processing',
    completed_status: str = 'completed',
    failed_status: str = 'failed',
    limit: int = 100,
    cleanup_temp: bool = True
):
    """
    从 NocoDB 批量处理 PDF
    
    Args:
        oss_url_field: OSS URL 字段名
        status_field: 状态字段名
        pending_status: 待处理状态
        processing_status: 处理中状态
        completed_status: 完成状态
        failed_status: 失败状态
        limit: 每次处理的最大数量
        cleanup_temp: 是否清理临时文件
    """
    print("="*80)
    print("📊 NocoDB PDF 批量处理")
    print("="*80)
    print(f"📋 配置:")
    print(f"   OSS URL 字段: {oss_url_field}")
    print(f"   状态字段: {status_field}")
    print(f"   待处理状态: {pending_status}")
    print(f"   处理限制: {limit} 条")
    print("="*80)
    
    try:
        # 初始化
        fetcher = NocoDBPDFFetcher.from_env()
        exporter = DataExporter.from_env()
        
        # 获取未处理的 PDF 记录
        print(f"\n🔍 查询未处理的 PDF...")
        records = fetcher.get_unprocessed_pdfs(
            oss_url_field=oss_url_field,
            status_field=status_field,
            pending_status=pending_status,
            limit=limit
        )
        
        if not records:
            print(f"✅ 没有待处理的 PDF")
            return
        
        print(f"📋 找到 {len(records)} 条待处理记录")
        
        # 统计信息
        total_count = len(records)
        success_count = 0
        fail_count = 0
        skip_count = 0
        total_charts = 0
        
        # 处理每条记录
        for idx, record in enumerate(records, 1):
            record_id = record.get('Id') or record.get('id')
            pdf_url = record.get(oss_url_field)
            pdf_name = record.get('pdf_name') or record.get('name') or f"pdf_{record_id}.pdf"
            
            print(f"\n{'='*80}")
            print(f"[{idx}/{total_count}] 处理记录 ID: {record_id}")
            print(f"{'='*80}")
            print(f"📄 PDF 名称: {pdf_name}")
            print(f"🔗 PDF URL: {pdf_url}")
            
            try:
                # 更新状态为"处理中"
                fetcher.update_record_status(
                    record_id,
                    processing_status,
                    status_field
                )
                
                # 下载 PDF
                local_pdf_path = fetcher.download_pdf_from_url(pdf_url, pdf_name)
                
                if not local_pdf_path:
                    print(f"❌ 下载失败，跳过")
                    fetcher.update_record_status(record_id, failed_status, status_field)
                    fail_count += 1
                    continue
                
                # 检查是否已处理过
                if exporter.check_pdf_processed(pdf_name):
                    print(f"⏭️  PDF 已处理过，跳过")
                    fetcher.update_record_status(record_id, completed_status, status_field)
                    skip_count += 1
                    
                    # 清理临时文件
                    if cleanup_temp and Path(local_pdf_path).exists():
                        Path(local_pdf_path).unlink()
                    
                    continue
                
                # 处理 PDF
                processor = PDFProcessor(local_pdf_path, original_name=pdf_name)
                result = processor.process()
                
                if result and result['success']:
                    success_count += 1
                    total_charts += len(result.get('charts', []))
                    print(f"✅ 处理成功: {pdf_name}")
                    print(f"   提取图表: {len(result.get('charts', []))} 个")
                    
                    # 更新状态为"完成"
                    fetcher.update_record_status(record_id, completed_status, status_field)
                else:
                    fail_count += 1
                    print(f"❌ 处理失败: {pdf_name}")
                    
                    # 更新状态为"失败"
                    fetcher.update_record_status(record_id, failed_status, status_field)
                
                # 清理临时文件
                if cleanup_temp and Path(local_pdf_path).exists():
                    Path(local_pdf_path).unlink()
                    print(f"🗑️  已清理临时文件")
                    
            except Exception as e:
                fail_count += 1
                print(f"❌ 处理异常: {e}")
                import traceback
                traceback.print_exc()
                
                # 更新状态为"失败"
                try:
                    fetcher.update_record_status(record_id, failed_status, status_field)
                except:
                    pass
        
        # 打印总结
        print(f"\n{'='*80}")
        print("📊 批量处理完成")
        print(f"{'='*80}")
        print(f"  总记录数: {total_count}")
        print(f"  成功: {success_count}")
        print(f"  跳过: {skip_count}")
        print(f"  失败: {fail_count}")
        print(f"  提取图表总数: {total_charts}")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"❌ 批量处理失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='从 NocoDB 批量处理 PDF')
    parser.add_argument('--oss-url-field', default='oss_url', help='OSS_URL字段名')
    parser.add_argument('--status-field', default='status', help='状态字段名')
    parser.add_argument('--pending-status', default='pending', help='待处理状态值')
    parser.add_argument('--processing-status', default='processing', help='处理中状态值')
    parser.add_argument('--completed-status', default='completed', help='完成状态值')
    parser.add_argument('--failed-status', default='failed', help='失败状态值')
    parser.add_argument('--limit', type=int, default=100, help='每次处理的最大数量')
    parser.add_argument('--no-cleanup', action='store_true', help='不清理临时文件')
    
    args = parser.parse_args()
    
    process_nocodb_pdfs(
        oss_url_field=args.oss_url_field,
        status_field=args.status_field,
        pending_status=args.pending_status,
        processing_status=args.processing_status,
        completed_status=args.completed_status,
        failed_status=args.failed_status,
        limit=args.limit,
        cleanup_temp=not args.no_cleanup
    )


if __name__ == '__main__':
    main()
