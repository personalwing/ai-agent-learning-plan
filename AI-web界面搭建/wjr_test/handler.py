# -*- coding: utf-8 -*-
import json
import requests
import time
import re
from datetime import datetime

# MySQL连接配置（通过 <SQL_PROXY_HOST> 上的 SQL 代理服务）
SQL_PROXY_URL = 'http://<SQL_PROXY_HOST>:5001/query'

# 默认请求头（根据接口文档固定）
DEFAULT_HEADERS = {
    "X-Auth-Project-Id": "<PROJECT_ID>",
    "X-Auth-Token": "<AUTH_TOKEN>",
    "X-KSC-APPLICATION-TOKEN": "<APPLICATION_TOKEN>",
    "X-KSC-APPLICATION-NAME": "ktrove",
    "User-Agent": "python-memdbclient",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# 固定接口文档（从MongoDB+Openstack+HTTP+API.docx解析）
FIXED_APIS = [
    # ==================== 公共接口 ====================
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{mongodb_uuid}/action", "method": "POST", "category": "公共接口", "name": "查询新旧系统注册id映射", "description": "通过任意实例id查询旧监控系统注册id对应的新系统注册id"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{mongo_id_eip}/action", "method": "POST", "category": "公共接口", "name": "申请EIP", "description": "为MongoDB资源申请弹性公网IP"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/get_instance_list", "method": "POST", "category": "公共接口", "name": "获取实例列表(通用)", "description": "根据type和mode获取实例列表，mode不传则返回全部"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource", "method": "GET", "category": "公共接口", "name": "获取实例列表(index)", "description": "获取所有未删除实例列表"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{mongo_id_rename}/action", "method": "POST", "category": "公共接口", "name": "修改实例名称", "description": "修改MongoDB实例的名称"},
    {"path": "/v1.0/{tenant_id}/backup-resources", "method": "POST", "category": "公共接口", "name": "手动发起物理备份", "description": "手动发起自动物理备份"},
    {"path": "/v1.0/{tenant_id}/backup-records/{record_id}", "method": "DELETE", "category": "公共接口", "name": "删除备份记录", "description": "根据备份记录ID删除指定备份"},
    
    # ==================== 副本集接口 ====================
    {"path": "/v1.0/{tenant_id}/mongodb-repset", "method": "GET", "category": "副本集接口", "name": "获取副本集列表(index)", "description": "获取所有未删除的副本集实例列表"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{repset_id}/action", "method": "POST", "category": "副本集接口", "name": "查看可恢复时间点", "description": "查看副本集实例可恢复时间点"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset", "method": "POST", "category": "副本集接口", "name": "创建副本集实例", "description": "创建MongoDB副本集实例"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id_eip}/action", "method": "POST", "category": "副本集接口", "name": "副本集申请EIP", "description": "为副本集实例申请弹性公网IP"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}", "method": "GET", "category": "副本集接口", "name": "获取副本集详情(show)", "description": "获取指定ID的副本集实例详情"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}/action", "method": "POST", "category": "副本集接口", "name": "解锁副本集实例", "description": "解锁被锁定的副本集实例"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id_eip02}/action", "method": "POST", "category": "副本集接口", "name": "副本集释放EIP", "description": "释放副本集实例的弹性公网IP"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}/action", "method": "POST", "category": "副本集接口", "name": "锁定副本集实例", "description": "锁定副本集实例防止操作"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}", "method": "GET", "category": "副本集接口", "name": "迁移副本-获取详情", "description": "迁移副本时获取副本集实例详情"},
    {"path": "/v1.0/{tenant_id}/backup-resources/{cluster_id}/list_backup_records", "method": "GET", "category": "副本集接口", "name": "查询副本集备份列表", "description": "查询副本集实例的备份记录列表"},
    
    # ==================== 分片集群接口 ====================
    {"path": "/v1.0/{tenant_id}/mongodb-cluster", "method": "GET", "category": "分片集群接口", "name": "获取分片集群列表(index)", "description": "获取所有未删除的分片集群实例列表"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}/action", "method": "POST", "category": "分片集群接口", "name": "分片集群添加Shard", "description": "为分片集群添加新的Shard分片"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id_shard}/action", "method": "POST", "category": "分片集群接口", "name": "获取分片列表(list_shards)", "description": "获取指定分片集群下的所有分片列表"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id_eip}/action", "method": "POST", "category": "分片集群接口", "name": "分片集群申请EIP", "description": "为分片集群实例申请弹性公网IP"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}", "method": "GET", "category": "分片集群接口", "name": "获取分片集群详情(show)", "description": "获取指定ID的分片集群实例详情"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}/action", "method": "POST", "category": "分片集群接口", "name": "解锁分片集群实例", "description": "解锁被锁定的分片集群实例"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id_eip02}/action", "method": "POST", "category": "分片集群接口", "name": "分片集群释放EIP", "description": "释放分片集群实例的弹性公网IP"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}/action", "method": "POST", "category": "分片集群接口", "name": "锁定分片集群实例", "description": "锁定分片集群实例防止操作"},
    {"path": "/v1.0/{tenant_id}/backup-resources/{cluster_id}/list_cluster_backup_records", "method": "GET", "category": "分片集群接口", "name": "查询分片集群备份列表", "description": "查询分片集群实例的备份记录列表"},
]

