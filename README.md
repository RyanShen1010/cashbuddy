# CashBuddy

大学生理财陪伴 AI 搭子 Demo。

核心定位：

> 大学生真正缺少的不是理财工具，而是一个愿意长期陪伴他们成长的理财搭子。

## 功能

- 消费分析与现金流诊断：分析生活费去向、识别高风险消费和情绪消费
- 攒钱目标规划：拆解目标金额、生成周计划和每日预算
- 消费与理财风险守护：购买前分析现金流、给冷静期和替代方案，并围绕应急金、风险认知、反跟风做金融素养启蒙
- Companion Agent：统一朋友式表达、长期记忆感和陪伴感

## 赛题贴合点

CashBuddy 面向在校大学生的完整资金管理链路：

1. 生活费、兼职收入、奖学金等可支配资金进入账户
2. 消费分析 Agent 帮用户看见钱花到哪里
3. 攒钱规划 Agent 把长期目标拆成每周可执行计划
4. Risk Guard Agent 与 Finance Literacy Agent 共同完成消费风险守护和非营销型理财启蒙，帮助用户建立应急储蓄意识和风险认知

产品不做专业投资平台，不推荐具体金融产品，而是作为轻量化、陪伴式、校园场景友好的理财搭子。

## 快速运行

```bash
cd CashBuddy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

浏览器打开 Streamlit 输出的本地地址，通常是：

```text
http://localhost:8501
```

## DeepSeek API

本 Demo 按赛题要求支持 DeepSeek API。没有 API Key 时，会自动使用本地规则化 Agent 回复，适合比赛现场稳定演示。

如需接入 DeepSeek：

```bash
export DEEPSEEK_API_KEY="你的 key"
streamlit run app.py
```

Streamlit Cloud 部署时可在 App settings 的 Secrets 中加入：

```toml
DEEPSEEK_API_KEY = "你的 key"
```

默认模型为 `deepseek-chat`。如需调整：

```bash
export DEEPSEEK_MODEL="deepseek-chat"
```

DeepSeek API 使用 OpenAI 兼容格式，应用内通过 `openai` Python SDK 设置 `base_url="https://api.deepseek.com"` 调用。

## Streamlit Cloud 部署

1. 新建 GitHub Repo
2. 上传 `app.py`、`requirements.txt`、`.streamlit/config.toml`
3. 打开 [Streamlit Community Cloud](https://share.streamlit.io/)
4. 连接 GitHub Repo
5. Main file path 填写 `app.py`
6. Deploy

## 比赛讲解重点

- 不做专业金融产品，不推荐投资产品
- 用 Prompt Routing 实现轻量 Multi-Agent
- 重点展示陪伴感、长期记忆感和大学生真实消费场景
- 最终展示 3 项核心能力：消费现金流诊断、攒钱目标规划、消费与理财风险守护
- 消费与理财风险守护是最大亮点：下单前冷静干预 + 应急金优先 + 反盲目跟风 + 风险先于收益

## 交付物建议

```text
CashBuddy/
├── app.py
├── requirements.txt
├── prompts.md
├── README.md
├── app_screenshots/
├── PPT.pdf
├── demo.mp4
├── 二维码.png
├── architecture.png
├── flowchart.png
└── testing_results.png
```
