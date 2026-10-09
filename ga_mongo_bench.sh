#!/bin/bash
#===============================================================================
# ga_mongo_bench.sh — MongoDB 全指标压测脚本（覆盖 openstack-memdb guestagent 全部业务监控采集项）
#
# 覆盖采集项对照:
#   请求监控/请求量  mongo.qps.* / mongo.nums.*  -> query/insert/update/delete/command/count/aggregate/getmore
#   时延监控         mongo.KSCopLatencies.delay_* -> 9 类 opLatencies 均产生 ops 增量
#   请求数耗时分布   mongo.KSCopLatencyStats.delay_10ms/50ms/100ms -> 慢查询 worker 产生 >50/100ms 请求
#   活跃/排队请求    mongo.ar/aw/qr/qw           -> 并发 + 全表扫描抬高活跃写/排队
#   globalLock       mongo.lock.readers/writers/total
#   TTL              mongo.ttl.passes/deleted_documents -> TTL 集合 3 秒过期
#   cursor           mongo.cursor.open_total/timeout -> getmore 大游标
#   网络流量/连接数/CPU/内存/磁盘 IOPS/写磁盘数据量 -> 压测自然带动
#   主从延迟         mongo.rs.slavedelay / replica_latency -> 持续写 oplog
#
# 用法:
#   bash ga_mongo_bench.sh [时长秒=300] [mix并发数=6] ["mongo连接参数"]
#   例:  bash ga_mongo_bench.sh 300 6 "--host 127.0.0.1 --port 27017"
# 有认证时: AUTH="--username xxx --password xxx --authenticationDatabase admin" bash ga_mongo_bench.sh
# 保留压测库: KEEP=1 bash ga_mongo_bench.sh
# 注意: 仅压非核心库 ga_bench，不触碰业务库；压测期间 qps 会明显上涨
#===============================================================================
set -u
DUR=${1:-300}
MIXW=${2:-6}
CONN=${3:---host 127.0.0.1 --port 27017}
AUTH=${AUTH:-}
KEEP=${KEEP:-0}
DB=ga_bench
TMP=$(mktemp -d)
MONGO="mongo $CONN $AUTH --quiet"

echo "==> 目标: $CONN   时长: ${DUR}s   mix并发: $MIXW"

#--------------- 1. 准备: 建库/预灌数据/记录基线 -------------------------------
$MONGO <<EOF
var db = db.getSiblingDB("$DB");
db.bench.drop(); db.ttl.drop(); db.mark.drop();
db.bench.createIndex({k:1});
// TTL 索引: 3 秒过期, 让 ttl.passes / ttl.deleted_documents 出数
db.ttl.createIndex({ts:1}, {expireAfterSeconds:3});
var pad = new Array(150).join("x");
var batch = [];
for (var i = 0; i < 50000; i++) {
    batch.push({k: i % 1000, v: Math.random(), nf: Math.random(), s: "pad" + pad});
    if (batch.length >= 5000) { db.bench.insert(batch); batch = []; }
}
if (batch.length) db.bench.insert(batch);
// 记录压测基线(opcounters + opLatencies), 结束时算增量平均时延
var s = db.serverStatus();
db.mark.save({_id: 1, t: new Date(), ops: s.opcounters, lat: s.opLatencies,
              ttl: s.metrics.ttl, cur: s.metrics.cursor.total.open});
print("==> 预灌完成: bench=" + db.bench.count() + " 条, 基线已记录");
EOF

#--------------- 2. 生成 worker 脚本 -------------------------------------------
# mix worker: 每轮覆盖 query/getmore/count/update/command/aggregate/delete/ttl
cat > $TMP/mix.js <<EOF
var db = db.getSiblingDB("$DB");
var end = new Date().getTime() + $DUR * 1000;
while (new Date().getTime() < end) {
    var r = Math.floor(Math.random() * 1000);
    db.bench.find({k: r}).limit(10).toArray();                       // query(索引点查)
    var c = db.bench.find({k: {\$gte: r}}).batchSize(64);            // 触发 getmore
    var n = 0; while (c.hasNext() && n < 256) { c.next(); n++; } c.close();
    db.bench.find({k: {\$lt: r}}).count();                           // count
    db.bench.update({k: r}, {\$inc: {v: 1}});                        // update
    db.runCommand({ping: 1});                                        // command
    db.bench.aggregate([{\$match: {k: {\$lt: 100}}},
                        {\$group: {_id: "\$k", c: {\$sum: 1}}}]).toArray(); // aggregate
    db.bench.remove({k: {\$lt: 3}, v: {\$lt: 0.001}}, {justOne: true}); // delete(低频)
    db.ttl.insert({ts: new Date(), v: Math.random()});               // 短命文档喂 TTL
    sleep(50);
}
EOF