# ktrove 后端实测可用的 MongoDB 路由表（对 KSCC 服务地址探测确认）
# 这些是 /wjr-test 扫描栏应展示的真实接口，替代原先探测不存在网关路径后回退的假数据。
SCANNED_APIS = [
    # ==================== 副本集 repset ====================
    {"path": "/v1.0/{tenant_id}/mongodb-repset", "method": "GET", "category": "副本集", "name": "副本集列表", "description": "获取所有未删除副本集实例列表，分页用 offset/limit"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset", "method": "POST", "category": "副本集", "name": "创建副本集", "description": "创建 MongoDB 副本集实例，选中后 body 自动填充必传字段", "body_template": "{\"mongodb_repset\": {\"admin_user\": \"root\", \"disk_size\": 25, \"name\": \"wjrdev32\", \"area\": [\"1\"], \"vcpu\": 2, \"mem_size\": 4, \"node_num\": 3, \"vpc\": {\"vpc_id\": \"<VPC_ID>\", \"vnet_id\": \"<VNET_ID>\"}, \"protocol\": \"memcached\", \"datastore\": {\"version\": \"3.2\"}, \"join_shard\": false, \"admin_password\": \"<ADMIN_PASSWORD>\"}}"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}", "method": "GET", "category": "副本集", "name": "副本集详情", "description": "获取指定副本集实例详情"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}", "method": "DELETE", "category": "副本集", "name": "删除副本集", "description": "删除指定副本集实例"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}/action", "method": "POST", "category": "副本集", "name": "副本集动作", "description": "lock/unlock/rename/restart/resize/add_user 等 action，选中后 body 自动填充", "actions": [
        {"key": "lock", "body": "{\"lock\": {}}"},
        {"key": "unlock", "body": "{\"unlock\": {}}"},
        {"key": "rename", "body": "{\"rename\": {\"name\": \"new_name\"}}"},
        {"key": "restart", "body": "{\"restart\": {}}"},
        {"key": "resize", "body": "{\"resize\": {\"flavor_id\": \"\", \"volume_size\": 0}}"},
        {"key": "add_user", "body": "{\"add_user\": {\"user\": \"\", \"password\": \"\", \"roles\": []}}"},
        {"key": "reset_state", "body": "{\"reset_state\": {}}"},
        {"key": "allocate_eip", "body": "{\"allocate_eip\": {\"band_width\": 1, \"ip_version\": 4}}"},
        {"key": "deallocate_eip", "body": "{\"deallocate_eip\": {}}"},
        {"key": "enable_ssl", "body": "{\"enable_ssl\": {\"ssl_version\": \"TLSv1.2\"}}"},
        {"key": "disable_ssl", "body": "{\"disable_ssl\": {}}"},
        {"key": "aggregate_monitor", "body": "{\"aggregate_monitor\": {\"target\": \"all\"}}"}
    ]},

    # ==================== 分片集群 cluster ====================
    {"path": "/v1.0/{tenant_id}/mongodb-cluster", "method": "GET", "category": "分片集群", "name": "集群列表", "description": "获取所有未删除分片集群实例列表，分页用 offset/limit"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster", "method": "POST", "category": "分片集群", "name": "创建集群", "description": "创建 MongoDB 分片集群实例，选中后 body 自动填充必传字段", "body_template": "{\"mongodb_cluster\": {\"admin_user\": \"root\", \"protocol\": \"memcached\", \"name\": \"wjrdev80\", \"shards\": {\"vcpu\": 2, \"mem_size\": 4, \"shards_num\": 2, \"disk_size\": 15, \"area\": [\"1\"]}, \"config_server\": {\"vcpu\": 2, \"mem_size\": 4, \"disk_size\": 40}, \"mongos\": {\"vcpu\": 2, \"mem_size\": 4, \"mongos_num\": 2, \"disk_size\": 15, \"area\": [\"2\"]}, \"vpc\": {\"vpc_id\": \"<VPC_ID>\", \"vnet_id\": \"<VNET_ID>\"}, \"datastore\": {\"version\": \"8.0\"}, \"join_shard\": false, \"admin_password\": \"<ADMIN_PASSWORD>\"}}"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}", "method": "GET", "category": "分片集群", "name": "集群详情", "description": "获取指定分片集群实例详情"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}", "method": "DELETE", "category": "分片集群", "name": "删除集群", "description": "删除指定分片集群实例"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}/action", "method": "POST", "category": "分片集群", "name": "集群动作", "description": "list_shards/add_shard/lock/unlock 等 action，选中后 body 自动填充", "actions": [
        {"key": "lock", "body": "{\"lock\": {}}"},
        {"key": "unlock", "body": "{\"unlock\": {}}"},
        {"key": "rename", "body": "{\"rename\": {\"name\": \"new_name\"}}"},
        {"key": "restart", "body": "{\"restart\": {}}"},
        {"key": "resize", "body": "{\"resize\": {\"flavor_id\": \"\", \"volume_size\": 0}}"},
        {"key": "add_user", "body": "{\"add_user\": {\"user\": \"\", \"password\": \"\", \"roles\": []}}"},
        {"key": "add_shard", "body": "{\"add_shard\": {\"name\": \"\", \"node_num\": 3, \"volume_size\": 25}}"},
        {"key": "list_shards", "body": "{\"list_shards\": {}}"},
        {"key": "list_shard_instances", "body": "{\"list_shard_instances\": {}}"},
        {"key": "add_mongos", "body": "{\"add_mongos\": {\"node_num\": 1}}"},
        {"key": "remove_mongos", "body": "{\"remove_mongos\": {\"instance_id\": \"\"}}"},
        {"key": "allocate_eip", "body": "{\"allocate_eip\": {\"band_width\": 1, \"ip_version\": 4}}"},
        {"key": "deallocate_eip", "body": "{\"deallocate_eip\": {}}"},
        {"key": "enable_ssl", "body": "{\"enable_ssl\": {\"ssl_version\": \"TLSv1.2\"}}"},
        {"key": "aggregate_monitor", "body": "{\"aggregate_monitor\": {\"target\": \"all\"}}"}
    ]},

    # ==================== 通用资源 resource ====================
    {"path": "/v1.0/{tenant_id}/mongodb-resource", "method": "GET", "category": "通用", "name": "资源列表", "description": "获取所有未删除 MongoDB 资源(repset+cluster)列表，分页用 offset/limit"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource", "method": "POST", "category": "通用", "name": "创建资源", "description": "创建 MongoDB 资源(按 type/mode 指定副本集或集群)，选中后 body 自动填充", "body_template": "{\"mongodb_repset\": {\"admin_user\": \"root\", \"disk_size\": 25, \"name\": \"wjrdev32\", \"area\": [\"1\"], \"vcpu\": 2, \"mem_size\": 4, \"node_num\": 3, \"vpc\": {\"vpc_id\": \"<VPC_ID>\", \"vnet_id\": \"<VNET_ID>\"}, \"protocol\": \"memcached\", \"datastore\": {\"version\": \"3.2\"}, \"join_shard\": false, \"admin_password\": \"<ADMIN_PASSWORD>\"}}"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{cluster_id}", "method": "GET", "category": "通用", "name": "资源详情", "description": "获取指定 MongoDB 资源详情"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{cluster_id}", "method": "DELETE", "category": "通用", "name": "删除资源", "description": "删除指定 MongoDB 资源"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{cluster_id}/action", "method": "POST", "category": "通用", "name": "资源动作", "description": "lock/unlock/rename/restart/resize 等 action，选中后 body 自动填充", "actions": [
        {"key": "lock", "body": "{\"lock\": {}}"},
        {"key": "unlock", "body": "{\"unlock\": {}}"},
        {"key": "rename", "body": "{\"rename\": {\"name\": \"new_name\"}}"},
        {"key": "restart", "body": "{\"restart\": {}}"},
        {"key": "resize", "body": "{\"resize\": {\"flavor_id\": \"\", \"volume_size\": 0}}"},
        {"key": "add_user", "body": "{\"add_user\": {\"user\": \"\", \"password\": \"\", \"roles\": []}}"},
        {"key": "reset_state", "body": "{\"reset_state\": {}}"},
        {"key": "allocate_eip", "body": "{\"allocate_eip\": {\"band_width\": 1, \"ip_version\": 4}}"},
        {"key": "deallocate_eip", "body": "{\"deallocate_eip\": {}}"},
        {"key": "enable_ssl", "body": "{\"enable_ssl\": {\"ssl_version\": \"TLSv1.2\"}}"},
        {"key": "aggregate_monitor", "body": "{\"aggregate_monitor\": {\"target\": \"all\"}}"}
    ]},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/get_instance_list", "method": "POST", "category": "通用", "name": "通用实例列表", "description": "按 type=mongodb & mode=repset/cluster 查询实例列表，选中后 body 自动填充", "body_template": "{\"type\": \"mongodb\", \"mode\": \"repset\", \"limit\": 10, \"offset\": 0}"},

    # ==================== 公共：统计/数据源/备份 ====================
    {"path": "/v1.0/{tenant_id}/statistic", "method": "GET", "category": "公共", "name": "资产统计", "description": "按 db_type=mongodb 统计实例总数/运行/异常及健康分布"},
    {"path": "/v1.0/{tenant_id}/datasource", "method": "GET", "category": "公共", "name": "数据源列表", "description": "按 db_type=mongodb 查询数据源列表"},
    {"path": "/v1.0/{tenant_id}/datasource/{instance_id}/sync_instance", "method": "POST", "category": "公共", "name": "同步数据源", "description": "触发指定实例数据源同步(健康检测)，body 可空", "body_template": "{}"},
    {"path": "/v1.0/{tenant_id}/backup-resources", "method": "POST", "category": "公共", "name": "发起备份", "description": "手动发起 MongoDB 物理备份，选中后 body 自动填充", "body_template": "{\"backup_resource\": {\"cluster_id\": \"\", \"mode\": \"repset\", \"reserve_days\": 7}}"},
    {"path": "/v1.0/{tenant_id}/backup-resources/{cluster_id}/list_backup_records", "method": "GET", "category": "公共", "name": "副本集备份列表", "description": "查询副本集实例备份记录列表"},
    {"path": "/v1.0/{tenant_id}/backup-resources/{cluster_id}/list_cluster_backup_records", "method": "GET", "category": "公共", "name": "集群备份列表", "description": "查询分片集群实例备份记录列表"},
    {"path": "/v1.0/{tenant_id}/backup-records/{record_id}", "method": "DELETE", "category": "公共", "name": "删除备份记录", "description": "按备份记录 ID 删除指定备份"},
]

