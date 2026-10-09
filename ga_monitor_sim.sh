#!/bin/bash
#===============================================================================
# ga_monitor_sim.sh — 模拟 openstack-memdb guestagent 的 MongoDB 采集逻辑
#
# 作用: 按 agent 同口径(每5秒一轮、与上轮差值计算)在本地打印全部采集指标,
#       指标名与 agent 上报 VictoriaMetrics 的名字一一对应,
#       用于和云监控值对账 (agent算的 = 云监控应该显示的)
#
# 用法:
#   bash ga_monitor_sim.sh                        # 默认 127.0.0.1:27017
#   CONN="--host 127.0.0.1 --port 27017" bash ga_monitor_sim.sh
#   AUTH="--username xxx --password xxx --authenticationDatabase admin" bash ga_monitor_sim.sh
#
# 输出说明:
#   [ga]   = mongo shell 采集的服务端指标 (每行一个 JSON payload, 与 agent 上报格式同构)
#   [disk] = /proc/diskstats 采集的磁盘 IOPS (对应 mongo.iops.read/write)
#   Ctrl+C 退出
#
# 注意: 首轮只建立基线, 从第 2 轮开始出数; qps/KSCopLatencies 为差值计算,
#       delay_* 单位 ms; count/aggregate 的时延 serverStatus 无对应键, agent 为私有实现,
#       本脚本以 null 输出。
#===============================================================================
set -u
CONN=${CONN:---host 127.0.0.1 --port 27017}
AUTH=${AUTH:-}
INTERVAL=5

