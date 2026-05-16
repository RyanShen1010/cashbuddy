import os
import re
from datetime import datetime

import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


st.set_page_config(
    page_title="CashBuddy",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="collapsed",
)


DEFAULT_MEMORY = {
    "goal": "攒钱买 iPad",
    "goal_amount": 3000,
    "goal_months": 3,
    "monthly_budget": 4000,
    "current_saving": 900,
    "emergency_fund": 500,
    "finance_level": "理财小白",
    "risk_level": "冲动消费偏高",
    "cashflow_status": "本月现金流正常",
    "spending_hotspot": "外卖 / 奶茶 / 数码冲动购",
    "spending_tip": "先稳住月底现金流，再做奖励型消费。",
    "goal_weekly": 250,
    "goal_daily": 33,
    "goal_tip": "周一先存一笔，周日轻复盘。",
    "guard_item": "暂无待冷静消费",
    "guard_action": "遇到大额消费先等 24 小时",
    "emergency_target": 2000,
    "finance_tip": "先保障生活费，再做低风险学习。",
    "pending_allocation": None,
    "last_completed_action": "还没有执行新的攒钱动作",
    "last_focus": "控制奶茶、外卖和电子产品冲动消费",
}


AGENT_PROMPTS = {
    "Spending Analyst Agent": """
你是 CashBuddy 的大学生理财陪伴 AI，负责消费分析。
请分析用户消费情况：
1. 找出主要消费问题
2. 识别冲动消费和情绪消费
3. 给出省钱建议
4. 用朋友式语气表达
5. 不要说教
6. 保持轻松陪伴感
""",
    "Goal Planner Agent": """
你是 CashBuddy 的大学生理财规划 AI，负责攒钱规划。
请根据用户目标：
1. 拆解攒钱周期
2. 给每周建议
3. 保持鼓励语气
4. 给出可执行计划
5. 输出清晰结构
""",
    "Risk Guard Agent": """
你是 CashBuddy 的大学生消费冷静助手，负责冲动消费干预。
用户想购买商品时：
1. 分析是否影响攒钱目标
2. 判断是否属于冲动消费
3. 给冷静期建议
4. 提供更合理替代方案
5. 不要强硬
6. 保持朋友聊天风格
""",
    "Finance Literacy Agent": """
你是 CashBuddy 的大学生入门理财陪伴 AI，负责金融素养启蒙。
请帮助理财小白用户：
1. 建立应急储蓄意识
2. 解释基础理财概念
3. 识别盲目跟风和高风险投资
4. 给出校园场景下的低门槛学习路径
5. 不推荐具体金融产品，不承诺收益
6. 用朋友式、非营销的语气表达
""",
    "Companion Agent": """
你是 CashBuddy 的陪伴型 Agent。
你的任务是让回复像一个长期陪伴大学生成长的理财搭子：
温和、具体、有记忆感，不制造焦虑，不推销金融产品。
""",
}


EXAMPLE_QUESTIONS = [
    "我这个月生活费4000，现在只剩500了",
    "我想3个月攒3000买iPad",
    "我有奖学金2000，想买iPhone17还是先理财？",
]


def init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "agent": "Companion Agent",
                "content": "嗨，我是 CashBuddy。今天我可以帮你看消费、拆攒钱计划，也可以在你想冲动下单前陪你冷静 3 分钟。",
            }
        ]
    if "memory" not in st.session_state:
        st.session_state.memory = DEFAULT_MEMORY.copy()
    if "latest_agent" not in st.session_state:
        st.session_state.latest_agent = "Companion Agent"


def money_number(text):
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb|RMB)?", text)
    return [float(item) for item in matches]


