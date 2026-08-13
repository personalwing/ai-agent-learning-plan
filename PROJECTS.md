# 🚀 30天学习计划 - 项目指南

本文档详细说明每周需要完成的项目，包括目标、步骤和验收标准。

---

## 📌 项目概览

| 周次 | 项目名称 | 难度 | 时间 | GitHub项目 |
|------|---------|------|------|-----------|
| Week 1 | micrograd 自动求导 | ⭐⭐ | 1.5h | karpathy/micrograd |
| Week 2 | makemore 字符生成 | ⭐⭐⭐ | 1.5h | karpathy/makemore |
| Week 3 | nanoGPT Part 1 | ⭐⭐⭐⭐ | 1.5h | karpathy/nanoGPT |
| Week 3 | nanoGPT Part 2 | ⭐⭐⭐⭐ | 1.5h | karpathy/nanoGPT |
| Week 4 | Pong Agent | ⭐⭐⭐⭐ | 1.5h | 参考RL文章 |
| Week 4 | 综合项目 | ⭐⭐⭐⭐⭐ | 4.5h | 自选 |

---

## 🔵 第一周：micrograd 项目

### 项目简介
**micrograd** 是Karpathy写的最小化自动求导引擎实现，仅用~100行代码实现了完整的反向传播过程。

### 学习目标
- ✅ 理解计算图 (Computational Graph)
- ✅ 掌握反向传播 (Backpropagation)
- ✅ 实现自动求导 (Autograd)
- ✅ 理解神经��络的数学基础

### 快速开始

```bash
# Step 1: 克隆项目
git clone https://github.com/karpathy/micrograd.git
cd micrograd

# Step 2: 运行演示
python demo.py

# Step 3: 在Jupyter中浏览
jupyter notebook
# 打开 trace_graph.ipynb 查看可视化
```

### 核心概念梳理

**Value类** - 自动微分的核心
```python
class Value:
    def __init__(self, data, _children=(), _op=''):
        self.data = data           # 数值
        self.grad = 0.0            # 梯度
        self._backward = lambda: None  # 反向传播函数
```

**关键操作**：
1. `__add__` - 加法及其反向传播
2. `__mul__` - 乘法及其反向传播
3. `backward()` - 执行反向传播
4. `relu()` - ReLU激活函数

### 手动实现任务

创建 `my_micrograd.py`，实现以下功能：
- [ ] Value 类的基础实现
- [ ] 支持 +, -, *, / 操作
- [ ] 实现 relu 激活函数
- [ ] 完整的反向传播

### 验收标准

- ✅ 能运行官方 demo.py
- ✅ 理解 Value 类设计
- ✅ 手写实现基本功能
- ✅ 测试通过，梯度计算正确

---

## 🟡 第二周：makemore 项目

### 项目简介
**makemore** 展示如何从简单到复杂地构建文本生成模型，最终实现 Transformer。

### 学习目标
- ✅ 掌握数据预处理
- ✅ 理解多种文本生成架构
- ✅ 实现完整的训练管道

### 快速开始

```bash
git clone https://github.com/karpathy/makemore.git
cd makemore

# 按顺序学习
jupyter notebook makemore1.ipynb  # Bigram + MLP
# 然后
jupyter notebook makemore2.ipynb  # 改进版
jupyter notebook makemore5.ipynb  # 高级版本
```

### 关键实现

**数据加载**：
```python
with open('names.txt', 'r') as f:
    words = f.read().splitlines()
chars = sorted(list(set(''.join(words))))
```

**模型架构** - 字符嵌入 → 线性层 → 激活 → 输出：
```python
model = nn.Sequential(
    nn.Embedding(vocab_size, embedding_dim),
    nn.Flatten(),
    nn.Linear(...),
    nn.BatchNorm1d(...),
    nn.Tanh(),
    nn.Linear(..., vocab_size)
)
```

**文本生成**：根据概率分布采样下一个字符

### 手动实现任务

- [ ] 实现数据预处理管道
- [ ] 从零构建神经网络模型
- [ ] 完整的训练循环
- [ ] 文本生成函数

### 验收标准