#---------------- 磁盘 IOPS (agent 侧来自主机 /proc/diskstats) -----------------
disk_loop() {
    local pr=0 pw=0 line r w
    sleep $INTERVAL   # 等首轮基线
    while true; do
        line=$(awk '$3 !~ /^(loop|ram|fd|sr|dm-)/ {rr+=$4; ww+=$8} END {print rr+0, ww+0}' /proc/diskstats)
        r=${line% *}; w=${line#* }
        if [ "$pr" != "0" ]; then
            echo "[disk] mongo.iops.read=$(( (r - pr) / INTERVAL ))  mongo.iops.write=$(( (w - pw) / INTERVAL ))"
        fi
        pr=$r; pw=$w
        sleep $INTERVAL
    done
}
disk_loop &
DISK_PID=$!
trap 'kill $DISK_PID 2>/dev/null' EXIT

#---------------- 主采集循环 (mongo shell, 复刻 agent 差值逻辑) ------------------
mongo $CONN $AUTH --quiet --norc <<'JSEOF'
var first = true, c = null;

function avg(cur, pre) {                      // (Δlatency_us / Δops) -> ms, 与 agent 一致
    if (!cur || !pre) return null;
    var dn = cur.ops - pre.ops;
    if (dn <= 0) return 0.0;
    return (cur.latency - pre.latency) / dn / 1000;
}
function aggAll(lat) {                        // delay_all = 各类合计
    var t = 0, n = 0;
    ["insert", "queries", "update", "remove", "commands", "getmore"].forEach(function (k) {
        if (lat[k]) { t += lat[k].latency; n += lat[k].ops; }
    });
    return { latency: t, ops: n };
}

var hi = db.hostInfo();                       // 主机内存总量, 用于 memused.percent
var hostMemMB = (hi.system && hi.system.memSizeMB) ? hi.system.memSizeMB : 0;

print("[ga] 基线采集中, 5 秒后开始输出... (Ctrl+C 退出)");
while (true) {
    var s = db.serverStatus();
    var now = new Date().getTime();

    if (!first) {
        var dt = (now - c.t) / 1000;
        var o = s.opcounters, po = c.ops;
        var m = s.metrics.commands || {}, pm = c.mcmds || {};
        var lat = s.opLatencies, plat = c.lat;
        var wt = s.wiredTiger.cache, wtc = c.wt;
        var net = s.network, pnet = c.net;
        var allC = aggAll(lat), allP = aggAll(plat);
        var allAvg = (allC.ops - allP.ops) > 0 ? (allC.latency - allP.latency) / (allC.ops - allP.ops) / 1000 : 0.0;
        var cacheMax = wt["maximum bytes configurable"] || 0;
        var cacheCur = wt["bytes currently in the cache"] || 0;
        var cacheDirty = wt["tracked dirty bytes in the cache"] || 0;
        var req = wt["pages requested from the cache"] || 0, preq = wtc.preq || 0;
        var rinto = wt["pages read into cache"] || 0, printo = wtc.rinto || 0;

        var P = {
            // ---- 请求监控 / 请求量: qps(差值) + nums(累计) ----
            'mongo.qps.query':      (o.query   - po.query)   / dt,
            'mongo.qps.insert':     (o.insert  - po.insert)  / dt,
            'mongo.qps.update':     (o.update  - po.update)  / dt,
            'mongo.qps.delete':     (o.delete  - po.delete)  / dt,
            'mongo.qps.getmore':    (o.getmore - po.getmore) / dt,
            'mongo.qps.command':    (o.command - po.command) / dt,
            'mongo.qps.count':      ((m.count ? m.count.total : 0)          - (pm.count ? pm.count.total : 0))          / dt,
            'mongo.qps.aggregates': ((m.aggregate ? m.aggregate.total : 0)  - (pm.aggregate ? pm.aggregate.total : 0))  / dt,
            'mongo.nums':           o.query + o.insert + o.update + o.delete + o.getmore + o.command,
            'mongo.nums.query': o.query,   'mongo.nums.insert': o.insert,
            'mongo.nums.update': o.update, 'mongo.nums.delete': o.delete,
            'mongo.nums.getmore': o.getmore, 'mongo.nums.command': o.command,
            'mongo.nums.count': (m.count ? m.count.total : 0),
            'mongo.nums.aggregates': (m.aggregate ? m.aggregate.total : 0),
            // ---- 时延监控: opLatencies 差值平均 (ms) ----
            'mongo.KSCopLatencies':           allAvg,
            'mongo.KSCopLatencies.delay_queries':   avg(lat.queries,  plat.queries),
            'mongo.KSCopLatencies.delay_insert':    avg(lat.insert,   plat.insert),
            'mongo.KSCopLatencies.delay_update':    avg(lat.update,   plat.update),
            'mongo.KSCopLatencies.delay_remove':    avg(lat.remove,   plat.remove),
            'mongo.KSCopLatencies.delay_command':   avg(lat.commands, plat.commands),
            'mongo.KSCopLatencies.delay_getmore':   avg(lat.getmore,  plat.getmore),
            'mongo.KSCopLatencies.delay_count':     null,   // agent 私有实现, serverStatus 无此键
            'mongo.KSCopLatencies.delay_aggregate': null,
            // ---- wiredTiger cache ----
            'mongo.wtcache.readinto_b':   (wt["bytes read into cache"]    - wtc.rb) / dt,
            'mongo.wtcache.writtenfrom_b':(wt["bytes written from cache"] - wtc.wb) / dt,
            'mongo.wtcache.used_percent':  cacheMax > 0 ? (cacheCur / cacheMax * 100) : null,
            'mongo.wtcache.dirty_percent': cacheMax > 0 ? (cacheDirty / cacheMax * 100) : null,
            'mongo.wtcache.pages_percent': (req - preq) > 0 ? ((1 - (rinto - printo) / (req - preq)) * 100) : null,  // ≈命中率
            // ---- 网络 ----
            'mongo.network.bytesin':      (net.bytesIn     - pnet.bytesIn)     / dt,
            'mongo.network.bytesout':     (net.bytesOut    - pnet.bytesOut)    / dt,
            'mongo.network.numrequesets': (net.numRequests - pnet.numRequests) / dt,
            'mongo.network.connections':  s.connections.current,
            'mongo.network.connections_percent':
                (s.connections.available > 0) ? (s.connections.current / (s.connections.current + s.connections.available) * 100) : null,
            // ---- 锁 / cursor / TTL ----
            'mongo.lock.readers': s.globalLock.currentQueue.readers,
            'mongo.lock.writers': s.globalLock.currentQueue.writers,
            'mongo.lock.total':   s.globalLock.currentQueue.total,
            'mongo.cursor.open_total': s.metrics.cursor.total.open,
            'mongo.cursor.timeout':    s.metrics.cursor.total.timedOut,
            'mongo.ttl.passes':             s.metrics.ttl.passes,
            'mongo.ttl.deleted_documents':  s.metrics.ttl.deletedDocuments,
            // ---- 活跃/排队请求 ----
            'mongo.ar': s.globalLock.activeClients.total - s.globalLock.activeClients.readers,
            'mongo.aw': s.globalLock.activeClients.writers,
            'mongo.qr': s.globalLock.currentQueue.readers,
            'mongo.qw': s.globalLock.currentQueue.writers,
            // ---- 内存 / 存活 ----
            'mongo.mem.memused.amount':  s.mem.resident / 1024,                       // GB
            'mongo.mem.memused.percent': hostMemMB > 0 ? (s.mem.resident / hostMemMB * 100) : null,
            'mongo.mongo_alive': 1
        };
        print("[ga] " + JSON.stringify(P));
    }

    // 保存本轮 cache (与 agent 的 cache time/count 机制一致)
    c = { t: now, ops: s.opcounters, mcmds: s.metrics.commands, lat: s.opLatencies,
          wt: { rb: wt["bytes read into cache"], wb: wt["bytes written from cache"],
                preq: req, rinto: rinto },
          net: net };
    first = false;
    sleep(5000);
}
JSEOF
