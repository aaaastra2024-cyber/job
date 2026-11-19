"""数据结构与常量。字段含义以 docs/设计方案.md 第 3.3 节为准。"""

LEVELS = ["硬门槛", "核心能力", "加分项", "软性要求"]
HARD_TYPES = ["学历", "届别", "城市", "到岗天数", "实习时长"]
SKILL_LEVELS = ["没学过", "了解", "会用", "熟练"]
MATCH_STATUSES = ["符合", "部分符合", "不符合", "信息不足"]
VERDICTS = ["建议投递", "补充后投递", "谨慎投递"]
APP_STATUSES = ["待投", "已投", "笔试", "面试", "拒绝", "录用"]
DEGREES = ["大专", "本科", "硕士", "博士"]
MAJOR_CATEGORIES = ["理工类", "经管类", "管理类", "文史类", "艺术类", "其他"]

DAILY_LIMIT = 10  # 每人每日分析次数上限


def empty_profile():
    return {
        "degree": "本科", "major": "", "major_category": "其他",
        "enroll_year": None, "grad_year": None,
        "city": "", "accept_cities": [],
        "days_per_week": None, "months_available": None, "start_date": "",
        "skills": [],        # [{"name", "level", "evidence"}]
        "experiences": [],   # [{"title", "text"}]
        "certificates": [],  # [{"name", "status"}]
    }


SAMPLE_PROFILE = {
    "degree": "本科", "major": "信息管理与信息系统", "major_category": "管理类",
    "enroll_year": 2024, "grad_year": 2027,  # 故意保留届别矛盾，用来演示冲突检查
    "city": "上海", "accept_cities": ["上海"],
    "days_per_week": 3, "months_available": 6, "start_date": "2026-11-01",
    "skills": [
        {"name": "Excel", "level": "熟练", "evidence": "社团招新时用透视表整理 300 条报名信息"},
        {"name": "SQL", "level": "会用", "evidence": "数据库课程作业，写过多表连接查询"},
        {"name": "Python", "level": "没学过", "evidence": ""},
    ],
    "experiences": [
        {"title": "社团招新报名统计", "text": "负责 300 条报名信息的汇总，用 Excel 透视表按学院和时间段统计，结果用于安排面试场次"},
    ],
    "certificates": [{"name": "英语六级", "status": "已通过"}],
}

SAMPLE_JD = """数据分析实习生（示例岗位，组内构造，非真实招聘）
岗位职责：
1. 协助业务团队完成日常数据提取、清洗与报表制作；
2. 参与用户行为分析，输出分析结论与建议。
任职要求：
1. 本科及以上，统计、数学、计算机、经管类专业优先；
2. 2027届毕业生；
3. 熟练使用Excel，掌握SQL，了解Python者优先；
4. 每周至少到岗4天，实习期不少于3个月；
5. 有互联网数据分析实习经历者加分；
6. 逻辑清晰，沟通能力强。
工作地点：上海
"""

SAMPLE_JD_PRODUCT = """产品助理实习生（示例岗位，组内构造，非真实招聘）
岗位职责：
1. 协助产品经理整理用户反馈，跟进需求上线进度；
2. 参与竞品体验与分析，输出体验报告。
任职要求：
1. 本科及以上；
2. 2027届、2028届毕业生均可；
3. 每周到岗3天，实习期6个月；
4. 熟练使用Excel，会用SQL查询数据；
5. 能独立撰写需求文档；
6. 有Axure、Figma等原型工具经验者优先；
7. 有用户调研或竞品分析经历者加分；
8. 逻辑清晰，沟通能力强，有责任心。
工作地点：上海
"""

SAMPLE_JD_OPERATION = """新媒体运营实习生（示例岗位，组内构造，非真实招聘）
岗位职责：
1. 负责公司小红书、抖音账号的日常内容策划与发布；
2. 跟踪内容数据，按周复盘并提出优化建议。
任职要求：
1. 本科及以上，新闻传播、中文、市场营销等专业优先；
2. 2027届、2028届毕业生；
3. 每周至少到岗3天，可连续实习4个月以上；
4. 熟悉小红书、抖音等平台的内容规则；
5. 有独立运营账号的经历；
6. 能使用剪映等工具剪辑短视频；
7. 会用Excel做数据复盘；
8. 有Photoshop或Canva作图经验者加分；
9. 文字功底好，有责任心。
工作地点：上海
"""