- ✅ 理解全部5个版本的区别
- ✅ 生成的名字看起来合理
- ✅ 尝试了多个超参数配置
- ✅ 记录了最佳参数组合

---

## 🔴 第三周：nanoGPT 项目

### 项目简介
**nanoGPT** 是完整的 GPT-2 实现，~500 行代码，包含 Transformer 的所有核心组件。

### 学习目标
- ✅ 理解 Transformer 架构
- ✅ 掌握自注意力机制
- ✅ 实现从零到一的 GPT
- ✅ 能在真实数据上训练

### 快速开始

```bash
git clone https://github.com/karpathy/nanoGPT.git
cd nanoGPT

# 准备数据
python data/shakespeare_char/prepare.py

# 训练小模型
python train.py \
    --n_layer=4 \
    --n_head=4 \
    --n_embd=64 \
    --max_iters=100 \
    --eval_interval=50 \
    --compile=False

# 生成文本
python sample.py --start_prompt="ROMEO:" --num_samples=1
```

### 核心概念

**Transformer 块**：
- Token Embedding
- Position Embedding
- Attention Head (多头)
- Feed-Forward Network
- Layer Norm
- Residual Connections

**自注意力**：
```
Query × Key^T / √d → Softmax → × Value
```

### 第3周分阶段计划

**Part 1 (D17-18)**：理解架构
- [ ] 理解 Transformer 结构
- [ ] 学习自注意力原理
- [ ] 分析 nanoGPT 代码结构

**Part 2 (D19-20)**：实现训练
- [ ] 准备数据集
- [ ] 运行训练
- [ ] 生成合理的文本

### 验收标准

- ✅ 能解释自注意力如何工作
- ✅ 成功训练一个小模型
- ✅ 能生成连贯的文本
- ✅ 理解位置编码的作用

---

## 🟣 第四周：强化学习与 Agent

### 周总体目标
- 理解强化学习基础
- 实现简单的 Agent
- 完成综合项目

### Part 1: Pong Agent

```
难度: ⭐⭐⭐⭐
时间: 1.5小时
```

**概念**：
- MDP (Markov Decision Process)
- 策略梯度 (Policy Gradient)
- 折扣回报 (Discounted Return)

**实现**：
```python
# 130行 Pong Agent
# 参考: https://github.com/karpathy/reinforcejs
```

**目标**：
- [ ] 理解 Policy Gradient 算法
- [ ] 实现 Pong Agent
- [ ] 看到模型收敛

### Part 2: 综合项目 (D27-30)

```
难度: ⭐⭐⭐⭐⭐
时间: 4.5小时
```

**可选项目**（选择其一）：

1. **聊天机器人**
   - 基于 nanoGPT 微调
   - 实现简单对话能力
   - 评估响应质量

2. **推荐系统 Agent**
   - 用强化学习优化推荐
   - 基于用户反馈学习
   - 最大化用户满意度

3. **游戏 AI Agent**
   - 扩展 Pong 到其他游戏
   - 实现多目标优化
   - 对比不同算法

4. **文本生成增强**
   - 在 nanoGPT 基础上
   - 添加约束 / 控制
   - 实现主题聚焦生成

---

## 🟤 Deepseek Harness 项目（可作为综合项目）

### 项目简介
**Deepseek Harness（Deepseek-harness）** 是围绕 DeepSeek 生态的运行时与插件系统，包含插件、数据源适配器、UI 客户端与 API 中继等组件。学习并实现一个 harness 插件或运行环境，能帮助你理解 agent/harness 架构、工具调用以及如何扩展 Agent 的能力。

### 学习目标
- ✅ 理解 Deepseek-harness 的整体架构（插件生命周期、数据源、工具调用）
- ✅ 能搭建并运行一个现成的 harness 实例
- ✅ 实现一个简单的插件或数据源适配器
- ✅ 理解安全与资源隔离（沙箱、权限）

### 快速开始（示例仓库）

- 克隆资源列表（推荐先阅读生态清单）：
  - https://github.com/0xsline/awesome-deepseek-harness
- 克隆 harness 源码示例（任选其一开始）：
  - https://github.com/Joe-zhouman/deepseek-harness-src
  - 也可参考桌面/客户端项目：https://github.com/MiniLaba/deepseek-harness-desktop

