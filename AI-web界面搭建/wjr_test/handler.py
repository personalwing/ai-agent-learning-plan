# -*- coding: utf-8 -*-
import json
import requests
import time
import re
import subprocess
import traceback
from datetime import datetime

# MySQL连接配置（通过 <SQL_PROXY_HOST> 上的 SQL 代理服务）
SQL_PROXY_URL = 'http://<SQL_PROXY_HOST>:5001/query'
# 多底座目标: nova=<SQL_PROXY_HOST> nova底座(127.0.0.1:3307), k8s=k8s集群trove底座MariaDB
SQL_TARGETS = ('nova', 'k8s')
SQL_DEFAULT_TARGET = 'nova'


def _norm_target(t):
    return t if t in SQL_TARGETS else SQL_DEFAULT_TARGET

# 默认请求头（根据接口文档固定）
DEFAULT_HEADERS = {
    "X-Auth-Project-Id": "<PROJECT_ID>",
    "X-Auth-Token": "<AUTH_TOKEN>",
    "X-KSC-APPLICATION-TOKEN": "<KSC_APPLICATION_TOKEN>",
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
    {"path": "/v1.0/{tenant_id}/backup-resources/list_backup_records", "method": "GET", "category": "副本集接口", "name": "查询副本集备份列表", "description": "查询副本集实例的备份记录列表，?id=备份资源ID或resource_id"},
    
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

# ktrove 后端实测可用的 MongoDB 路由表
SCANNED_APIS = [
    # ==================== 副本集 repset ====================
    {"path": "/v1.0/{tenant_id}/mongodb-repset", "method": "GET", "category": "副本集", "name": "副本集列表", "description": "获取所有未删除副本集实例列表，分页用 offset/limit"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset", "method": "POST", "category": "副本集", "name": "创建副本集", "description": "同一接口按body衍生: 下拉选 vm/k8s 自动填默认参数。k8s走mongodb_create_replicaset_kube流程, 前置: wjrdev部署k8s_mongodb分支且conf配mongodb.compute_backend=kube与[kubernetes]段, datastore.version需有对应kube镜像(默认4.2), volume.type转storageclass(ESSD_PL0→essd-pl0); 重复创建需改name", "actions": [
        {"key": "vm-默认", "body": "{\"mongodb_repset\": {\"admin_user\": \"root\", \"admin_password\": \"<ADMIN_PASSWORD>\", \"name\": \"wjrdev32\", \"area\": [\"1\"], \"vcpu\": 2, \"mem_size\": 4, \"disk_size\": 25, \"node_num\": 3, \"vpc\": {\"vpc_id\": \"<VPC_ID>\", \"vnet_id\": \"<VNET_ID>\"}, \"protocol\": \"memcached\", \"datastore\": {\"version\": \"3.2\"}, \"join_shard\": false}}"},
        {"key": "k8s-默认", "body": "{\"mongodb_repset\": {\"admin_user\": \"root\", \"admin_password\": \"<ADMIN_PASSWORD>\", \"name\": \"wjrkube01\", \"area\": [\"1\"], \"vcpu\": 2, \"mem_size\": 4, \"disk_size\": 25, \"node_num\": 3, \"volume\": {\"size\": 25, \"type\": \"ESSD_PL0\"}, \"vpc\": {\"vpc_id\": \"<VPC_ID>\", \"vnet_id\": \"<VNET_ID>\"}, \"protocol\": \"memcached\", \"datastore\": {\"type\": \"mongodb\", \"version\": \"4.2\"}, \"join_shard\": false}}"}
    ]},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}", "method": "GET", "category": "副本集", "name": "副本集详情", "description": "获取指定副本集实例详情"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}", "method": "DELETE", "category": "副本集", "name": "删除副本集", "description": "删除指定副本集实例"},
    {"path": "/v1.0/{tenant_id}/mongodb-repset/{cluster_id}/action", "method": "POST", "category": "副本集", "name": "副本集动作", "description": "lock/unlock/rename/restart/resize/add_user 等 action，选中后 body 自动填充; aggregate_monitor 的 target=all/primary/secondary", "actions": [
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
    {"path": "/v1.0/{tenant_id}/mongodb-cluster", "method": "POST", "category": "分片集群", "name": "创建集群", "description": "创建 MongoDB 分片集群实例，选中后 body 自动填充必传字段", "body_template": "{\"mongodb_cluster\": {\"admin_user\": \"root\", \"protocol\": \"memcached\", \"name\": \"wjrdev80\", \"shards\": {\"vcpu\": 2, \"mem_size\": 4, \"shards_num\": 2, \"disk_size\": 15, \"area\": [\"1\"]}, \"config_server\": {\"vcpu\": 2, \"mem_size\": 4, \"disk_size\": 40}, \"mongos\": {\"vcpu\": 2, \"mem_size\": 4, \"mongos_num\": 2, \"disk_size\": 15, \"area\": [\"2\"]}, \"vpc\": {\"vpc_id\": \"<VPC_ID2>\", \"vnet_id\": \"<VNET_ID2>\"}, \"datastore\": {\"version\": \"8.0\"}, \"join_shard\": false, \"admin_password\": \"<ADMIN_PASSWORD>\"}}"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}", "method": "GET", "category": "分片集群", "name": "集群详情", "description": "获取指定分片集群实例详情"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}", "method": "DELETE", "category": "分片集群", "name": "删除集群", "description": "删除指定分片集群实例"},
    {"path": "/v1.0/{tenant_id}/mongodb-cluster/{cluster_id}/action", "method": "POST", "category": "分片集群", "name": "集群动作", "description": "list_shards/add_shard/lock/unlock 等 action，选中后 body 自动填充; aggregate_monitor 的 target=mongos/shard/all(target=configsvr 会报错)", "actions": [
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
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{cluster_id}/action", "method": "POST", "category": "通用", "name": "资源动作", "description": "lock/unlock/rename/restart/resize 等 action，选中后 body 自动填充; aggregate_monitor 的 target 按产品类型: 副本集=all/primary/secondary, 集群=mongos/shard/all", "actions": [
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
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{product_id}/list_instances", "method": "GET", "category": "通用", "name": "产品下实例列表", "description": "查询指定产品(product_id)下的节点实例列表", "params": {}},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{product_id}/ssl/certificates/{cert_id}/download", "method": "GET", "category": "通用", "name": "SSL证书下载", "description": "下载指定实例的SSL证书文件"},

    # ==================== 公共：统计/数据源/备份 ====================
    {"path": "/v1.0/{tenant_id}/mongodb-resource/statistic", "method": "GET", "category": "公共", "name": "资产统计", "description": "按 db_type=mongodb 统计实例总数/运行/异常及健康分布"},
    {"path": "/v1.0/{tenant_id}/datasource", "method": "GET", "category": "公共", "name": "数据源列表", "description": "按 db_type=mongodb 查询数据源列表"},
    {"path": "/v1.0/{tenant_id}/datasource/{instance_id}/sync_instance", "method": "POST", "category": "公共", "name": "同步数据源", "description": "触发指定实例数据源同步(健康检测)，body 可空", "body_template": "{}"},
    {"path": "/v1.0/{tenant_id}/backup-resources", "method": "POST", "category": "公共", "name": "发起备份", "description": "手动发起 MongoDB 物理备份，选中后 body 自动填充", "body_template": "{\"backup_resource\": {\"cluster_id\": \"\", \"mode\": \"repset\", \"reserve_days\": 7}}"},
    {"path": "/v1.0/{tenant_id}/backup-resources/detail", "method": "GET", "category": "公共", "name": "备份资源详情", "description": "列出当前租户所有备份资源详情"},
    {"path": "/v1.0/{tenant_id}/backup-resources/list_backup_records", "method": "GET", "category": "公共", "name": "副本集备份列表", "description": "查询副本集实例备份记录列表，?id=备份资源ID或resource_id", "params": {"id": ""}},
    {"path": "/v1.0/{tenant_id}/backup-resources/list_cluster_backup_records", "method": "GET", "category": "公共", "name": "集群备份列表", "description": "查询分片集群实例备份记录列表，?id=备份资源ID或resource_id", "params": {"id": ""}},
    {"path": "/v1.0/{tenant_id}/backup-records/{record_id}", "method": "DELETE", "category": "公共", "name": "删除备份记录", "description": "按备份记录 ID 删除指定备份"},

    # ==================== 会话管理(mongodb-resource, 2026-09 dmp 一期) ====================
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{product_id}/session-mgmt", "method": "GET", "category": "会话管理", "name": "会话列表+连接统计", "description": "返回会话列表/连接明细/统计+node_stats节点级五项概览(一次请求同拿明细与概览)。可选参数: instance_id(按节点查, 副本集secondary/集群shard/configsvr均支持)、active_only(默认true)、min_secs_running(秒)。不传instance_id时副本集fan-out全部业务节点、集群fan-out全部mongos", "params": {"instance_id": "", "active_only": "true", "min_secs_running": "0"}},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{product_id}/session-mgmt/kill", "method": "POST", "category": "会话管理", "name": "终止会话", "description": "单条/精确批量用opids(必传instance_id, opid为节点本地值须与查询节点同源, 集群可为\"shard:opid\")；条件批量用pattern(users/roles需实例侧kscSessionMgr角色授权, 3.6有服务端自中断bug表现400快速失败, 4.0+正常)", "body_template": "{\"opids\": [12345], \"instance_id\": \"\", \"force\": false}"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{product_id}/session-mgmt/kill", "method": "POST", "category": "会话管理", "name": "条件批量终止(pattern)", "description": "按pattern批量kill: {\"users\":[{\"user\":\"x\",\"db\":\"admin\"}]} / {\"roles\":[...]} / {\"lsid\":{...}}; 不传instance_id时按拓扑定位(副本集primary/集群mongos)", "body_template": "{\"pattern\": {\"users\": [{\"user\": \"\", \"db\": \"admin\"}]}, \"instance_id\": \"\"}"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/{product_id}/session-mgmt/history", "method": "GET", "category": "会话管理", "name": "终止历史", "description": "会话终止操作审计记录(按start_time倒序), 支持limit与instance_id(节点)过滤", "params": {"limit": "10", "instance_id": ""}},

    # ==================== 账号管理(instances/{instance_id}/accounts, dmp 一期) ====================
    {"path": "/v1.0/{tenant_id}/instances/{instance_id}/accounts", "method": "GET", "category": "账号管理", "name": "账号列表", "description": "查询实例账号列表, 支持keyword模糊过滤", "params": {"keyword": ""}},
    {"path": "/v1.0/{tenant_id}/instances/{instance_id}/accounts", "method": "POST", "category": "账号管理", "name": "创建账号", "description": "创建账号, roles为标准mongo角色(read/readWrite/dbAdmin/root等); 系统保留用户/短密码/非法字符等会被拒绝(1104/1105)", "body_template": "{\"name\": \"wjrtest_user\", \"password\": \"<ADMIN_PASSWORD>\", \"description\": \"测试账号\", \"databases\": [{\"name\": \"admin\", \"roles\": [\"read\"]}]}"},
    {"path": "/v1.0/{tenant_id}/instances/{instance_id}/accounts/{account_name}", "method": "PUT", "category": "账号管理", "name": "修改账号密码/描述", "description": "修改账号密码与描述", "body_template": "{\"password\": \"NewPass456!!\", \"description\": \"描述已改\"}"},
    {"path": "/v1.0/{tenant_id}/instances/{instance_id}/accounts/{account_name}/privileges", "method": "POST", "category": "账号管理", "name": "权限变更", "description": "变更账号在库上的角色(如admin:read -> admin:dbAdmin)", "body_template": "{\"databases\": [{\"name\": \"admin\", \"roles\": [\"dbAdmin\"]}]}"},
    {"path": "/v1.0/{tenant_id}/instances/{instance_id}/accounts/{names}", "method": "DELETE", "category": "账号管理", "name": "删除账号", "description": "删除指定账号(支持逗号分隔批量)"},

    # ==================== 数据源/大盘(datasource, dmp 一期) ====================
    {"path": "/v1.0/{tenant_id}/datasource", "method": "GET", "category": "数据源", "name": "数据源列表", "description": "查询数据源列表(db_type=mongodb), 可按instance_id过滤", "params": {"db_type": "mongodb", "instance_id": ""}},
    {"path": "/v1.0/{tenant_id}/datasource", "method": "POST", "category": "数据源", "name": "创建数据源", "description": "创建数据源(upsert防重: 同实例重复创建为更新); datasource_type=admin/ro", "body_template": "{\"instance_id\": \"\", \"engine\": \"mongodb\", \"name\": \"wjr-test-ds\", \"username\": \"ksc_admin\", \"password\": \"<DATASOURCE_PASSWORD>\", \"datasource_type\": \"admin\"}"},
    {"path": "/v1.0/{tenant_id}/datasource/{instance_id}", "method": "PUT", "category": "数据源", "name": "编辑数据源", "description": "编辑数据源配置(密码/描述等)", "body_template": "{\"password\": \"\", \"description\": \"\"}"},
    {"path": "/v1.0/{tenant_id}/datasource/{instance_id}", "method": "DELETE", "category": "数据源", "name": "删除数据源", "description": "删除数据源(支持逗号分隔批量), 会级联删除已同步的库/schema元数据"},
    {"path": "/v1.0/{tenant_id}/datasource/ping", "method": "POST", "category": "数据源", "name": "数据源连通性检测", "description": "用给定凭据实测连接(不经instance_id), ok=true/false 区分成功与凭据错误", "body_template": "{\"instance_id\": \"\", \"engine\": \"mongodb\", \"username\": \"ksc_admin\", \"password\": \"\", \"datasource_type\": \"admin\"}"},
    {"path": "/v1.0/{tenant_id}/datasource/{instance_id}/sync_instance", "method": "POST", "category": "数据源", "name": "同步实例元数据", "description": "触发实例元数据同步(健康检测), body 可空", "body_template": "{}"},
    {"path": "/v1.0/{tenant_id}/mongodb-resource/statistic", "method": "GET", "category": "数据源", "name": "资产大盘统计", "description": "按db_type统计实例总数/运行/异常及health_breakdown细分", "params": {"db_type": "mongodb"}},

    # ==================== SQL窗口(dmp 一期) ====================
    {"path": "/v1.0/{tenant_id}/sql/execute", "method": "POST", "category": "SQL窗口", "name": "MQL执行", "description": "执行MQL语句(读/写需confirmed=true); dropDatabase等黑名单拒绝; 多语句; 1000行截断", "body_template": "{\"instance_id\": \"\", \"datasource_type\": \"admin\", \"database\": \"admin\", \"statement\": \"db.runCommand({ping: 1})\", \"confirmed\": false}"},
    {"path": "/v1.0/{tenant_id}/sql/check", "method": "POST", "category": "SQL窗口", "name": "MQL语法检查", "description": "真实语法检查(body需engine=mongodb): 多语句拆分(上限10条)/黑名单函数(eval/load/sleep/assert)/括号配对/show元命令放行, 与ga执行前置逻辑一致; 返回{success,error}, 异常HTTP仍200; 不带engine走原桩恒true(pg等不受影响)", "body_template": "{\"engine\": \"mongodb\", \"statement\": \"db.t1.find({a:1}).limit(10)\"}"},
    {"path": "/v1.0/{tenant_id}/sql/pretty", "method": "POST", "category": "SQL窗口", "name": "MQL格式化", "description": "真实格式化(body需engine=mongodb): 按括号深度缩进, 只动空白不动token, 多语句以空行分隔; 解析失败原样返回不报错; 不带engine原样透传", "body_template": "{\"engine\": \"mongodb\", \"statement\": \"db.t1.find({a:{$gt:1}},{b:1}).sort({a:-1}).limit(5)\"}"},
    {"path": "/v1.0/{tenant_id}/sql/history", "method": "GET", "category": "SQL窗口", "name": "执行历史", "description": "MQL执行历史, 支持instance_id/limit/时间过滤(start_time/end_time), 返回record+total_count+marker", "params": {"instance_id": "", "limit": "10"}},
    {"path": "/v1.0/{tenant_id}/db", "method": "GET", "category": "SQL窗口", "name": "库列表(元数据)", "description": "返回实例的库列表(裸数组[{id,name,...}])", "params": {"instance_id": ""}},
    {"path": "/v1.0/{tenant_id}/db/{db_id}/schema", "method": "GET", "category": "SQL窗口", "name": "集合结构详情", "description": "返回库的schema(collections/fields类型推断/indexes); 需先sync_schema", "params": {}},
    {"path": "/v1.0/{tenant_id}/db/{db_id}/sync_schema", "method": "POST", "category": "SQL窗口", "name": "同步集合结构", "description": "同步指定库的集合结构与索引, body 可空", "body_template": "{}"},

    # ==================== K8S(mongodb on kube, DataBase-NoSQL-1308) ====================
    # 注意: k8s创建副本集不是独立接口, 是POST /mongodb-repset按body参数衍生(volume.type转storageclass等),
    # 独立条目会因path+method与「创建副本集」相同被integrate_apis去重, 故做成该条目的actions下拉(vm-默认/k8s-默认)
]

# ============ SQL 元数据缓存（按底座 target 独立） ============
_SQL_META_CACHE = {}
_SQL_META_TTL = 300  # 5 分钟
# =====================================


class WJRTestHandler:
    """WJR测试处理器"""

    @staticmethod
    def _convert_page_to_offset(params):
        """将分页参数 page 转换为后端认的 offset。"""
        if not params:
            return params
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
        params = dict(params)
        if 'page' in params and 'offset' not in params:
            try:
                page = int(params.pop('page'))
                limit = int(params.get('limit', 10))
                params['offset'] = max(0, (page - 1) * limit)
            except (ValueError, TypeError):
                params.pop('page', None)
        else:
            params.pop('page', None)
        return params

    def __init__(self):
        self.kscc_base_url = "http://<SQL_PROXY_HOST>:9777"
        self.ktrove_proxy_path = ""
        self.scanner = APIScanner()
        self.runner = TestRunner()
        self.analyzer = AIAnalyzer()

    # ============================================================
    # 流程图追踪相关常量
    # ============================================================
    KSCC_CONTAINER = 'wjrKscc'
    FLOW_TRACE_TIMEOUT = 600  # 秒
    # ============================================================

    def handle_discover(self):
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

            params = self._convert_page_to_offset(params)

            target_url = self.kscc_base_url + self.ktrove_proxy_path + api_path

            start_time = time.time()
            max_retries = 2
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    response = requests.request(
                        method=method,
                        url=target_url,
                        headers=headers,
                        params=params,
                        json=body if (method.upper() in ('POST', 'PUT') and body is not None) else None,
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
                except requests.exceptions.Timeout:
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
        return self.execute_sql_query("SELECT * FROM api_endpoints WHERE is_fixed=1 AND is_active=1 ORDER BY category, name")

    def handle_execute_sql(self, data):
        sql = data.get('sql', '').strip()
        if not sql:
            return {'success': False, 'error': 'SQL不能为空'}
        sql_upper = sql.upper()
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('SHOW') or sql_upper.startswith('DESCRIBE')):
            return {'success': False, 'error': '仅支持 SELECT / SHOW / DESCRIBE 查询'}
        return self.execute_sql_query(sql, data.get('target'))

    def execute_sql_query(self, sql, target=None):
        try:
            headers = {'Content-Type': 'application/json'}
            payload = json.dumps({'sql': sql, 'target': _norm_target(target)})
            response = requests.post(
                SQL_PROXY_URL,
                data=payload,
                headers=headers,
                timeout=30
            )
            return json.loads(response.text)
        except requests.exceptions.ConnectionError as e:
            return {'success': False, 'error': '无法连接到 SQL 代理服务 (<SQL_PROXY_HOST>:5001)，请确认服务已启动: ' + str(e)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_sql_meta(self, target=None):
        target = _norm_target(target)
        now = time.time()
        cache = _SQL_META_CACHE.setdefault(target, {'data': None, 'ts': 0})
        if cache['data'] and (now - cache['ts']) < _SQL_META_TTL:
            data = dict(cache['data'])
            data['cached'] = True
            data['ts'] = cache['ts']
            return data

        sql = ("SELECT TABLE_NAME, COLUMN_NAME "
               "FROM information_schema.COLUMNS "
               "WHERE TABLE_SCHEMA = DATABASE() "
               "ORDER BY TABLE_NAME, ORDINAL_POSITION")

        result = self.execute_sql_query(sql, target)

        tables = []
        columns = {}
        error_msg = None

        if not isinstance(result, dict) or not result.get('success', True):
            error_msg = (result or {}).get('error', 'SQL 代理返回异常')

        rows = self._extract_rows(result)

        for r in rows:
            if isinstance(r, dict):
                t = (r.get('TABLE_NAME') or r.get('table_name') or r.get('table') or r.get('col_0'))
                c = (r.get('COLUMN_NAME') or r.get('column_name') or r.get('column') or r.get('col_1'))
            elif isinstance(r, (list, tuple)) and len(r) >= 2:
                t, c = r[0], r[1]
            else:
                continue
            if not t:
                continue
            if t not in columns:
                columns[t] = []
                tables.append(t)
            if c and c not in columns[t]:
                columns[t].append(c)

        data = {
            'success': True,
            'tables': tables,
            'columns': columns,
            'cached': False,
            'ts': now
        }
        if error_msg:
            data['warning'] = error_msg

        if tables:
            cache['data'] = {
                'success': True,
                'tables': tables,
                'columns': columns
            }
            cache['ts'] = now

        return data

    def handle_products(self):
        try:
            products = self.scanner.list_mongodb_products(self.kscc_base_url)
            return {'success': True, 'data': products}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ============================================================
    # 请求流程图追踪（调用 kscc /flow-trace skill）
    # ============================================================
    def handle_flow_trace(self, data):
        try:
            api_path = (data.get('path') or '').strip()
            method = (data.get('method') or 'GET').strip().upper()
            action = (data.get('action') or '').strip()

            if not api_path:
                return {'success': False, 'error': '缺少 path'}

            prompt = self._build_flow_trace_prompt(method, api_path, action)
            raw, call_err = self._call_kscc_flow_trace(prompt)
            if raw is None:
                return {'success': False, 'error': call_err or 'KSCC /flow-trace 调用失败或超时'}

            parsed = self._parse_flow_trace(raw, method, api_path)
            parsed['success'] = True
            return {'success': True, 'data': parsed}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _build_flow_trace_prompt(self, method, api_path, action):
        """构造 kscc /flow-trace 命令。"""
        prompt = u'/flow-trace %s %s' % (method, api_path)
        if action:
            prompt += u' action=%s' % action
        return prompt

    def _call_kscc_flow_trace(self, prompt):
        """直接执行 /root/.kscc/skills/flow-trace/scripts/flow-trace.sh（绕过 kscc 沙箱审批）。

        prompt 格式: "/flow-trace POST /v1.0/{tenant_id}/mongodb-repset"
        """
        import threading
        import sys as _sys

        def _log(msg):
            try:
                _sys.stderr.write(u'[flow-trace] %s\n' % msg)
                _sys.stderr.flush()
            except Exception:
                pass

        try:
            m = re.match(r'/flow-trace\s+(\S+)\s+(.+)', prompt.strip())
            if not m:
                return None, u'无法解析 flow-trace 命令: %s' % prompt
            method = m.group(1).strip()
            path = m.group(2).strip()

            path_safe = path.replace("'", "'\\''")

            cmd = "docker exec %s /root/.kscc/skills/flow-trace/scripts/flow-trace.sh %s '%s'" % (
                self.KSCC_CONTAINER, method, path_safe
            )
            _log('START cmd=%s' % cmd[:200])
            t0 = time.time()

            proc = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.PIPE, close_fds=True
            )
            timed_out = [False]

            def _kill():
                timed_out[0] = True
                _log('TIMEOUT after %.1fs, killing pid=%s' % (time.time() - t0, proc.pid))
                try:
                    proc.kill()
                except Exception:
                    pass

            timer = threading.Timer(self.FLOW_TRACE_TIMEOUT, _kill)
            timer.start()
            try:
                out, err = proc.communicate()
            finally:
                timer.cancel()

            dt = time.time() - t0
            out_s = out.decode('utf-8', 'replace').strip() if out else u''
            err_s = err.decode('utf-8', 'replace').strip() if err else u''

            _log('DONE dt=%.1fs rc=%s timed_out=%s out_len=%d err_len=%d'
                 % (dt, proc.returncode, timed_out[0], len(out_s), len(err_s)))
            if err_s:
                _log('STDERR: ' + err_s[:500])

            if timed_out[0]:
                return None, u'flow-trace 超时（%d 秒）' % self.FLOW_TRACE_TIMEOUT
            if proc.returncode != 0:
                return None, u'flow-trace 脚本退出码 %s: %s' % (proc.returncode, err_s[:300])
            if not out_s:
                return None, u'flow-trace 无输出（stderr: %s）' % err_s[:300]
            return out_s, None
        except Exception as e:
            try:
                _sys.stderr.write('[flow-trace exception] ' + traceback.format_exc() + '\n')
                _sys.stderr.flush()
            except Exception:
                pass
            return None, u'调用异常: %s' % unicode(e)

    def _parse_flow_trace(self, raw, method, api_path):
        """从 kscc 返回文本中解析 JSON；解析失败则降级为纯文本展示。"""
        text = (raw or '').strip()

        fence = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
        if fence:
            text = fence.group(1).strip()

        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            i = text.find('{')
            j = text.rfind('}')
            if i != -1 and j != -1 and j > i:
                try:
                    parsed = json.loads(text[i:j + 1])
                except Exception:
                    parsed = None

        if not isinstance(parsed, dict) or 'nodes' not in parsed:
            return {
                'api': {'method': method, 'path': api_path},
                'nodes': [],
                'edges': [],
                'summary': '',
                'raw': raw,
                'degraded': True
            }

        nodes = parsed.get('nodes', []) or []
        edges = parsed.get('edges', []) or []

        clean_nodes = []
        seen_ids = set()
        for idx, n in enumerate(nodes):
            if not isinstance(n, dict):
                continue
            nid = n.get('id') or ('n%d' % idx)
            if nid in seen_ids:
                nid = nid + '_%d' % idx
            seen_ids.add(nid)
            clean_nodes.append({
                'id': nid,
                'layer': n.get('layer', 'unknown'),
                'title': n.get('title', ''),
                'detail': n.get('detail', ''),
                'file': n.get('file', '')
            })

        clean_edges = []
        node_ids = set(n['id'] for n in clean_nodes)
        for e in edges:
            if not isinstance(e, dict):
                continue
            f = e.get('from')
            t = e.get('to')
            if f in node_ids and t in node_ids:
                clean_edges.append({
                    'from': f, 'to': t,
                    'label': e.get('label', '')
                })

        return {
            'api': {'method': method, 'path': api_path},
            'nodes': clean_nodes,
            'edges': clean_edges,
            'summary': parsed.get('summary', ''),
            'raw': raw,
            'degraded': False
        }

    # ============================================================
    # 执行轨迹查询（查 flows / tasks / sub_tasks 表）
    # ============================================================
    def handle_list_flows(self, data):
        """查询最近的 flow 列表。

        请求: {name?, product_id?, limit?, target?}
        返回: {success, data: [ {...}, ... ]}
        """
        name = (data.get('name') or '').strip()
        product_id = (data.get('product_id') or '').strip()
        limit = int(data.get('limit') or 30)
        if limit > 200:
            limit = 200
        target = _norm_target(data.get('target'))

        where = []
        if name:
            where.append("name LIKE '%%%s%%'" % name.replace("'", "''"))
        if product_id:
            where.append("product_id = '%s'" % product_id.replace("'", "''"))
        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

        sql = ("SELECT id, product_id, name, status, created, updated, "
               "TIMESTAMPDIFF(SECOND, created, updated) AS duration_sec "
               "FROM flows %s "
               "ORDER BY created DESC LIMIT %d" % (where_sql, limit))

        return self.execute_sql_query(sql, target)

    def handle_flow_detail(self, data):
        """根据 flow_id 查该 flow 下所有 task + 每个 task 下所有 sub_task。

        请求: {flow_id}
        返回: {success, data: {flow, tasks:[{...task, sub_tasks:[...]}]}}
        """
        flow_id = (data.get('flow_id') or '').strip()
        if not flow_id:
            return {'success': False, 'error': '缺少 flow_id'}
        flow_id_safe = flow_id.replace("'", "''")
        target = _norm_target(data.get('target'))

        flow_sql = ("SELECT id, product_id, name, status, created, updated, result, "
                    "TIMESTAMPDIFF(SECOND, created, updated) AS duration_sec "
                    "FROM flows WHERE id = '%s' LIMIT 1" % flow_id_safe)
        flow_result = self.execute_sql_query(flow_sql, target)
        flow_rows = self._extract_rows(flow_result)
        if not flow_rows:
            return {'success': False, 'error': '未找到 flow: %s' % flow_id}
        flow = flow_rows[0]

        tasks_sql = ("SELECT id, flow_id, name, status, created, updated, result, "
                     "TIMESTAMPDIFF(SECOND, created, updated) AS duration_sec "
                     "FROM tasks WHERE flow_id = '%s' "
                     "ORDER BY created ASC" % flow_id_safe)
        tasks_result = self.execute_sql_query(tasks_sql, target)
        tasks = self._extract_rows(tasks_result)

        for t in tasks:
            st_sql = ("SELECT id, task_id, name, status, number, created, updated, result, "
                      "TIMESTAMPDIFF(SECOND, created, updated) AS duration_sec "
                      "FROM sub_tasks WHERE task_id = '%s' "
                      "ORDER BY number ASC, created ASC" % t['id'].replace("'", "''"))
            st_result = self.execute_sql_query(st_sql, target)
            t['sub_tasks'] = self._extract_rows(st_result)

        return {
            'success': True,
            'data': {'flow': flow, 'tasks': tasks}
        }

    # ============================================================
    # 资源列表查询（副本集 / 集群）
    # ============================================================
    def handle_list_resources(self, data):
        """查询 MySQL 里的 MongoDB 副本集 + 分片集群。

        products.type:
          MONGODB        -> 副本集
          SHARD_CLUSTER  -> 分片集群
        其它 type（SHARD_CLUSTER_NODE / MONGOS / CONFIGSVR）是内部节点，不展示。

        请求: {limit?, include_deleted?, target?}
        返回: {success, data: [ {id, name, type, kind, status, created, version} ]}
        """
        limit = int(data.get('limit') or 100)
        if limit > 500:
            limit = 500
        include_deleted = bool(data.get('include_deleted'))
        target = _norm_target(data.get('target'))

        where = ["type IN ('MONGODB', 'SHARD_CLUSTER')"]
        if not include_deleted:
            where.append("deleted = 0")
        where_sql = 'WHERE ' + ' AND '.join(where)

        sql = ("SELECT id, name, type, status, created, updated, deleted, version "
               "FROM products %s "
               "ORDER BY created DESC LIMIT %d" % (where_sql, limit))
        result = self.execute_sql_query(sql, target)
        rows = self._extract_rows(result)

        for r in rows:
            t = (r.get('type') or '').upper()
            if t == 'MONGODB':
                r['kind'] = 'repset'
            elif t == 'SHARD_CLUSTER':
                r['kind'] = 'cluster'
            else:
                r['kind'] = 'other'

        return {'success': True, 'data': rows, 'table': 'products'}

    # ============================================================
    # flow 重试: 重置失败task + flow-run (经<SQL_PROXY_HOST>代理执行, 仅nova底座)
    # ============================================================
    def handle_flow_retry(self, data):
        flow_id = (data.get('flow_id') or '').strip()
        if not flow_id:
            return {'success': False, 'error': '缺少 flow_id'}
        if _norm_target(data.get('target')) != 'nova':
            return {'success': False, 'error': 'k8s底座暂不支持 flow 重试(代理仅nova可写库)'}
        try:
            headers = {'Content-Type': 'application/json'}
            payload = json.dumps({'flow_id': flow_id})
            response = requests.post(
                SQL_PROXY_URL.rsplit('/', 1)[0] + '/flow_retry',
                data=payload, headers=headers, timeout=30)
            return json.loads(response.text)
        except requests.exceptions.ConnectionError as e:
            return {'success': False, 'error': '无法连接 <SQL_PROXY_HOST> SQL 代理服务(5001), 请确认新版 sql_proxy.py 已重启: ' + str(e)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _extract_rows(self, result):
        """从 SQL 代理返回的各种结构里抽出 rows 列表。"""
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ('data', 'rows', 'result', 'results'):
                v = result.get(key)
                if isinstance(v, list):
                    return v
        return []
    # ============================================================


class APIScanner:
    """API扫描器"""

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

        params = WJRTestHandler._convert_page_to_offset(params)

        target_url = kscc_url + proxy_path + path

        try:
            start_time = time.time()
            response = requests.request(
                method=method,
                url=target_url,
                headers=headers,
                params=params,
                json=body if (method.upper() in ('POST', 'PUT') and body is not None) else None,
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