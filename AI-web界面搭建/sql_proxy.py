# -*- coding: utf-8 -*-
"""
SQL 查询代理服务 - 用 mysql 命令行实现，无需 MySQLdb
部署在 <SQL_PROXY_HOST> 上
"""
import json
import subprocess
import BaseHTTPServer
import SocketServer
from datetime import datetime, date

MYSQL_CMD = [
    'mysql', '-h127.0.0.1', '-P3307', '-uroot', '-p<DB_PASSWORD>',
    'wjr_trove', '-B', '-N', '--raw'
]

class SQLHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path == '/query':
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
                if not (sql_upper.startswith('SELECT') or sql_upper.startswith('SHOW') or sql_upper.startswith('DESCRIBE')):
                    self._send_json({'success': False, 'error': '仅支持 SELECT / SHOW / DESCRIBE 查询'})
                    return

                # 用 mysql 命令行执行
                cmd = MYSQL_CMD + ['-e', sql]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = proc.communicate()

                if proc.returncode != 0:
                    self._send_json({'success': False, 'error': stderr.decode('utf-8', 'replace')})
                    return

                # 解析结果
                lines = stdout.decode('utf-8', 'replace').strip().split('\n')
                if not lines or lines == ['']:
                    self._send_json({'success': True, 'data': []})
                    return

                # 第一行是列名（-B 参数输出 tab 分隔）
                # 实际 mysql -B -N 没有列名头，需要 DESCRIBE 获取
                # 这里用 DESCRIBE 先获取列名（对 SELECT 语句）
                table = self._extract_table(sql)
                cols = []
                if table:
                    try:
                        desc_cmd = MYSQL_CMD + ['-e', 'DESCRIBE %s' % table]
                        desc_proc = subprocess.Popen(desc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        desc_out, _ = desc_proc.communicate()
                        for line in desc_out.decode('utf-8', 'replace').strip().split('\n'):
                            if line:
                                parts = line.split('\t')
                                if parts:
                                    cols.append(parts[0])
                    except:
                        pass

                # 对于 SHOW TABLES 等命令，使用通用列名
                if not cols:
                    # 根据返回数据的列数生成 col_0, col_1, ...
                    if lines and len(lines) > 0:
                        first_row_cols = len(lines[0].split('\t'))
                        for i in range(first_row_cols):
                            cols.append('col_%d' % i)

                # 解析数据行
                data = []
                for line in lines:
                    if line:
                        values = line.split('\t')
                        row = {}
                        for i, val in enumerate(values):
                            if i < len(cols):
                                row[cols[i]] = val
                            else:
                                row['col_%d' % i] = val
                        data.append(row)

                self._send_json({'success': True, 'data': data})

            except Exception as e:
                self._send_json({'success': False, 'error': str(e)})
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == '/health':
            self._send_json({'status': 'ok'})
        else:
            self.send_error(404)

    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(self._dumps(data))

    def _dumps(self, obj):
        def default(o):
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            raise TypeError
        return json.dumps(obj, default=default)

    def _extract_table(self, sql):
        # 提取表名 - 支持 FROM, DESCRIBE, SHOW COLUMNS FROM 等
        import re
        sql_upper = sql.upper()

        # DESCRIBE tablename
        match = re.search(r'DESCRIBE\s+(\w+)', sql, re.IGNORECASE)
        if match:
            return match.group(1)

        # SHOW COLUMNS FROM tablename
        match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

if __name__ == '__main__':
    PORT = 5001
    print('SQL Proxy 启动在 http://0.0.0.0:%d' % PORT)
    server = SocketServer.TCPServer(('0.0.0.0', PORT), SQLHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止')
