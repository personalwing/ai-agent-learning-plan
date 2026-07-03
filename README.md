# 30天AI Agent学习计划 📚

> 一个系统化的学习路线，用30天时间深入学习AI Agent相关知识。  
> **学习承诺**：每天1.5小时有效学习时间 = 45小时总投入

## 🎯 学习目标

通过学习Andrew Ng、李宏毅、Andrey Karpathy等专家的内容，理解：
- AI Agent的核心概念与架构
- 神经网络基础与深度学习原理
- 大型语言模型(LLM)与Agent的实现
- 实际编码能力与项目实践

---

## 📖 核心学习资源

### 1. **Andrew Ng - AI for Everyone**
- 📺 [Coursera课程](https://www.coursera.org/learn/ai-for-everyone)
- ⏱️ 预期学习时间：3-4小时
- 📝 内容：AI基础概念、应用场景、技术栈
- 💡 特点：易懂、系统、适合入门

### 2. **李宏毅 - AI网课**
- 📺 [李宏毅深度学习课程](https://www.youtube.com/@HungyiLee_NTU)
- ⏱️ 预期学习时间：20-25小时
- 📝 内容：深度学习、RNN/LSTM、强化学习
- 💡 特点：详细讲解、配套练习、中文资源

### 3. **Andrey Karpathy - GitHub Projects**
- 🔗 [个人博客 & 项目](https://github.com/karpathy)
- 📚 核心项目：
  - **micrograd** - 自动梯度计算引擎
  - **makemore** - 字符级文本生成
  - **nanoGPT** - 从零实现GPT
  - **microgpt** - 200行代码的完整GPT
  - char-rnn - 字符级RNN
  - neuraltalk - 图像描述生成

---

## 📅 30天学习计划详情

### **第一周：AI基础与概念 (7.5 小时)**

| 天数 | 主题 | 学习内容 | 时间 | 资源 |
|------|------|---------|------|------|
| D1-2 | AI 基础入门 | AI定义、应用、职业机会 | 1.5h | AI for Everyone (Module 1) |
| D3 | 机器学习原理 | 监督学习、无监督学习基础 | 1.5h | 李宏毅 ML基础 |
| D4 | 数据与特征 | 数据集、特征工程、模型评估 | 1.5h | AI for Everyone (Module 2) |
| D5 | 神经网络入门 | 感知机、反向传播、激活函数 | 1.5h | 李宏毅 NN基础 |
| D6-7 | **实践**：micrograd项目 | 自己实现自动梯度计算 | 1.5h | [Karpathy micrograd](https://github.com/karpathy/micrograd) |

**本周任务**：
- [ ] 完成AI for Everyone Module 1-2
- [ ] 理解反向传播算法
- [ ] 运行micrograd示例代码

---

### **第二周：深度学习与序列模型 (7.5 小时)**

| 天数 | 主题 | 学习内容 | 时间 | 资源 |
|------|------|---------|------|------|
| D8 | 卷积神经网络 (CNN) | 卷积、池化、经典架构(VGG/ResNet) | 1.5h | 李宏毅 CNN |
| D9-10 | RNN与LSTM基础 | 循环神经网络、长短期记忆、序列建模 | 1.5h | 李宏毅 RNN/LSTM |
| D11 | 字符级文本建模 | Char-RNN原理、代码解析 | 1.5h | [Karpathy RNN论文](https://karpathy.ai/posts/) |
| D12-13 | **实践**：Makemore项目 | 实现字符级生成模型 | 1.5h | [Karpathy makemore](https://github.com/karpathy/makemore) |
| D14 | 深度学习实践技巧 | 超参数调优、正则化、训练技巧 | 1.5h | A Recipe for Training Neural Networks |

**本周任务**：
- [ ] 理解RNN和LSTM的数学原理
- [ ] 完成makemore项目 (名字生成)
- [ ] 实现一个字符级文本生成模型

---

### **第三周：Transformer与大型语言模型 (7.5 小时)**

| 天数 | 主题 | 学习内容 | 时间 | 资源 |
|------|------|---------|------|------|
| D15 | Attention 机制 | Self-attention、多头注意力 | 1.5h | 李宏毅 Attention |
| D16 | Transformer架构 | Encoder-Decoder、位置编码、模型设计 | 1.5h | 李宏毅 Transformer |
| D17-18 | **实践**：nanoGPT项目 (Part 1) | GPT架构、tokenizer、数据加载 | 1.5h | [Karpathy nanoGPT](https://github.com/karpathy/nanoGPT) |
| D19-20 | **实践**：nanoGPT项目 (Part 2) | 模型训练、文本生成、超参数调优 | 1.5h | nanoGPT代码解析 |
| D21 | 大型语言模型 (LLM) | GPT演变、对齐、指令微调 | 1.5h | AI for Everyone (LLM模块) |

**本周任务**：
- [ ] 深入理解Transformer结构
- [ ] 完成nanoGPT从零到一的实现
- [ ] 用莎士比亚或其他文本数据集训练一个迷你GPT

---

### **第四周：AI Agent与强化学习 (7.5 小时)**

| 天数 | 主题 | 学习内容 | 时间 | 资源 |
|------|------|---------|------|------|
| D22 | 强化学习基础 | MDP、价值函数、策略梯度 | 1.5h | 李宏毅 强化学习 |
| D23 | Agent的核心概念 | 感知、决策、行动、反馈循环 | 1.5h | AI for Everyone Agent模块 |
| D24 | 从Pong开始 | Policy Gradient、ATARI游戏 | 1.5h | [Karpathy RL博客](https://karpathy.ai/posts/) |
| D25 | **实践**：简单Agent项目 | 实现一个Policy Gradient Agent | 1.5h | 130行Pong代码 |
| D26 | Agent应用场景 | 对话Agent、推荐系统、自主系统 | 1.5h | AI for Everyone 应用案例 |
| D27-30 | **综合项目** | 设计并实现一个完整的AI Agent | 4.5h | 融合所有知识 |

**本周任务**：
- [ ] 理解强化学习核心算法
- [ ] 实现一个简单的Pong游戏Agent
- [ ] 规划综合项目（可选：聊天机器人、推荐系统、游戏AI）

---

## 📚 仓库文件结构

```
ai-agent-learning-plan/
├── README.md                 # 本文件 - 学习计划概览
├── RESOURCES.md             # 详细的学习资源索引
├── PROJECTS.md              # 项目实施指南
├── WEEKLY_TEMPLATE.md       # 周学习追踪模板
├── progress.md              # 总体学习进度追踪
├── notes/                   # 学习笔记目录
│   ├── week1/
│   ├── week2/
│   ├── week3/
│   └── week4/
└── code/                    # 代码实现目录
    ├── week1_micrograd/
    ├── week2_makemore/
    ├── week3_nanogpt/
    └── week4_agent/
```

---

## 💻 开发环境设置

### 必要工具
```bash
# Python版本
Python 3.8+

# 必要库
pip install numpy pytorch matplotlib jupyter

# 推荐编辑器
VS Code 或 PyCharm
```

### 快速启动
```bash
# 克隆学习项目
git clone https://github.com/karpathy/micrograd.git
cd micrograd
python demo.py

# 或使用Jupyter
jupyter notebook
```

---

## 🎓 学习建议

### ✅ 最佳实践
1. **边学边练**：不要只看视频，要敲代码
2. **深度理解**：理解"为什么"而不仅仅是"是什么"
3. **代码复现**：完全从零实现一遍，不要复制粘贴
4. **笔记整理**：记录核心概念和公式
5. **项目导向**：每周完成一个小项目来巩固学习

### ⚠️ 容易犯的错误
- ❌ 只看不练 → ✅ 每天敲至少30分钟代码
- ❌ 跳过数学 → ✅ 理解反向传播、梯度等数学基础
- ❌ 一次全学 → ✅ 遵循计划，循序渐进
- ❌ 忽视调试 → ✅ 学会用print()和debugger

---

## 🚀 进阶挑战（可选）

完成基础计划后的进阶方向：

1. **论文阅读**：阅读Attention is All You Need、BERT、GPT系列论文
2. **项目扩展**：在nanoGPT基础上添加新功能
3. **多模态**：探索视觉-语言模型(ViT、CLIP)
4. **Agent框架**：学习LangChain、AutoGPT等框架
5. **生产部署**：学习模型量化、蒸馏、部署优化

---

## 📝 快速开始

### 第一步：准备环境
```bash
# 克隆本仓库
git clone https://github.com/personalwing/ai-agent-learning-plan.git
cd ai-agent-learning-plan

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\\Scripts\\activate  # Windows

# 安装依赖
pip install numpy torch matplotlib jupyter
```

### 第二步：开始学习
1. 阅读 [RESOURCES.md](./RESOURCES.md) 了解学习资源
2. 查看 [PROJECTS.md](./PROJECTS.md) 了解项目要求
3. 按照 README.md 中的日程表开始学习
4. 使用 [WEEKLY_TEMPLATE.md](./WEEKLY_TEMPLATE.md) 记录进度

### 第三步：每周总结
- 复制周模板到 `notes/week_X/summary.md`
- 记录学习内容、代码和思考
- 提交到GitHub（可选）

---

## 💡 学习理念

> "The only way to learn deep learning is to do deep learning." — Andrey Karpathy

这个计划不是为了让你快速成为专家，而是帮助你：
- 📚 **系统地**学习AI的核心概念
- 💻 **动手实践**而不仅仅理论学习
- 🎯 **目标导向**地完成项目
- 🔄 **持续迭代**和改进
- 🌟 **建立兴趣**和热情

---

## 📋 进度概览

```
Week 1: AI基础 + micrograd        [          ]  0% 
Week 2: 深度学习 + makemore       [          ]  0%
Week 3: Transformer + nanoGPT     [          ]  0%
Week 4: Agent + 综合项目          [          ]  0%

总体进度: 0/30 天
```

---

## 🎉 鼓励

深度学习和AI Agent是一个深邃且迷人的领域。这30天的学习可能会很有挑战，但是：

- 📖 每一个概念的理解都会给你新的视角
- 💡 每一个项目的完成都会增强你的信心
- 🚀 每一次的努力都是在构建你的AI基础

**开始日期**：2026-07-03  
**预期完成日期**：2026-08-02  

**加油！🚀 让我们开始这段AI之旅吧！**

---

**最后更新**: 2026-07-03  
**维护者**: personalwing  
**License**: MIT