class WJRTestHandler:
    """WJR测试处理器 - 处理Ktrove API测试请求"""

    @staticmethod
    def _convert_page_to_offset(params):
        """将分页参数 page 转换为后端认的 offset。

        ktrove mongodb 列表接口的分页约定是 offset/limit（offset 从 0 开始），
        不认 page。前端若传 page=N，按 offset=(N-1)*limit 转换；
        未传 limit 时默认按 10 条/页计算。支持 dict 和 'k=v&k=v' 字符串两种形式。
        """
        if not params:
            return params
        # 字符串形式 -> dict
        if isinstance(params, str):
            parts = [p for p in params.lstrip('?').split('&') if p]
            d = {}
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    d[k] = v
                else:
                    d[p] = ''
            params = d
        if not isinstance(params, dict):
            return params
        params = dict(params)  # 浅拷贝，不改调用方传入的对象
        if 'page' in params and 'offset' not in params:
            try:
                page = int(params.pop('page'))
                limit = int(params.get('limit', 10))
                params['offset'] = max(0, (page - 1) * limit)
            except (ValueError, TypeError):
                params.pop('page', None)
        else:
            params.pop('page', None)  # 有 offset 或 page 非法时，丢弃 page 避免 500
        return params

    def __init__(self):
        # 直连 ktrove-api 后端（<SQL_PROXY_HOST> 宿主 9777 端口），不再经 <APP_HOST>:8888 的 /api/ktrove 代理
        # （该代理路由在 app.py 中并不存在，会导致请求打回自己/404 并最终超时）
        self.kscc_base_url = "http://<KSCC_HOST>:9777"
        self.ktrove_proxy_path = ""
        self.scanner = APIScanner()
        self.runner = TestRunner()
        self.analyzer = AIAnalyzer()
    
    def handle_discover(self):
        """处理API发现请求 - 返回固定接口 + KSCC扫描接口"""
        try:
            scanned_apis = self.scanner.scan_mongodb_products(self.kscc_base_url)
            ktrove_apis = self.scanner.scan_ktrove_service(
                self.kscc_base_url + self.ktrove_proxy_path
            )
            
            all_scanned = scanned_apis + ktrove_apis
            scanned_integrated = self.analyzer.integrate_apis([], all_scanned)
            
            fixed_with_analysis = []
            for api in FIXED_APIS:
                api_copy = api.copy()
                api_copy['source'] = 'fixed_doc'
                api_copy['ai_analysis'] = self.analyzer._analyze_api(api)
                fixed_with_analysis.append(api_copy)
            
            return {
                'success': True,
                'data': {
                    'fixed_apis': fixed_with_analysis,
                    'scanned_apis': scanned_integrated,
                    'fixed_count': len(fixed_with_analysis),
                    'scanned_count': len(scanned_integrated),
                    'scan_time': datetime.now().isoformat()
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def handle_test(self, data):
        """处理单个API测试 - 使用固定默认Headers，增加超时和重试"""
        try:
            api_path = data.get('path', '')
            method = data.get('method', 'GET')
            user_headers = data.get('headers', {})
            headers = DEFAULT_HEADERS.copy()
            headers.update(user_headers)
            
            params = data.get('params', {})
            body = data.get('body', {})

            tenant_id = data.get('tenant_id', '092019a81f644fa0a6643153f25a8d3d')
            api_path = api_path.replace('{tenant_id}', tenant_id)

            # page -> offset 转换，避免后端对未知参数 page 报 500
            params = self._convert_page_to_offset(params)

            target_url = self.kscc_base_url + self.ktrove_proxy_path + api_path
            
            start_time = time.time()
            
            # 增加超时时间到120秒，添加重试
            max_retries = 2
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    response = requests.request(
                        method=method,
                        url=target_url,
                        headers=headers,
                        params=params,
                        json=body if body else None,
                        timeout=120
                    )
                    elapsed = time.time() - start_time
                    
                    analysis = self.analyzer.analyze_response(response, api_path, method)
                    
                    return {
                        'success': True,
                        'data': {
                            'status_code': response.status_code,
                            'headers': dict(response.headers),
                            'body': response.json() if response.text else {},
                            'elapsed': round(elapsed, 2),
                            'analysis': analysis,
                            'request_headers': headers,
                            'target_url': target_url,
                            'retry_count': attempt
                        }
                    }
                except requests.exceptions.Timeout as e:
                    last_error = "请求超时(120秒)，请检查目标服务是否正常"
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                except requests.exceptions.ConnectionError as e:
                    last_error = "连接失败: " + str(e)
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
            
            return {
                'success': False,
                'error': last_error or "请求失败，已重试 " + str(max_retries) + " 次"
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def handle_run_tests(self, data):
        """处理批量测试运行"""
        try:
            test_cases = data.get('test_cases', [])
            parallel = data.get('parallel', False)
            
            results = self.runner.run_test_suite(
                test_cases,
                self.kscc_base_url,
                self.ktrove_proxy_path
            )
            
            summary = self.analyzer.analyze_test_results(results)
            
            return {
                'success': True,
                'data': {
                    'results': results,
                    'summary': summary,
                    'total_tests': len(results),
                    'passed': sum(1 for r in results if r.get('passed')),
                    'failed': sum(1 for r in results if not r.get('passed'))
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def handle_fixed_apis(self):
        """获取固定接口列表 - 改为从MySQL查询"""
        return self.execute_sql_query("SELECT * FROM api_endpoints WHERE is_fixed=1 AND is_active=1 ORDER BY category, name")

    def handle_execute_sql(self, data):
        """执行SQL查询"""
        sql = data.get('sql', '').strip()
        if not sql:
            return {'success': False, 'error': 'SQL不能为空'}

        # 只允许 SELECT / SHOW / DESCRIBE 语句（安全限制）
        sql_upper = sql.upper()
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('SHOW') or sql_upper.startswith('DESCRIBE')):
            return {'success': False, 'error': '仅支持 SELECT / SHOW / DESCRIBE 查询'}

        return self.execute_sql_query(sql)

    def execute_sql_query(self, sql):
        """执行SQL - 通过 <SQL_PROXY_HOST> 上的 SQL 代理服务"""
        try:
            import json
            headers = {'Content-Type': 'application/json'}
            payload = json.dumps({'sql': sql})
            response = requests.post(
                SQL_PROXY_URL,
                data=payload,
                headers=headers,
                timeout=30
            )
            # Python 2 兼容：手动解析JSON
            return json.loads(response.text)
        except requests.exceptions.ConnectionError as e:
            return {'success': False, 'error': '无法连接到 SQL 代理服务 (<SQL_PROXY_HOST>:5001)，请确认服务已启动: ' + str(e)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_products(self):
        """获取产品列表"""
        try:
            products = self.scanner.list_mongodb_products(self.kscc_base_url)
            return {'success': True, 'data': products}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class APIScanner:
    """API扫描器 - 返回 ktrove 后端实测可用的 MongoDB 路由表。

    原实现探测 /api/mongodb/products、/endpoints、/swagger 等网关路径，
    这些路径在 8888 网关上不存在，全部失败后回退与 ktrove 无关的假数据。
    现直接返回对 <SQL_PROXY_HOST>:9777 后端实测确认的真实路由表（SCANNED_APIS）。
    """

    def scan_mongodb_products(self, kscc_url):
        return list(SCANNED_APIS)
    
    def _scan_product(self, kscc_url, product):
        return list(SCANNED_APIS)
    
    def _get_mock_apis(self):
        return list(SCANNED_APIS)
    
    def scan_ktrove_service(self, ktrove_url):
        return list(SCANNED_APIS)
    
    def list_mongodb_products(self, kscc_url):
        return [
            {'id': 'mongodb-repset', 'name': '副本集(repset)'},
            {'id': 'mongodb-cluster', 'name': '分片集群(cluster)'},
            {'id': 'mongodb-resource', 'name': '通用资源(resource)'},
        ]


class TestRunner:
    """测试执行器"""
    
    def run_test_suite(self, test_cases, kscc_url, proxy_path):
        results = []
        for test_case in test_cases:
            result = self._run_single_test(test_case, kscc_url, proxy_path)
            results.append(result)
        return results
    
    def _run_single_test(self, test_case, kscc_url, proxy_path):
        method = test_case.get('method', 'GET')
        path = test_case.get('path', '')
        headers = DEFAULT_HEADERS.copy()
        user_headers = test_case.get('headers', {})
        headers.update(user_headers)
        params = test_case.get('params', {})
        body = test_case.get('body', {})
        expected_status = test_case.get('expected_status', 200)

        tenant_id = test_case.get('tenant_id', '092019a81f644fa0a6643153f25a8d3d')
        path = path.replace('{tenant_id}', tenant_id)

        # page -> offset 转换，避免后端对未知参数 page 报 500
        params = WJRTestHandler._convert_page_to_offset(params)

        target_url = kscc_url + proxy_path + path
        
        try:
            start_time = time.time()
            response = requests.request(
                method=method,
                url=target_url,
                headers=headers,
                params=params,
                json=body if body else None,
                timeout=120
            )
            elapsed = time.time() - start_time
            
            passed = response.status_code == expected_status
            
            return {
                'test_case': test_case,
                'passed': passed,
                'status_code': response.status_code,
                'response': response.text[:500] if response.text else '',
                'elapsed': round(elapsed, 2),
                'errors': [] if passed else ["status code: " + str(response.status_code)]
            }
        except Exception as e:
            return {
                'test_case': test_case,
                'passed': False,
                'error': str(e)
            }


class AIAnalyzer:
    """AI分析器"""
    
    def integrate_apis(self, mongo_apis, ktrove_apis):
        integrated = []
        seen = set()
        all_apis = mongo_apis + ktrove_apis
        
        for api in all_apis:
            key = api.get('method', 'GET') + "|" + api.get('path', '')
            if key not in seen:
                seen.add(key)
                if 'ai_analysis' not in api:
                    api['ai_analysis'] = self._analyze_api(api)
                integrated.append(api)
        
        return integrated
    
    def _analyze_api(self, api):
        analysis = {
            'risk_level': 'low',
            'complexity': 'simple',
            'suggestions': [],
            'auto_tests': []
        }
        
        path = api.get('path', '')
        method = api.get('method', 'GET')
        
        if 'delete' in path.lower():
            analysis['risk_level'] = 'high'
            analysis['suggestions'].append('⚠️ 删除操作请谨慎')
        elif 'update' in path.lower() or 'modify' in path.lower():
            analysis['risk_level'] = 'medium'
            analysis['suggestions'].append('📝 建议先查询再操作')
        
        if '{' in path:
            analysis['complexity'] = 'medium'
            analysis['suggestions'].append('🔧 需要替换路径参数 {tenant_id}')
        
        if method == 'GET':
            analysis['auto_tests'].append({'name': '查询测试', 'params': {'limit': 10}})
        elif method == 'POST':
            analysis['auto_tests'].append({'name': '创建测试', 'body': {'name': 'test'}})
        
        return analysis
    
    def generate_test_suggestions(self, apis):
        suggestions = {
            'priority_high': [],
            'priority_medium': [],
            'priority_low': [],
            'test_scenarios': []
        }
        
        for api in apis:
            risk = api.get('ai_analysis', {}).get('risk_level', 'low')
            if risk == 'high':
                suggestions['priority_high'].append(api)
            elif risk == 'medium':
                suggestions['priority_medium'].append(api)
            else:
                suggestions['priority_low'].append(api)
        
        return suggestions
    
    def analyze_response(self, response, api_path, method):
        analysis = {
            'status': 'success' if response.status_code < 400 else 'error',
            'performance': {},
            'issues': [],
            'suggestions': []
        }
        
        elapsed = response.elapsed.total_seconds()
        if elapsed > 3:
            analysis['performance']['warning'] = '⚠️ 响应时间过长'
            analysis['suggestions'].append('建议优化查询')
        elif elapsed > 1:
            analysis['performance']['warning'] = '⚡ 响应时间偏慢'
        else:
            analysis['performance']['status'] = '✅ 响应快速'
        
        if response.status_code >= 400:
            analysis['issues'].append('❌ HTTP ' + str(response.status_code))
        
        return analysis
    
    def analyze_test_results(self, results):
        summary = {
            'total': len(results),
            'passed': 0,
            'failed': 0,
            'errors': [],
            'recommendations': []
        }
        
        for r in results:
            if r.get('passed', False):
                summary['passed'] += 1
            else:
                summary['failed'] += 1
                summary['errors'].append({
                    'test': r.get('test_case', {}).get('name', 'Unknown'),
                    'error': r.get('error', '') or ', '.join(r.get('errors', []))
                })
        
        if summary['failed'] > 0:
            summary['recommendations'].append('🔧 有测试失败，请检查')
        
        if summary['total'] > 0:
            summary['trends'] = {
                'pass_rate': "{:.1f}%".format(float(summary['passed']) / summary['total'] * 100)
            }
        else:
            summary['trends'] = {
                'pass_rate': "0%"
            }
        
        return summary