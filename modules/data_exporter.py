"""
数据导出模块 - 只导出到 NocoDB
"""

import requests
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


class DataExporter:
    """数据导出器 - 只支持 NocoDB"""
    
    def __init__(
        self, 
        output_dir: str = None,
        nocodb_config: Optional[Dict[str, str]] = None
    ):
        """初始化导出器"""
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        
        # NocoDB 配置
        self.nocodb_config = nocodb_config or self._load_nocodb_config_from_env()
        self.nocodb_enabled = bool(self.nocodb_config and self.nocodb_config.get('api_url'))
        
        print(f"\n[DataExporter 初始化]")
        print(f"  nocodb_config: {self.nocodb_config is not None}")
        if self.nocodb_config:
            print(f"  api_url: {self.nocodb_config.get('api_url', 'N/A')}")
            print(f"  table_id: {self.nocodb_config.get('table_id', 'N/A')}")
        print(f"  nocodb_enabled: {self.nocodb_enabled}")
        
        if self.nocodb_enabled:
            print(f"✅ NocoDB 已配置: {self.nocodb_config['api_url']}")
        else:
            print(f"⚠️  NocoDB 未配置")
    
    def _load_nocodb_config_from_env(self) -> Optional[Dict[str, str]]:
        """从环境变量加载 NocoDB 配置"""
        if not os.getenv('NOCODB_API_URL'):
            return None
        
        return {
            'api_url': os.getenv('NOCODB_API_URL'),
            'api_token': os.getenv('NOCODB_API_TOKEN'),
            'table_id': os.getenv('NOCODB_TABLE_ID'),
            'base_id': os.getenv('NOCODB_BASE_ID', ''),
        }
    
    def check_pdf_processed(self, source_file: str) -> bool:
        """检查 PDF 是否已经处理过（查询数据库）"""
        if not self.nocodb_enabled:
            print(f"   ℹ️  NocoDB 未启用，无法检查处理状态")
            return False
        
        try:
            api_url = self.nocodb_config['api_url'].rstrip('/')
            api_token = self.nocodb_config['api_token']
            table_id = self.nocodb_config['table_id']
            
            endpoint = f"{api_url}/api/v2/tables/{table_id}/records"
            
            headers = {
                'xc-token': api_token,
                'Content-Type': 'application/json'
            }
            
            params = {
                'where': f'(source_file,eq,{source_file})',
                'limit': 1
            }
            
            print(f"   🔍 检查数据库: {source_file}")
            
            response = requests.get(
                endpoint,
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('list', []) or data.get('records', [])
                exists = len(records) > 0
                
                if exists:
                    print(f"   ✓ 数据库中已存在该文件的记录")
                else:
                    print(f"   ✓ 数据库中未找到该文件（可以处理）")
                
                return exists
            else:
                print(f"   ⚠️  数据库查询失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ⚠️  数据库检查异常: {e}")
            return False
    
    def acquire_processing_lock(self, source_file: str, timeout: int = 1800) -> bool:
        """
        获取处理锁（防止多进程重复处理）
        使用 NocoDB 作为分布式锁 + 双重检查机制
        
        Args:
            source_file: PDF 文件名
            timeout: 锁超时时间（秒），默认 30 分钟
        
        Returns:
            是否成功获取锁
        """
        if not self.nocodb_enabled:
            return True  # 如果没有数据库，默认允许处理
        
        try:
            from datetime import datetime, timedelta
            import time
            
            # 【双重检查 1】先检查是否已处理完成（正常记录）
            if self.check_pdf_processed(source_file):
                print(f"   ✓ 文件已处理完成（跳过）: {source_file}")
                return False
            
            # 【双重检查 2】尝试创建锁记录
            lock_key = f"__LOCK__{source_file}"
            current_time = datetime.now().isoformat()
            
            # 尝试插入锁记录
            success = self._try_insert_lock(lock_key, current_time, timeout)
            
            if not success:
                print(f"   � 文件正在被理其他进程处理: {source_file}")
                return False
            
            # 【双重检查 3】获取锁后再次检查是否已处理
            # 防止在获取锁的过程中，其他进程已经完成处理
            time.sleep(0.1)  # 短暂等待，确保数据库同步
            if self.check_pdf_processed(source_file):
                print(f"   ✓ 文件已被其他进程处理完成（释放锁）: {source_file}")
                # 释放刚获取的锁
                self.release_processing_lock(source_file)
                return False
            
            print(f"   🔓 成功获取处理锁: {source_file}")
            return True
            
        except Exception as e:
            print(f"   ⚠️  锁获取异常: {e}")
            # 异常时检查是否已处理，如果已处理就不允许，否则允许
            return not self.check_pdf_processed(source_file)
    
    def _try_insert_lock(self, lock_key: str, current_time: str, timeout: int) -> bool:
        """
        尝试插入锁记录（原子操作）
        
        Returns:
            是否成功获取锁
        """
        try:
            api_url = self.nocodb_config['api_url'].rstrip('/')
            api_token = self.nocodb_config['api_token']
            table_id = self.nocodb_config['table_id']
            
            # 1. 先查询是否已有锁记录
            endpoint = f"{api_url}/api/v2/tables/{table_id}/records"
            headers = {
                'xc-token': api_token,
                'Content-Type': 'application/json'
            }
            
            params = {
                'where': f'(source_file,eq,{lock_key})',
                'limit': 1
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('list', []) or data.get('records', [])
                
                if records:
                    # 已有锁记录，检查是否超时
                    lock_record = records[0]
                    lock_time_str = lock_record.get('analysis_time', '')
                    
                    if lock_time_str:
                        from datetime import datetime
                        try:
                            # 尝试解析时间
                            lock_time = datetime.fromisoformat(lock_time_str.replace('Z', '+00:00'))
                            current = datetime.now(lock_time.tzinfo) if lock_time.tzinfo else datetime.now()
                            
                            # 检查是否超时
                            if (current - lock_time).total_seconds() > timeout:
                                print(f"   ⏰ 锁已超时，删除旧锁")
                                # 删除超时的锁
                                self._delete_lock(lock_record.get('Id') or lock_record.get('id'))
                                # 继续尝试获取锁
                            else:
                                # 锁未超时，不能获取
                                return False
                        except:
                            # 时间解析失败，认为锁无效，删除
                            self._delete_lock(lock_record.get('Id') or lock_record.get('id'))
                    else:
                        # 没有时间戳，认为锁无效，删除
                        self._delete_lock(lock_record.get('Id') or lock_record.get('id'))
            
            # 2. 尝试插入新的锁记录
            lock_record = {
                'source_file': lock_key,
                'analysis_time': current_time,
                'chart_title': '__PROCESSING_LOCK__',
                'pdf_industry': 'LOCK'
            }
            
            response = requests.post(endpoint, headers=headers, json=[lock_record], timeout=10)
            
            if response.status_code in [200, 201]:
                return True
            else:
                # 插入失败，可能是其他进程抢先了
                return False
                
        except Exception as e:
            print(f"   ⚠️  锁操作异常: {e}")
            return False
    
    def _delete_lock(self, record_id):
        """删除锁记录"""
        try:
            if not record_id:
                return
            
            api_url = self.nocodb_config['api_url'].rstrip('/')
            api_token = self.nocodb_config['api_token']
            table_id = self.nocodb_config['table_id']
            
            endpoint = f"{api_url}/api/v2/tables/{table_id}/records"
            headers = {
                'xc-token': api_token,
                'Content-Type': 'application/json'
            }
            
            requests.delete(f"{endpoint}/{record_id}", headers=headers, timeout=10)
        except:
            pass
    
    def release_processing_lock(self, source_file: str):
        """
        释放处理锁
        
        Args:
            source_file: PDF 文件名
        """
        if not self.nocodb_enabled:
            return
        
        try:
            lock_key = f"__LOCK__{source_file}"
            
            api_url = self.nocodb_config['api_url'].rstrip('/')
            api_token = self.nocodb_config['api_token']
            table_id = self.nocodb_config['table_id']
            
            endpoint = f"{api_url}/api/v2/tables/{table_id}/records"
            headers = {
                'xc-token': api_token,
                'Content-Type': 'application/json'
            }
            
            # 查询锁记录
            params = {
                'where': f'(source_file,eq,{lock_key})',
                'limit': 1
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('list', []) or data.get('records', [])
                
                if records:
                    record_id = records[0].get('Id') or records[0].get('id')
                    self._delete_lock(record_id)
                    print(f"   🔓 释放处理锁: {source_file}")
        except Exception as e:
            print(f"   ⚠️  释放锁异常: {e}")
    
    def export_to_nocodb(
        self,
        images: List[Dict[str, Any]],
        source_file: str,
        timestamp: str = None,
        pdf_industry: str = "未知"
    ) -> Dict[str, Any]:
        """导出到 NocoDB"""
        print(f"\n📤 [调试] export_to_nocodb 被调用")
        print(f"   nocodb_enabled: {self.nocodb_enabled}")
        print(f"   images 数量: {len(images) if images else 0}")
        print(f"   source_file: {source_file}")
        
        if not self.nocodb_enabled:
            print("⚠️  NocoDB 未配置，跳过导入")
            return {'success': False, 'message': 'NocoDB 未配置'}
        
        if not images:
            print("⚠️  没有图片需要导入到 NocoDB")
            return {'success': True, 'inserted_count': 0, 'message': '没有图片需要导入'}
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"\n📤 开始导入到 NocoDB...")
        
        # 准备数据
        records = []
        for img in images:
            # 调试：检查原始数据
            analysis_value = img.get('analysis_cleaned', '')
            print(f"  调试：准备记录 {img.get('image_filename', 'unknown')}")
            print(f"        analysis_cleaned 长度: {len(analysis_value)}")
            if not analysis_value:
                print(f"        ⚠️  警告：analysis_cleaned 为空！")
                print(f"        可用字段: {list(img.keys())}")
            
            record = {
                'source_file': source_file,
                'analysis_time': timestamp,
                'pdf_industry': pdf_industry,
                'chart_industry': img.get('chart_industry', pdf_industry or '其它'),
                'content_category': img.get('content_category', ''),
                'category_confidence': img.get('category_confidence', 0.0),
                'page_num': img['page_num'],
                'image_index': img['image_index'],
                'image_size': img.get('image_size', ''),
                'image_width': img.get('image_width', 0),
                'image_height': img.get('image_height', 0),
                'image_format': img.get('image_format', 'png'),
                'image_filename': img.get('image_filename', ''),
                'image_url': img.get('image_url', ''),
                'image_relative_path': img.get('image_relative_path', ''),
                'chart_title': img.get('chart_title', ''),
                'analysis_cleaned': analysis_value,  # 修改字段名匹配数据库
                'analysis_length': len(analysis_value),
                'data_source': img.get('data_source', ''),
                'keywords': img.get('keywords', ''),
            }
            
            # 调试：检查 record
            print(f"        record['analysis'] 长度: {len(record['analysis'])}")
            
            records.append(record)
        
        # 批量导入
        try:
            result = self._batch_insert_to_nocodb(records)
            
            if result['success']:
                print(f"✅ 成功导入 {result['inserted_count']} 条记录到 NocoDB")
            else:
                print(f"❌ NocoDB 导入失败: {result['message']}")
            
            return result
            
        except Exception as e:
            print(f"❌ NocoDB 导入异常: {e}")
            return {'success': False, 'message': str(e)}
    
    def _batch_insert_to_nocodb(
        self,
        records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量插入记录到 NocoDB"""
        api_url = self.nocodb_config['api_url'].rstrip('/')
        api_token = self.nocodb_config['api_token']
        table_id = self.nocodb_config['table_id']
        
        endpoint = f"{api_url}/api/v2/tables/{table_id}/records"
        
        headers = {
            'xc-token': api_token,
            'Content-Type': 'application/json'
        }
        
        inserted_count = 0
        failed_count = 0
        
        # 批量插入（每次最多 100 条）
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            # 调试：打印第一条记录的 analysis 字段
            if i == 0 and batch:
                first_record = batch[0]
                print(f"  调试：第一条记录")
                print(f"        文件名: {first_record.get('image_filename', 'unknown')}")
                print(f"        analysis 长度: {len(first_record.get('analysis', ''))}")
                print(f"        analysis 预览: {first_record.get('analysis', '')[:100]}...")
            
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=batch,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    inserted_count += len(batch)
                    print(f"  [{i + len(batch)}/{len(records)}] 已导入")
                else:
                    print(f"  ⚠️  批次 {i//batch_size + 1} 失败: {response.status_code}")
                    failed_count += len(batch)
                    
            except Exception as e:
                print(f"  ❌ 批次 {i//batch_size + 1} 异常: {e}")
                failed_count += len(batch)
        
        return {
            'success': inserted_count > 0,
            'inserted_count': inserted_count,
            'failed_count': failed_count,
            'total': len(records),
            'message': f'成功 {inserted_count}/{len(records)}'
        }
    
    @staticmethod
    def from_env(output_dir: str = None):
        """从环境变量创建导出器"""
        return DataExporter(
            output_dir=output_dir,
            nocodb_config=None
        )
