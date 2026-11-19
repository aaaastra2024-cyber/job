"""冒烟测试：演示模式下跑通注册 → 档案 → 分析 → 追问 → 报告 → 看板 → 缺口汇总。"""
import os, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest


def test_full_flow_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/a.db")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.chdir(ROOT)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception

    # 注册
    at.tabs[1].text_input[0].input("测试员")
    at.tabs[1].text_input[1].input("12345678")
    at.tabs[1].text_input[2].input("demo2026")
    at.tabs[1].checkbox[0].check()
    at.tabs[1].button[0].click().run()
    assert at.session_state.user == "测试员" and not at.exception

    # 档案：载入示例
    at.sidebar.radio[0].set_value("我的档案").run()
    next(b for b in at.button if b.label == "载入示例档案").click().run()
    assert not at.exception and at.warning  # 届别矛盾提示

    # 分析示例岗位
    at.sidebar.radio[0].set_value("分析岗位").run()
    next(b for b in at.button if b.label == "填入示例招聘信息").click().run()
    next(b for b in at.button if b.label == "开始分析").click().run()
    assert not at.exception
    assert "确认" in at.header[0].value  # 进入追问

    # 回答追问：2028 届，到岗能调整
    at.main.radio[0].set_value("2028")
    at.main.radio[1].set_value("能")
    next(b for b in at.button if b.label == "提交并出报告").click().run()
    assert not at.exception
    assert at.session_state.page == "岗位报告"
    body = " ".join(m.value for m in at.markdown) + " ".join(x.value for x in [*at.warning, *at.success, *at.error])
    # 用户确认 2028 届，岗位要 2027 届：届别硬门槛不满足，封顶谨慎投递
    assert "谨慎投递" in body and "2027届毕业生" in body

    for pg in ("岗位列表与对比", "投递看板", "缺口汇总", "账号与数据"):
        at.sidebar.radio[0].set_value(pg).run()
        assert not at.exception, pg