def route_agent(user_input):
    text = user_input.lower()
    risk_keywords = ["买", "下单", "剁手", "要不要", "该不该", "iphone", "ipad", "switch", "电脑", "球鞋", "演唱会"]
    goal_keywords = ["攒", "存", "目标", "计划", "预算", "旅行", "旅游", "考研", "买iPad".lower()]
    finance_keywords = [
        "理财",
        "投资",
        "基金",
        "股票",
        "收益",
        "亏",
        "风险",
        "奖学金",
        "兼职",
        "应急",
        "备用金",
        "跟风",
    ]

    if is_completion_message(text):
        return "Finance Literacy Agent"
    if any(keyword in text for keyword in finance_keywords):
        return "Finance Literacy Agent"
    if any(keyword in text for keyword in goal_keywords) and re.search(r"\d|个月|周|目标|计划|预算", text):
        return "Goal Planner Agent"
    if any(keyword in text for keyword in risk_keywords):
        return "Risk Guard Agent"
    if any(keyword in text for keyword in goal_keywords):
        return "Goal Planner Agent"
    return "Spending Analyst Agent"


def update_memory(user_input, agent):
    memory = st.session_state.memory
    nums = money_number(user_input)

    if is_completion_message(user_input):
        apply_pending_allocation(memory)
        return

    if agent == "Goal Planner Agent":
        memory["goal"] = infer_goal(user_input) or memory["goal"]
        if nums:
            memory["goal_amount"] = int(max(nums))
        month_match = re.search(r"(\d+)\s*个?月", user_input)
        if month_match:
            memory["goal_months"] = int(month_match.group(1))
        weeks = max(memory["goal_months"] * 4, 1)
        memory["goal_weekly"] = round(memory["goal_amount"] / weeks)
        memory["goal_daily"] = round(memory["goal_amount"] / max(memory["goal_months"] * 30, 1))
        memory["goal_tip"] = f"每周先存 {memory['goal_weekly']} 元，剩下用少点外卖补齐。"
        memory["last_focus"] = f"围绕「{memory['goal']}」稳定攒钱"

    if agent == "Risk Guard Agent":
        item = extract_item(user_input)
        memory["risk_level"] = "正在观察大额冲动消费"
        memory["cashflow_status"] = "大额消费会挤压现金流"
        memory["spending_hotspot"] = item
        memory["spending_tip"] = f"先把「{item}」放进 24 小时冷静期。"
        memory["guard_item"] = item
        memory["guard_action"] = "先收藏不付款，明天同一时间再决定"
        memory["last_focus"] = "先冷静，再决定是否下单"

    if agent == "Finance Literacy Agent":
        memory["finance_level"] = "正在建立入门理财认知"
        memory["risk_level"] = "需要避免盲目跟风"
        memory["cashflow_status"] = "先分清生活费、应急金和学习预算"
        memory["guard_item"] = extract_item(user_input)
        memory["guard_action"] = "先建应急金，再用小额学习预算观察"
        memory["finance_tip"] = "不懂不买，不急用的钱才适合学习理财。"
        memory["last_focus"] = "先建应急金，再学习低风险理财知识"
        if nums:
            available = int(max(nums))
            memory["emergency_target"] = max(round(memory["monthly_budget"] * 0.5), 1000)
            allocation = build_allocation_plan(available, memory)
            memory["pending_allocation"] = allocation
            memory["guard_action"] = (
                f"待执行：应急金 +{allocation['emergency_add']} 元，"
                f"{memory['goal']} +{allocation['goal_add']} 元"
            )
            memory["spending_tip"] = f"{available} 元可支配资金先分成生活、应急、目标三份。"

    if agent == "Spending Analyst Agent" and len(nums) >= 2:
        memory["monthly_budget"] = int(max(nums))
        memory["current_saving"] = int(min(nums))
        memory["risk_level"] = "月底现金流紧张"
        spent = max(memory["monthly_budget"] - memory["current_saving"], 0)
        spent_rate = round(spent / memory["monthly_budget"] * 100) if memory["monthly_budget"] else 0
        daily_budget = max(memory["current_saving"] // 10, 20)
        memory["cashflow_status"] = f"已花约 {spent_rate}%，剩余 {memory['current_saving']} 元"
        memory["spending_hotspot"] = infer_spending_hotspot(user_input)
        memory["spending_tip"] = f"接下来每天尽量控制在 {daily_budget} 元左右。"
        memory["emergency_target"] = max(round(memory["monthly_budget"] * 0.5), 1000)


def infer_spending_hotspot(text):
    hotspots = []
    for keyword in ["外卖", "奶茶", "打车", "游戏", "衣服", "球鞋", "数码", "电子产品", "演唱会", "聚餐"]:
        if keyword in text:
            hotspots.append(keyword)
    if hotspots:
        return " / ".join(hotspots[:3])
    return "外卖 / 奶茶 / 临时购物"


def is_completion_message(text):
    completion_keywords = ["照做", "按你说", "按照你", "已经", "完成", "执行", "分配好了", "存好了", "转进", "转入"]
    return any(keyword in text for keyword in completion_keywords)


def build_allocation_plan(amount, memory):
    emergency_target = max(round(memory["monthly_budget"] * 0.5), 1000)
    emergency_gap = max(emergency_target - memory["emergency_fund"], 0)
    learning_amount = max(round(amount * 0.1), 0)
    emergency_add = min(round(amount * 0.4), emergency_gap)
    goal_add = max(amount - emergency_add - learning_amount, 0)

    if emergency_gap == 0:
        goal_add += emergency_add
        emergency_add = 0

    return {
        "source_amount": amount,
        "emergency_add": emergency_add,
        "goal_add": goal_add,
        "learning_amount": learning_amount,
    }


def apply_pending_allocation(memory):
    allocation = memory.get("pending_allocation")
    if not allocation:
        memory["last_completed_action"] = "收到你的更新，但当前没有待执行的分配方案"
        memory["guard_action"] = "可以告诉我金额，我再帮你更新卡片"
        memory["finance_tip"] = "下次说“我有 2000 元奖学金，帮我分配”，我会先生成待执行方案。"
        return

    memory["emergency_fund"] = min(
        memory["emergency_fund"] + allocation["emergency_add"],
        memory["emergency_target"],
    )
    memory["current_saving"] = min(
        memory["current_saving"] + allocation["goal_add"],
        memory["goal_amount"],
    )
    progress = min(round(memory["current_saving"] / memory["goal_amount"] * 100), 100)
    memory["finance_level"] = "已完成一次资金分配"
    memory["risk_level"] = "执行力良好，继续稳住"
    memory["cashflow_status"] = "奖学金已完成分配"
    memory["spending_tip"] = f"这次没有乱花，{memory['goal']} 进度已经到 {progress}%。"
    memory["goal_tip"] = f"刚刚为 {memory['goal']} 新增 {allocation['goal_add']} 元，继续保持。"
    memory["guard_item"] = f"{allocation['source_amount']} 元奖学金分配"
    memory["guard_action"] = "已执行：应急金、目标攒钱、学习预算分开管理"
    memory["finance_tip"] = f"应急金新增 {allocation['emergency_add']} 元，学习预算预留 {allocation['learning_amount']} 元。"
    memory["last_completed_action"] = (
        f"已把 {allocation['source_amount']} 元分配完成："
        f"应急金 +{allocation['emergency_add']} 元，"
        f"{memory['goal']} +{allocation['goal_add']} 元，"
        f"学习预算 {allocation['learning_amount']} 元"
    )
    memory["pending_allocation"] = None


def infer_goal(text):
    patterns = [
        r"攒\d+(?:\.\d+)?(?:元|块)?买([^，。,.!！\s]+)",
        r"买([^，。,.!！\s]+)",
        r"去([^，。,.!！\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            target = match.group(1)
            if target:
                return f"攒钱买{target}"
    return None


def get_deepseek_api_key():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("DEEPSEEK_API_KEY", None)
        except Exception:
            api_key = None
    return api_key


def use_deepseek_response(user_input, agent):
    api_key = get_deepseek_api_key()
    if not api_key or OpenAI is None:
        return None

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    memory = st.session_state.memory
    system_prompt = f"""
{AGENT_PROMPTS['Companion Agent']}

当前子 Agent：
{AGENT_PROMPTS[agent]}

用户记忆：
{memory}

输出要求：
- 中文
- 朋友聊天语气
- 结构清晰，但不要像银行报告
- 不提供投资建议，不推荐金融产品
- 结尾给一个很小、今天就能做的行动
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def local_agent_response(user_input, agent):
    memory = st.session_state.memory
    if is_completion_message(user_input):
        return completion_reply(memory)
    if agent == "Finance Literacy Agent":
        return finance_literacy_reply(user_input, memory)
    if agent == "Risk Guard Agent":
        return risk_guard_reply(user_input, memory)
    if agent == "Goal Planner Agent":
        return goal_planner_reply(user_input, memory)
    return spending_analyst_reply(user_input, memory)


def spending_analyst_reply(user_input, memory):
    nums = money_number(user_input)
    monthly_budget = int(max(nums)) if nums else memory["monthly_budget"]
    left = int(min(nums)) if len(nums) >= 2 else memory["current_saving"]
    spent = max(monthly_budget - left, 0)
    spent_rate = round(spent / monthly_budget * 100) if monthly_budget else 0
    daily_budget = max(left // 10, 20)

    return f"""
我帮你快速捋了一下：这个月生活费大概 **{monthly_budget} 元**，现在还剩 **{left} 元**，也就是已经花掉约 **{spent_rate}%**。

**我看到的消费信号**
- 现金流有点紧，接下来每一天最好控制在 **{daily_budget} 元左右**
- 高风险区大概率在外卖、奶茶、打车和临时购物这些“当下很爽”的支出
- 这不像你不会理财，更像是没有一个人在旁边帮你及时按暂停键

**这周先这样做**
1. 给外卖设一个上限：本周最多 2 次
2. 奶茶改成“想喝先等 20 分钟”，还想喝再买
3. 每天睡前记 3 笔最大支出，不用记全账，只抓大头

顺便记一下，你之前的重点是 **{memory['last_focus']}**。我们先把月底稳住，不追求完美，先别让余额继续自由落体。
"""


def goal_planner_reply(user_input, memory):
    nums = money_number(user_input)
    goal_amount = int(max(nums)) if nums else memory["goal_amount"]
    month_match = re.search(r"(\d+)\s*个?月", user_input)
    months = int(month_match.group(1)) if month_match else memory["goal_months"]
    weeks = max(months * 4, 1)
    weekly = round(goal_amount / weeks)
    daily = round(goal_amount / (months * 30))
    auto_save = max(round(weekly * 0.6), 1)
    flexible_save = weekly - auto_save
    goal = infer_goal(user_input) or memory["goal"]

    return f"""
可以，这个目标很适合拆成一个“不会太痛苦”的计划。你现在的目标是：**{goal}，{months} 个月攒 {goal_amount} 元**。

**拆解后长这样**
- 每周目标：**{weekly} 元**
- 每日参考预算：每天少花或存下 **{daily} 元**
- 自动攒钱：每周先存 **{auto_save} 元**
- 弹性补齐：周末再补 **{flexible_save} 元**，来自少点一次外卖/少一次冲动小单

**执行节奏**
1. 周一先转入目标账户，不靠意志力硬扛
2. 周三看一次进度，只看差多少，不批评自己
3. 周日复盘：如果没完成，下周只加 10%，别突然上强度

这件事的关键不是你每天都很自律，而是让计划足够轻，轻到你愿意一直做。今天的小动作：先给这个目标起个名字，比如“iPad 基金”。
"""


def risk_guard_reply(user_input, memory):
    item = extract_item(user_input)
    monthly_budget = memory["monthly_budget"]
    current_saving = memory["current_saving"]
    goal_amount = memory["goal_amount"]
    goal = memory["goal"]

    return f"""
先不急着拦你，我陪你把这笔 **{item}** 放到现金流里看一下。

**冷静判断**
- 你目前的月预算记忆是 **{monthly_budget} 元**
- 最近现金流余量大约 **{current_saving} 元**
- 你还有一个目标：**{goal}（目标 {goal_amount} 元）**

如果这笔购买超过你当前余量的 50%，它大概率会直接挤压你的攒钱计划。不是不能买，而是现在买可能会让后面的生活费变得很紧。

**我建议你做一个 24 小时冷静期**
1. 先把商品放进收藏夹，不付款
2. 明天同一时间再问自己：它是“需要”，还是“想奖励一下自己”
3. 如果还想买，先找一个替代方案：二手、分期前总成本、旧设备再撑 1 个月、或者降低配置

**更稳的替代方案**
- 如果是电子产品：先查教育优惠/二手平台/上一代机型
- 如果是情绪奖励：把预算压到 100 元以内，换成一顿好吃的或一次短途放松
- 如果真的刚需：我们可以一起重排你的 {goal} 计划，不让它直接崩掉

我的建议是：今天先别付款。你不是不能拥有它，只是别让“现在就要”替你做决定。
"""


def finance_literacy_reply(user_input, memory):
    nums = money_number(user_input)
    available = int(max(nums)) if nums else memory["current_saving"]
    emergency_target = max(round(memory["monthly_budget"] * 0.5), 1000)
    starter_amount = max(round(available * 0.2), 100)
    item = extract_item(user_input)
    purchase_note = ""
    if any(keyword in user_input.lower() for keyword in ["买", "下单", "iphone", "ipad", "电脑"]):
        purchase_note = f"""

**关于「{item}」这笔消费**
- 如果它会动用你的应急金或下个月生活费，先放进 24 小时冷静期
- 如果它是刚需，先比较教育优惠、二手、上一代型号，再决定
- 如果它只是奖励自己，建议先给奖励预算设上限，不让它吃掉你的目标攒钱
"""
    allocation = memory.get("pending_allocation")
    allocation_note = ""
    if allocation:
        allocation_note = f"""

**我建议这笔 {allocation['source_amount']} 元先这样分**
- 应急备用：**{allocation['emergency_add']} 元**
- {memory['goal']}：**{allocation['goal_add']} 元**
- 理财学习预算：**{allocation['learning_amount']} 元**

如果你确认已经这么做了，直接告诉我“我已经按你的分配照做了”，我会把右侧卡片里的应急金和攒钱进度同步更新。
"""

    return f"""
这个问题很适合认真一点，但不用紧张。你现在不是要立刻变成“会投资的人”，而是先建立一个不会被带节奏的理财底盘。

**先给你一个校园版顺序**
1. 先留应急金：目标先放到 **{emergency_target} 元**，用来应对临时买书、看病、设备维修这类突发支出
2. 再做现金流：生活费、兼职收入、奖学金分开看，别把下个月饭钱拿去冒险
3. 最后才学习理财：先理解风险、流动性、收益，不急着追热门

**如果你现在有 {available} 元可支配**
- 建议最多拿 **{starter_amount} 元** 做“学习预算”，先用于观察和学习，不追求赚钱
- 其余部分优先补应急金和你的目标：**{memory['goal']}**
- 看到“稳赚、高收益、同学都买了”这类话，先当作风险信号

**理财小白最该避开的坑**
- 跟风买自己讲不清的产品
- 只看收益截图，不看亏损可能
- 为了投资影响生活费和学业安排
- 把短期要用的钱放进波动大的地方
{purchase_note}
{allocation_note}

今天的小任务很简单：把你的钱分成 3 个小口袋：**日常生活、应急备用、目标攒钱**。等这三个口袋稳了，再谈入门理财会踏实很多。
"""


def completion_reply(memory):
    return f"""
收到，已经帮你把这次动作记到账上了。

**本次更新**
- {memory['last_completed_action']}
- 现在 {memory['goal']} 已攒到 **{memory['current_saving']} / {memory['goal_amount']} 元**
- 应急金现在是 **{memory['emergency_fund']} / {memory['emergency_target']} 元**

这一步很关键：你不是只听了建议，而是真的把钱分好了。右侧卡片也已经同步更新，可以继续用它盯进度。
"""


def extract_item(text):
    cleaned = re.sub(r"我想|我该不该|要不要|买|下单|这个|那个", "", text)
    cleaned = cleaned.strip(" ，。,.!！?")
    return cleaned or "这件东西"


def agent_response(user_input):
    agent = route_agent(user_input)
    update_memory(user_input, agent)
    if is_completion_message(user_input):
        response = local_agent_response(user_input, agent)
    else:
        response = use_deepseek_response(user_input, agent) or local_agent_response(user_input, agent)
    st.session_state.latest_agent = agent
    return agent, response


def render_css():
    st.markdown(
        """
<style>
:root {
  --mint: #42c7b8;
  --blue: #3d8bff;
  --ink: #172033;
  --muted: #667085;
  --line: #e7eef7;
  --soft: #f5fbfb;
}
.stApp {
  background: linear-gradient(180deg, #f7fcff 0%, #ffffff 42%, #f7fbf9 100%);
  color: var(--ink);
}
[data-testid="stHeader"] { background: rgba(255,255,255,0); }
.hero {
  padding: 30px 4px 12px 4px;
}
.brand-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--mint), var(--blue));
  color: #fff;
  font-size: 24px;
  font-weight: 800;
}
.title {
  font-size: 42px;
  font-weight: 850;
  letter-spacing: 0;
  margin: 0;
}
.slogan {
  margin: 8px 0 0 0;
  color: var(--muted);
  font-size: 18px;
}
.metric-card, .feature-card, .memory-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255,255,255,0.86);
  padding: 18px;
  box-shadow: 0 12px 30px rgba(31, 70, 106, 0.06);
}
.feature-card h3, .metric-card h3, .memory-card h3 {
  font-size: 16px;
  margin: 0 0 8px 0;
}
.feature-card p, .memory-card p {
  color: var(--muted);
  margin: 0;
  line-height: 1.55;
}
.agent-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: #e9f8f6;
  color: #087a6f;
  border: 1px solid #cfefeb;
  font-size: 13px;
  margin-bottom: 10px;
}
.chat-shell {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  background: rgba(255,255,255,0.92);
}
.small-note {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.45;
}
.progress-track {
  height: 10px;
  border-radius: 999px;
  background: #e7eef7;
  overflow: hidden;
}
.progress-fill {
  height: 10px;
  width: 30%;
  background: linear-gradient(90deg, var(--mint), var(--blue));
}
.stButton > button {
  border-radius: 8px;
  border: 1px solid var(--line);
  background: #ffffff;
}
.stButton > button:hover {
  border-color: var(--mint);
  color: #087a6f;
}
@media (max-width: 768px) {
  .title { font-size: 32px; }
  .slogan { font-size: 16px; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_hero():
    st.markdown(
        """
<section class="hero">
  <div class="brand-row">
    <div class="logo">¥</div>
    <div>
      <h1 class="title">CashBuddy</h1>
      <p class="slogan">陪你一起攒下人生第一桶金</p>
    </div>
  </div>
</section>
""",
        unsafe_allow_html=True,
    )


def render_feature_cards():
    col1, col2, col3 = st.columns(3)
    cards = [
        ("消费分析与现金流诊断", "看懂生活费去哪了，识别外卖、奶茶、打车和情绪消费。"),
        ("攒钱目标规划", "把想买 iPad、旅行、考研预算拆成每周能做到的小目标。"),
        ("消费与理财风险守护", "下单前冷静 24 小时，并从应急金、风险认知和反跟风开始做理财启蒙。"),
    ]
    for col, (title, desc) in zip([col1, col2, col3], cards):
        with col:
            st.markdown(f'<div class="feature-card"><h3>{title}</h3><p>{desc}</p></div>', unsafe_allow_html=True)


def render_sidebar_cards():
    memory = st.session_state.memory
    progress = min(int(memory["current_saving"] / memory["goal_amount"] * 100), 100)
    emergency_progress = min(int(memory["emergency_fund"] / max(memory["emergency_target"], 1) * 100), 100)
    st.markdown(
        f"""
<div class="memory-card">
  <h3>消费分析卡片</h3>
  <p>本月预算：{memory['monthly_budget']} 元</p>
  <p>现金流状态：{memory['cashflow_status']}</p>
  <p>高风险消费：{memory['spending_hotspot']}</p>
  <p>风险状态：{memory['risk_level']}</p>
  <p>AI 提醒：{memory['spending_tip']}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown(
        f"""
<div class="memory-card">
  <h3>攒钱目标卡片</h3>
  <p>当前目标：{memory['goal']}</p>
  <p>已攒：{memory['current_saving']} / {memory['goal_amount']} 元</p>
  <div class="progress-track"><div class="progress-fill" style="width:{progress}%"></div></div>
  <p style="margin-top:10px;">周计划：每周存 {memory['goal_weekly']} 元</p>
  <p>每日参考：少花或存下 {memory['goal_daily']} 元</p>
  <p>AI 提醒：{memory['goal_tip']}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown(
        f"""
<div class="memory-card">
  <h3>理财安全卡片</h3>
  <p>当前阶段：{memory['finance_level']}</p>
  <p>正在观察：{memory['guard_item']}</p>
  <p>应急金：{memory['emergency_fund']} / {memory['emergency_target']} 元</p>
  <div class="progress-track"><div class="progress-fill" style="width:{emergency_progress}%"></div></div>
  <p style="margin-top:10px;">守护动作：{memory['guard_action']}</p>
  <p>反跟风提醒：不懂、不急用、不承诺收益。</p>
  <p>AI 提醒：{memory['finance_tip']}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    if memory.get("pending_allocation"):
        if st.button("我已按分配照做", use_container_width=True):
            handle_user_message("我已经按你的分配照做了")
            st.rerun()
    st.write("")
    st.caption("Demo 记忆为伪实现，用于呈现长期陪伴感。")


def render_chat():
    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    st.markdown(f'<span class="agent-pill">当前路由：{st.session_state.latest_agent}</span>', unsafe_allow_html=True)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                st.caption(message.get("agent", "Companion Agent"))
            st.markdown(message["content"])

    st.markdown("</div>", unsafe_allow_html=True)


def quick_question_buttons():
    cols = st.columns(3)
    labels = ["消费现金流诊断", "攒钱目标规划", "消费与理财守护"]
    prompts = EXAMPLE_QUESTIONS
    for col, label, prompt in zip(cols, labels, prompts):
        with col:
            if st.button(label, use_container_width=True):
                handle_user_message(prompt)
                st.rerun()


def handle_user_message(user_input):
    st.session_state.messages.append({"role": "user", "content": user_input})
    agent, response = agent_response(user_input)
    st.session_state.messages.append({"role": "assistant", "agent": agent, "content": response})


def render_architecture():
    st.subheader("Agent 架构")
    st.markdown(
        """
```mermaid
flowchart LR
    U[大学生用户输入] --> R[Prompt Router]
    R --> C[Companion Agent]
    R --> S[Spending Analyst Agent]
    R --> G[Goal Planner Agent]
    R --> K[Risk Guard Agent]
    R --> F[Finance Literacy Agent]
    C --> M[伪长期记忆]
    S --> O[朋友式回复]
    G --> O
    K --> O
    F --> O
    M --> O
```
"""
    )


def main():
    init_state()
    render_css()
    render_hero()
    render_feature_cards()
    st.write("")

    tab_chat, tab_arch = st.tabs(["Demo 聊天", "Agent 架构"])
    with tab_chat:
        left, right = st.columns([1.7, 1], gap="large")
        with left:
            quick_question_buttons()
            render_chat()
            user_input = st.chat_input("输入你的消费/攒钱/想买的东西，比如：我想买 iPhone17")
            if user_input:
                handle_user_message(user_input)
                st.rerun()
        with right:
            render_sidebar_cards()

    with tab_arch:
        render_architecture()
        st.markdown(
            f"""
**当前 Demo 状态**

- 运行时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}
- AI 模式：{"DeepSeek API" if get_deepseek_api_key() else "本地规则回复"}
- DeepSeek 模型：{os.getenv("DEEPSEEK_MODEL", "deepseek-chat")}
- 路由逻辑：理财/投资/基金/风险/奖学金 → Finance Literacy；买/下单/该不该 → Risk Guard；攒钱/计划/预算 → Goal Planner；其他 → Spending Analyst
"""
        )


if __name__ == "__main__":
    main()
