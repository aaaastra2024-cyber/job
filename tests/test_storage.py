import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from storage import Store


def test_account_profile_reports_roundtrip(tmp_path):
    s = Store(f"sqlite:///{tmp_path}/t.db")
    assert s.register("小明", "12345678", "bad", {"OK"}) == "邀请码不正确"
    assert s.register("小明", "123", "OK", {"OK"}) == "密码至少 8 位"
    assert s.register("小明", "12345678", "OK", {"OK"}) is None
    assert s.register("小明", "12345678", "OK", {"OK"}) == "用户名已被占用"
    assert s.login("小明", "12345678") and not s.login("小明", "wrongpass")
    assert s.register(" 小红 ", "12345678", " OK ", {"OK"}) is None and s.login("小红", "12345678")  # 首尾空格

    s.save_profile("小明", {"major": "信管"})
    s.save_profile("小明", {"major": "统计"})
    assert s.get_profile("小明")["major"] == "统计"

    rid = s.save_report("小明", {"job": {"title": "数据分析"}})
    rep = s.list_reports("小明")[0]
    rep["application"] = {"status": "已投"}
    s.save_report("小明", rep)
    assert len(s.list_reports("小明")) == 1 and s.list_reports("小明")[0]["application"]["status"] == "已投"

    s.add_usage("小明"); s.add_usage("小明")
    assert s.used_today("小明") == 2

    s.delete_user("小明")
    assert s.get_profile("小明") is None and s.list_reports("小明") == [] and not s.login("小明", "12345678")
    assert rid
