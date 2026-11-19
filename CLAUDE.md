# 岗位筛选助手（课程原型）

## 必读
- 动手前先读 docs/设计方案.md 中与本次功能编号对应的小节，以及 implementation-notes.md。
- 一次只实现一个功能编号（F00 至 F25），不顺手改无关文件。

## 结构
- app.py：Streamlit 页面与流程
- rules.py：硬门槛检查、结论判定、风险关键词。纯函数，禁止调用模型
- llm.py：模型调用与 JSON 三级兜底；提示词从 prompts/*.md 读取，不写在代码里
- models.py：常量与示例数据；数据结构以设计方案 3.3 节为准，改字段前先问
- storage.py：数据库与账号，所有数据库访问只经过这里；只写 SQLite 与 PostgreSQL 都支持的基础 SQL
- tests/：pytest 测试

## 规则
- 结论档位只能由 rules.judge 判定，模型输出不得直接决定结论。
- 改动 rules.py 必须同时更新 tests/test_rules.py；任何改动后 pytest 全部通过才算完成。
- 不输出任何匹配百分比或无依据分数。
- 提示词必须保留：不得虚构用户没有的技能或经历；拿不准标信息不足。
- 密钥只从 st.secrets 或环境变量读取，不得写进代码或日志。
- 密码只存 hashlib.scrypt 加盐哈希；不得新增姓名、电话、学号字段。
- 不得参考或复制 qiuzhao-voyage 仓库的代码、提示词和文案（非商业许可）。
- Python 代码里的中文引号写成 “ ”，或放进 prompts/ 文本文件，避免写入工具把弯引号改成直引号导致语法错误。

## 完成标准
- streamlit run app.py 能启动，本功能可在页面上操作。
- pytest 通过。
- 用两三句话说明改了什么、为什么这样改。
