# -*- coding: utf-8 -*-
"""
SQL 查询代理服务 - 用 mysql 命令行实现，无需 MySQLdb
部署在 <SQL_PROXY_HOST> 上

多底座支持: /query 请求体带 target 字段分流
  - nova: <SQL_PROXY_HOST> 本机 nova底座 mysql (127.0.0.1:3307/wjr_trove)
  - k8s : k8s 集群 trove 底座 MariaDB (经 <APP_HOST> 上的 kubectl port-forward 中转,
          因集群↔<SQL_PROXY_HOST> 网络隔离, <SQL_PROXY_HOST> 无法直达 ClusterIP/pod IP)
不带 target 时默认走 nova, 兼容旧客户端。

修复记录：
  - 旧版用 DESCRIBE 猜列名，导致列名与 SELECT 的列完全错位
  - 新版直接用 mysql -B 输出的第一行（真实列名），可靠且通用
  - Python 2 下 wfile.write(unicode) 会按 ascii 编码，中文报
    "'ascii' codec can't encode characters" —— 写之前先 encode('utf-8')
"""
import json
import os
import subprocess
import BaseHTTPServer
import SocketServer
from datetime import datetime, date

# ============ 多底座目标配置 ============
# k8s 目标前置:
#   1) <APP_HOST> 上保持 port-forward (kubectl -n trove port-forward svc/mysql 3306:3306 --address=0.0.0.0)
#   2) pod 内建远程账号: CREATE USER '<K8S_DB_USER>'@'%' IDENTIFIED BY '<K8S_DB_PASSWORD>';
#      GRANT SELECT ON wjr_trove.* TO '<K8S_DB_USER>'@'%'; FLUSH PRIVILEGES;
#
# 数据库密码不写入代码：默认占位符，真实密码通过环境变量注入。
# 例：NOVA_DB_PASSWORD='***' K8S_DB_PASSWORD='***' python2 sql_proxy.py
NOVA_DB_PASSWORD = os.environ.get('NOVA_DB_PASSWORD') or os.environ.get('TROVE_DB_PASSWORD', '<DB_PASSWORD>')
K8S_DB_PASSWORD = os.environ.get('K8S_DB_PASSWORD', '<DB_PASSWORD>')
TARGETS = {
    'nova': {
        'cmd': ['mysql', '-h127.0.0.1', '-P3307', '-uroot', '-p' + NOVA_DB_PASSWORD,
                '--default-character-set=utf8', 'wjr_trove', '-B', '--raw'],
    },
    'k8s': {
        'cmd': ['mysql', '-h<APP_HOST>', '-P3306', '-u<K8S_DB_USER>', '-p' + K8S_DB_PASSWORD,
                '--default-character-set=utf8', 'wjr_trove', '-B', '--raw'],
    },
}
DEFAULT_TARGET = 'nova'


def get_mysql_cmd(target):
    t = TARGETS.get(target) or TARGETS[DEFAULT_TARGET]
    return list(t['cmd'])


class SQLHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path == '/flow_retry':
            self._handle_flow_retry()
            return
        if self.path != '/query':
            self.send_error(404)
            return

        try:
            length = int(self.headers.getheader('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            sql = data.get('sql', '').strip()
            target = data.get('target', DEFAULT_TARGET) or DEFAULT_TARGET
            if target not in TARGETS:
                target = DEFAULT_TARGET

            if not sql:
                self._send_json({'success': False, 'error': 'SQL为空'})
                return

            # 只允许 SELECT / SHOW / DESCRIBE
            sql_upper = sql.upper()
            if not (sql_upper.startswith('SELECT')
                    or sql_upper.startswith('SHOW')
                    or sql_upper.startswith('DESCRIBE')
                    or sql_upper.startswith('DESC')
                    or sql_upper.startswith('EXPLAIN')):
                self._send_json({'success': False,
                                 'error': '仅支持 SELECT / SHOW / DESCRIBE / DESC / EXPLAIN 查询'})
                return

            # 用 mysql 命令行执行（保留列名头）
            cmd = get_mysql_cmd(target) + ['-e', sql]
            proc = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()

            if proc.returncode != 0:
                self._send_json({'success': False,
                                 'error': stderr.decode('utf-8', 'replace'),
                                 'target': target})
                return

            text = stdout.decode('utf-8', 'replace')
            # 去掉末尾空行，但保留中间空字符串（虽然理论上不会出现）
            lines = text.split('\n')
            while lines and lines[-1] == '':
                lines.pop()

            if not lines:
                # 空结果：给一个空 data，前端能正常处理
                self._send_json({'success': True, 'data': [], 'columns': [], 'target': target})
                return

            # 第一行 = 真实列名
            header = lines[0].split('\t')
            cols = [h.strip() for h in header]

            data_rows = []
            for line in lines[1:]:
                if line == '':
                    continue
                values = line.split('\t')
                row = {}
                for i, col in enumerate(cols):
                    # 越界保护：mysql -B 下每行列数应一致
                    row[col] = values[i] if i < len(values) else None
                data_rows.append(row)

            self._send_json({
                'success': True,
                'data': data_rows,
                'columns': cols,
                'target': target,
            })

        except Exception as e:
            try:
                self._send_json({'success': False, 'error': str(e)})
            except Exception:
                pass

    def do_GET(self):
        if self.path == '/health':
            self._send_json({'status': 'ok', 'targets': TARGETS.keys()})
        else:
            self.send_error(404)

    # ============ flow 重试: 重置失败task + flow-run (仅nova底座) ============
    def _exec_sql(self, sql, target=DEFAULT_TARGET):
        """内部直跑SQL(不做白名单校验, 仅服务端内部调用)"""
        cmd = get_mysql_cmd(target) + ['-e', sql]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            raise Exception(stderr.decode('utf-8', 'replace'))
        return stdout.decode('utf-8', 'replace')

    def _handle_flow_retry(self):
        """重试flow: 1) 把非终态卡住的task/sub_task重置为FAILED 2) flow置FAILED 3) 拉起 flow-run

        Flow.run 前置条件(engine/flow.py): flow.status 必须 NEW/FAILED;
        task.py: FAILED 的 task 引擎重跑时自动转 NEW 执行, 但 RUNNING 会抛 "task is running";
        因此这里把 RUNNING/TIMEOUT/TERMINATED 的 task/sub_task 统一重置为 FAILED,
        再触发 flow-run, 由引擎按 FAILED->NEW 的语义重跑失败部分。
        注意: flow-run 只针对 nova 底座的 taskmanager, k8s 底座不支持(handler.py 已拦截)。
        """
        try:
            length = int(self.headers.getheader('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            flow_id = (data.get('flow_id') or '').strip().replace("'", "''")
            if not flow_id:
                self._send_json({'success': False, 'error': 'flow_id为空'})
                return

            # 0. 前置检查: flow 必须存在
            out = self._exec_sql("SELECT status FROM flows WHERE id='%s' AND deleted=0" % flow_id,
                                 'nova')
            lines = [l for l in out.split('\n') if l != '']
            if len(lines) < 2:
                self._send_json({'success': False, 'error': 'flow不存在: %s' % flow_id})
                return
            flow_status = lines[1].strip()
            if flow_status == 'RUNNING':
                self._send_json({'success': False,
                                 'error': 'flow正在RUNNING(可能真实在跑), 禁止重试; 如确认卡死请先人工reset-status'})
                return

            reset = []
            # 1. 卡住的 task / sub_task (RUNNING|TIMEOUT|TERMINATED) 重置为 FAILED
            self._exec_sql("UPDATE tasks SET status='FAILED' WHERE flow_id='%s' "
                           "AND status IN ('RUNNING','TIMEOUT','TERMINATED')" % flow_id, 'nova')
            reset.append('tasks')
            self._exec_sql("UPDATE sub_tasks st INNER JOIN tasks t ON st.task_id=t.id "
                           "SET st.status='FAILED' WHERE t.flow_id='%s' "
                           "AND st.status IN ('RUNNING','TIMEOUT','TERMINATED')" % flow_id, 'nova')
            reset.append('sub_tasks')

            # 2. flow 状态非NEW/FAILED时(TIMEOUT/TERMINATED)拉回FAILED, 否则 Flow.run 会拒绝
            if flow_status not in ('NEW', 'FAILED'):
                self._exec_sql("UPDATE flows SET status='FAILED' WHERE id='%s'" % flow_id, 'nova')
                reset.append('flows(%s->FAILED)' % flow_status)

            # 3. 拉起 flow-run (与 ktrove-manage flow-run 等价, 后台执行)
            flow_shell = ('/home/wangjingru/ktrove_venv/lib/python2.7/site-packages'
                          '/trove/taskmanager/engine/shell.py')
            cmd = ('/home/wangjingru/ktrove_venv/bin/python %s run %s '
                   '--config_file /home/wangjingru/etc/ktrove/ktrove-taskmanager.conf'
                   % (flow_shell, flow_id))
            subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE, close_fds=True)

            self._send_json({'success': True, 'flow_id': flow_id,
                             'reset': reset, 'prev_status': flow_status,
                             u'message': u'已重置并触发flow-run, 请稍后刷新查看'})
        except Exception as e:
            import traceback as _tb
            self._send_json({'success': False, 'error': str(e), 'tb': _tb.format_exc()})

    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        _body = self._dumps(self._to_unicode(data))
        # Python 2 修复：unicode 直接写 wfile 会按 ascii 编码，中文报错
        if isinstance(_body, unicode):
            _body = _body.encode('utf-8')
        self.wfile.write(_body)

    def _dumps(self, obj):
        def _default(o):
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            raise TypeError
        return json.dumps(obj, default=_default, ensure_ascii=False)

    @staticmethod
    def _to_unicode(o):
        """递归把 py2 str(可能含utf-8中文)转unicode, 避免json.dumps混型炸ascii"""
        if isinstance(o, str):
            return o.decode('utf-8', 'replace')
        if isinstance(o, list):
            return [SQLHandler._to_unicode(x) for x in o]
        if isinstance(o, tuple):
            return tuple(SQLHandler._to_unicode(x) for x in o)
        if isinstance(o, dict):
            return dict((SQLHandler._to_unicode(k), SQLHandler._to_unicode(v))
                        for k, v in o.items())
        return o


if __name__ == '__main__':
    PORT = 5001
    print('SQL Proxy 启动在 http://0.0.0.0:%d' % PORT)
    for name in TARGETS:
        c = TARGETS[name]['cmd']
        # 只打印到 -P 端口，避免把 -p 密码打进日志
        print('  target[%s]: %s' % (name, ' '.join(c[:3])))
    server = SocketServer.TCPServer(('0.0.0.0', PORT), SQLHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止')
