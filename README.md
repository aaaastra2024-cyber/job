# 岗位筛选助手（课程原型 P0）

粘贴一份招聘信息，调用已保存的求职档案，先追问关键缺失信息，再给出一页报告：规则判定的三档结论、硬门槛逐项检查、逐条对照表、可勾选准备清单；可保存多个岗位并排比较、管理投递进度、汇总能力缺口。

设计依据见 `docs/设计方案.md`，实现中偏离设计的地方见 `implementation-notes.md`。

## 本机运行

需要 Python 3.10 及以上。在本文件夹里打开终端，按自己的系统执行。

Mac / Linux：

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/streamlit run app.py
```

Windows（PowerShell）：

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pytest
.venv\Scripts\streamlit run app.py
```

浏览器打开 http://localhost:8501，用邀请码 `demo2026` 注册。数据存在本机 `data/app.db`，每个人的库互不相通。

没有 DeepSeek 密钥时左侧会自动打开演示模式（规则替代模型，效果弱很多，只用于演示流程和断网兜底）。有密钥时，把 `.streamlit/secrets.toml.example` 复制一份改名为 `secrets.toml`，填入密钥。`DATABASE_URL` 那行保持注释，本机就一直用 SQLite。

## 测试

```sh
.venv/bin/python -m pytest -q
```

- `tests/test_rules.py`：硬门槛、结论规则、追问、风险提示、缺口汇总
- `tests/test_storage.py`：注册登录、档案、报告、用量、注销删除
- `tests/test_app.py`：演示模式下的完整页面流程

## 文件

| 文件 | 作用 |
|---|---|
| app.py | 页面与流程 |
| rules.py | 硬门槛检查、结论判定、追问、风险提示、缺口汇总（纯函数，不调用模型） |
| llm.py | DeepSeek 调用、JSON 三级兜底、演示模式 |
| prompts/ | 三个提示词，不懂代码也可以直接改 |
| storage.py | 数据库与账号（本机 SQLite，线上 Supabase） |
| models.py | 常量、示例档案、示例招聘信息 |

## 部署（免费方案，见设计方案 D3）

1. Supabase 新建项目（区域选新加坡或东京），复制连接串。
2. 魔搭社区创空间新建应用，选择 Streamlit（是否支持待验证；不支持则用 Streamlit Community Cloud），连接本仓库。
3. 在平台的密钥配置里填 `DEEPSEEK_API_KEY`、`DATABASE_URL`、`INVITE_CODES`。
4. 部署后注册一个账号、存一份档案，然后重启应用，确认数据还在。