# slow worker: 无索引 COLLSCAN + regex, 产出 >50ms/>100ms 请求, 抬高活跃请求与时延分布
cat > $TMP/slow.js <<EOF
var db = db.getSiblingDB("$DB");
var end = new Date().getTime() + $DUR * 1000;
var pad = new Array(150).join("y");
while (new Date().getTime() < end) {
    db.bench.find({nf: Math.random()}).limit(1).toArray();           // 全表扫描
    db.bench.find({s: {\$regex: pad}}).limit(1).toArray();           // regex 扫描
    db.bench.update({k: Math.floor(Math.random() * 1000)},
                    {\$set: {s: "u" + pad}});                        // 大文档写
    sleep(300);
}
EOF

# insert worker: 批量写, 带动网络流量/磁盘写/IOPS/oplog(主从延迟)
cat > $TMP/ins.js <<EOF
var db = db.getSiblingDB("$DB");
var end = new Date().getTime() + $DUR * 1000;
var pad = new Array(150).join("z");
while (new Date().getTime() < end) {
    var batch = [];
    for (var i = 0; i < 200; i++) {
        batch.push({k: Math.floor(Math.random() * 1000), v: Math.random(),
                    nf: 0.5, s: "ins" + pad});
    }
    db.bench.insert(batch);
    db.bench.remove({k: {\$lt: 2}}, {justOne: true});                // 控制集合不膨胀
    sleep(100);
}
EOF

#--------------- 3. 启动压测 -----------------------------------------------------
PIDS=()
for i in $(seq 1 $MIXW); do
    $MONGO "$DB" $TMP/mix.js  >/dev/null 2>&1 &
    PIDS+=($!)
done
$MONGO "$DB" $TMP/slow.js >/dev/null 2>&1 &
PIDS+=($!)
$MONGO "$DB" $TMP/ins.js  >/dev/null 2>&1 &
PIDS+=($!)

echo "==> 压测中... (workers: ${#PIDS[@]})  每 30s 打一次心跳"
ELAPSED=0
while [ $ELAPSED -lt $DUR ]; do
    sleep 30
    ELAPSED=$((ELAPSED + 30))
    ALIVE=0; for p in "${PIDS[@]}"; do kill -0 $p 2>/dev/null && ALIVE=$((ALIVE+1)); done
    echo "    ${ELAPSED}s / ${DUR}s  存活worker: $ALIVE"
done
wait 2>/dev/null

#--------------- 4. 汇总: 用 opLatencies 增量算各类平均时延(与 agent 同口径) ----
$MONGO <<EOF
var db = db.getSiblingDB("$DB");
var s = db.serverStatus();
var m = db.mark.findOne({_id: 1});
var oc = s.opcounters, o = m.ops, lat = s.opLatencies, ol = m.lat;
var map = {query: "queries", insert: "insert", update: "update",
           delete: "remove", getmore: "getmore", command: "commands"};
print("==================================================================");
print("== 压测期间增量统计 (时延 = Δlatencies_us / Δops, 与 agent 口径一致) ==");
print("==================================================================");
for (var k in map) {
    var latKey = map[k];
    var dn = oc[k] - o[k];
    var dt = lat[latKey] ? (lat[latKey].ops - ol[latKey].ops) : 0;
    var dtime = lat[latKey] ? (lat[latKey].latency - ol[latKey].latency) : 0;
    var avg = dt > 0 ? (dtime / dt / 1000).toFixed(3) + " ms" : "N/A";
    print("  " + k + "\t新增ops=" + dn + "\t平均时延=" + avg);
}
var ttl = s.metrics.ttl, mttl = m.ttl || {passes: 0, deletedDocuments: 0};
print("  ttl.passes 增量=" + (ttl.passes - mttl.passes)
      + "  删除文档增量=" + (ttl.deletedDocuments - mttl.deletedDocuments)
      + "  cursor打开=" + (s.metrics.cursor.total.open - (m.cur || 0)));
print("==================================================================");
EOF

#--------------- 5. 清理 ---------------------------------------------------------
if [ "$KEEP" != "1" ]; then
    $MONGO <<EOF
db.getSiblingDB("$DB").dropDatabase();
print("==> 已清理压测库 $DB");
EOF
else
    echo "==> KEEP=1, 压测库 $DB 已保留"
fi
rm -rf $TMP
echo "==> 压测结束. 建议立即到云监控看: qps 各分项/时延监控 9 项/耗时分布/活跃请求/TTL 应全部出数"