```bash
# Step 1: 克隆示例仓库
git clone https://github.com/Joe-zhouman/deepseek-harness-src.git
cd deepseek-harness-src

# Step 2: 阅读 README，安装依赖并运行（各仓库说明不同）
# 一般会有类似命令：
# pip install -r requirements.txt 或 npm install
# 然后运行服务： python main.py 或 npm start
```

### 核心任务（建议分三天完成）
1. Day 1 — 理解与运行
   - [ ] 阅读项目 README 与架构文档
   - [ ] 本地启动 harness 实例，确保基础服务可用
   - [ ] 用官方或示例插件执行一次完整流程

2. Day 2 — 插件/适配器开发
   - [ ] 实现一个简单插件（例如：HTTP 数据源、网页抓取器或一个简单工具调用）
   - [ ] 写单元测试验证接口
   - [ ] 在本地 harness 中加载并验证插件功能

3. Day 3 — 安全与集成
   - [ ] 理解并配置插件权限/沙箱策略
   - [ ] 集成一个外部 API（例如搜索或简单 LLM 代理）以增强插件能力
   - [ ] 编写使用说明与 demo 脚本

### 验收标准
- ✅ 本地能启动 harness 并运行至少一个插件
- ✅ 成功实现并加载自定义插件/数据源
- ✅ 提交测试用例覆盖主要接口
- ✅ 写出 1 页的技术总结（运行步骤、架构要点、改进建议）

### 参考资料
- Deepseek 相关仓库搜索结果：https://github.com/search?q=deepseek+in%3Aname&sort=updated&order=desc
- 生态精选（插件/工具/基建）：https://github.com/0xsline/awesome-deepseek-harness

---

## 📊 项目完成检查表

### ✅ Week 1 完成标志
- [ ] 环境搭建成功
- [ ] micrograd 演示运行
- [ ] 理解 Value 类设计
- [ ] 自己实现了反向传播
- [ ] 所有测试通过

### ✅ Week 2 完成标志
- [ ] 理解数据预处理
- [ ] 实现字符生成模型
- [ ] 生成合理的名字
- [ ] 尝试 ≥3 种配置
- [ ] 记录最佳参数

### ✅ Week 3 完成标志
- [ ] 理解 Transformer 结构
- [ ] 理解自注意力机制
- [ ] 成功训练模型
- [ ] 能生成文本
- [ ] 能修改参数进行实验

### ✅ Week 4 完成标志
- [ ] 理解强化学习基础
- [ ] Pong Agent 能运行
- [ ] 选择并完成综合项目
- [ ] 能解释项目设计
- [ ] 有清晰的项目文档

---

## 🎯 学习质量指标

完成每个项目时自评：

```
1. 代码理解度：_____/100%
   我能从零重新写出这个项目吗？

2. 概念掌握度：_____/100%
   我能用简单的语言解释核心原理吗？

3. 动手实现度：_____/100%
   代码有多少是自己写的（非复制粘贴）？

4. 知识迁移度：_____/100%
   我能用这些知识解决其他问题吗？

总体评分：_____/100
```

---

## 💡 调试与优化建议

### 常见问题解决

**问题**：梯度计算不正确
- 用手动计算验证
- 添加 print 语句追踪
- 对比官方实现

**问题**：训练不收敛
- 检查学习率
- 查看数据是否正确加载
- 尝试简化模型

**问题**：代码运行缓慢
- 使用 GPU
- 检查是否有不必要的计算
- 考虑批处理

---

## 📝 项目产出物管理

每个项目应产出：

```
Week_X_Project/
├── code/
│   ├── main.py          # 主要实现
│   ├── utils.py         # 辅助函数
│   └── test.py          # 测试代码
├── notes/
│   ├── learning.md      # 学习笔记
│   └── insights.md      # 关键洞察
├── results/
│   ├── model.pt         # 训练好的模型
│   ├── samples.txt      # 生成样本
│   └── metrics.json     # 性能指标
└── README.md            # 项目总结
```

---

**项目指南版本**: v1.0  
**最后更新**: 2026-07-03  
**维护者**: personalwing
