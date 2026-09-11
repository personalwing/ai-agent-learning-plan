# -*- coding: utf-8 -*-
"""
SQL 查询代理服务 - 用 mysql 命令行实现，无需 MySQLdb
部署在 <SQL_PROXY_HOST> 上

修复记录：
  - 旧版用 DESCRIBE 猜列名，导致列名与 SELECT 的列完全错位
  - 新版直接用 mysql -B 输出的第一行（真实列名），可靠且通用
"""
import json
import os
import subprocess
import BaseHTTPServer
import SocketServer
from datetime import datetime, date

# 数据库密码不写入代码：默认占位符，真实密码通过环境变量注入。
# 例：TROVE_DB_PASSWORD='***' python2 sql_proxy.py
DB_PASSWORD = os.environ.get('TROVE_DB_PASSWORD', '<DB_PASSWORD>')

MYSQL_CMD = [
    'mysql', '-h127.0.0.1', '-P3307', '-uroot', '-p' + DB_PASSWORD,
    'wjr_trove', '-B', '--raw'
    # 注意：去掉了 -N（--skip-column-names），保留第一行列名
]


class SQLHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path != '/query':
            self.send_error(404)
            return

        try:
            length = int(self.headers.getheader('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            sql = data.get('sql', '').strip()

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
            cmd = MYSQL_CMD + ['-e', sql]
            proc = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()

            if proc.returncode != 0:
                self._send_json({'success': False,
                                 'error': stderr.decode('utf-8', 'replace')})
                return

            text = stdout.decode('utf-8', 'replace')
            # 去掉末尾空行，但保留中间空字符串（虽然理论上不会出现）
            lines = text.split('\n')
            while lines and lines[-1] == '':
                lines.pop()

            if not lines:
                # 空结果：给一个空 data，前端能正常处理
                self._send_json({'success': True, 'data': [], 'columns': []})
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
            })

        except Exception as e:
            try:
                self._send_json({'success': False, 'error': str(e)})
            except Exception:
                pass

    def do_GET(self):
        if self.path == '/health':
            self._send_json({'status': 'ok'})
        else:
            self.send_error(404)

    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(self._dumps(data))

    def _dumps(self, obj):
        def default(o):
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            raise TypeError
        return json.dumps(obj, default=default, ensure_ascii=False)


if __name__ == '__main__':
    PORT = 5001
    print('SQL Proxy 启动在 http://0.0.0.0:%d' % PORT)
    server = SocketServer.TCPServer(('0.0.0.0', PORT), SQLHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止')