# 演示用示例档案：不同年级、专业、学历的虚构同学，均为组内构造，不是真实用户
SAMPLE_PROFILES = {
    "大二·信息管理（含届别矛盾）": SAMPLE_PROFILE,
    "大三·统计学（数据分析方向）": {
        "degree": "本科", "major": "统计学", "major_category": "理工类",
        "enroll_year": 2023, "grad_year": 2027,
        "city": "上海", "accept_cities": ["上海", "杭州"],
        "days_per_week": 4, "months_available": 6, "start_date": "2026-12-01",
        "skills": [
            {"name": "Excel", "level": "熟练", "evidence": "统计调查课用 Excel 清洗 2000 份问卷并做交叉分析"},
            {"name": "SQL", "level": "熟练", "evidence": "数据库课程设计负责建表和查询，写过窗口函数"},
            {"name": "Python", "level": "会用", "evidence": "用 pandas 完成课程作业，做过电商销量的描述统计"},
        ],
        "experiences": [
            {"title": "大学生创新训练项目", "text": "分析校园外卖订单数据，用 SQL 提取、Python 作图，结论写进结题报告"},
            {"title": "统计建模大赛", "text": "三人组队，负责数据清洗和回归建模，获校级二等奖"},
        ],
        "certificates": [{"name": "英语六级", "status": "已通过"}, {"name": "计算机二级 Python", "status": "在考"}],
    },
    "大三·工业设计（产品方向）": {
        "degree": "本科", "major": "工业设计", "major_category": "艺术类",
        "enroll_year": 2023, "grad_year": 2027,
        "city": "上海", "accept_cities": ["上海"],
        "days_per_week": 3, "months_available": 6, "start_date": "2027-01-01",
        "skills": [
            {"name": "Figma", "level": "熟练", "evidence": "课程项目中独立完成校园二手 App 的高保真原型"},
            {"name": "Axure", "level": "会用", "evidence": "交互设计课用 Axure 做过可点击的流程原型"},
            {"name": "Excel", "level": "了解", "evidence": "整理过用户访谈记录表"},
        ],
        "experiences": [
            {"title": "校园二手交易 App 设计", "text": "访谈 12 名同学做用户调研，梳理需求后用 Figma 出原型，课程评分优秀"},
        ],
        "certificates": [{"name": "英语四级", "status": "已通过"}],
    },
    "大二·新闻传播（运营方向）": {
        "degree": "本科", "major": "新闻学", "major_category": "文史类",
        "enroll_year": 2024, "grad_year": 2028,
        "city": "上海", "accept_cities": ["上海"],
        "days_per_week": 3, "months_available": 4, "start_date": "2027-01-15",
        "skills": [
            {"name": "剪映", "level": "熟练", "evidence": "给学院公众号剪过 20 多条活动短视频"},
            {"name": "Canva", "level": "会用", "evidence": "做社团活动海报和推文封面"},
            {"name": "Excel", "level": "了解", "evidence": ""},
        ],
        "experiences": [
            {"title": "学院公众号编辑", "text": "每周写 1 至 2 篇推文，负责选题和排版，单篇最高阅读 3000"},
            {"title": "个人小红书账号", "text": "独立运营账号的半年里发布 40 篇校园探店笔记，涨粉 1200"},
        ],
        "certificates": [],
    },
    "大专大三·电子商务（学历门槛演示）": {
        "degree": "大专", "major": "电子商务", "major_category": "经管类",
        "enroll_year": 2024, "grad_year": 2027,
        "city": "上海", "accept_cities": ["上海"],
        "days_per_week": 5, "months_available": 6, "start_date": "2026-11-15",
        "skills": [
            {"name": "Excel", "level": "会用", "evidence": "网店运营课整理商品销售数据"},
            {"name": "剪映", "level": "会用", "evidence": "给实训店铺剪过商品短视频"},
        ],
        "experiences": [
            {"title": "淘宝店铺运营实训", "text": "三人小组运营实训店铺两个月，负责商品上架和详情页文案"},
        ],
        "certificates": [{"name": "英语四级", "status": "已通过"}],
    },
}

# 演示用示例岗位：名称 -> 招聘信息。三个岗位对应 D4 三类，按示例档案设计成三种不同结论
SAMPLE_JDS = {
    "数据分析实习生（示例）": SAMPLE_JD,
    "产品助理实习生（示例）": SAMPLE_JD_PRODUCT,
    "新媒体运营实习生（示例）": SAMPLE_JD_OPERATION,
}
