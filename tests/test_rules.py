import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rules import (check_hard, judge, check_quotes, profile_conflicts, pick_followups,
                   apply_answer, risk_flags, gap_summary)

P = {"degree": "本科", "enroll_year": 2024, "grad_year": 2028, "accept_cities": ["上海"],
     "days_per_week": 3, "months_available": 6}


def R(i, level, quote="q", hard_type=None, params=None, soft=False, topic=None):
    return {"id": i, "level": level, "quote": quote, "hard_type": hard_type,
            "params": params or {}, "soft_flag": soft, "topic": topic}


def M(i, status):
    return {"req_id": i, "status": status, "profile_evidence": "", "user_override": None}


def test_days_3_vs_4_fails():
    m = check_hard(R("r1", "硬门槛", hard_type="到岗天数", params={"min_days": 4}), P)
    assert m["status"] == "不符合" and "差 1" in m["note"]


def test_grad_year_and_missing_field():
    assert check_hard(R("r", "硬门槛", hard_type="届别", params={"grad_years": [2027]}), P)["status"] == "不符合"
    assert check_hard(R("r", "硬门槛", hard_type="届别", params={"grad_years": [2028]}), P)["status"] == "符合"
    assert check_hard(R("r", "硬门槛", hard_type="实习时长", params={"min_months": 3}), {})["status"] == "信息不足"


def test_degree_city_remote():
    assert check_hard(R("r", "硬门槛", hard_type="学历", params={"min_degree": "硕士"}), P)["status"] == "不符合"
    assert check_hard(R("r", "硬门槛", hard_type="城市", params={"cities": ["北京"]}), P)["status"] == "不符合"
    assert check_hard(R("r", "硬门槛", hard_type="城市", params={"cities": ["北京"], "remote": True}), P)["status"] == "符合"


def test_hard_fail_caps_to_cautious():
    reqs = [R("h", "硬门槛", hard_type="到岗天数"), R("c", "核心能力")]
    v, reasons, remedies = judge(reqs, [{**M("h", "不符合"), "profile_evidence": "可到岗天数 3 天/周"}, M("c", "符合")])
    assert v == "谨慎投递" and remedies and "3" in remedies[0]


def test_soft_flag_duration_is_confirm_not_cautious():
    reqs = [R("h", "硬门槛", hard_type="实习时长", soft=True)]
    assert judge(reqs, [M("h", "不符合")])[0] == "补充后投递"


def test_strict_core_rule():
    reqs = [R("a", "核心能力"), R("b", "核心能力")]
    assert judge(reqs, [M("a", "符合"), M("b", "不符合")])[0] == "补充后投递"
    assert judge(reqs, [M("a", "部分符合"), M("b", "部分符合")])[0] == "补充后投递"
    assert judge(reqs, [M("a", "符合"), M("b", "部分符合")])[0] == "建议投递"


def test_bonus_never_affects_verdict():
    reqs = [R("a", "核心能力"), R("x", "加分项")]
    assert judge(reqs, [M("a", "符合"), M("x", "不符合")])[0] == "建议投递"


def test_user_override_wins():
    reqs = [R("a", "核心能力")]
    m = {**M("a", "不符合"), "user_override": {"status": "符合", "reason": "我做过"}}
    assert judge(reqs, [m])[0] == "建议投递"


def test_quote_check_ignores_whitespace():
    jd = "熟练使用 Excel，\n掌握SQL"
    assert check_quotes(jd, [R("a", "核心能力", quote="熟练使用Excel"), R("b", "核心能力", quote="精通Java")]) == ["b"]


def test_grad_conflict_and_followups():
    prof = {**P, "grad_year": 2027}
    c = profile_conflicts(prof)
    assert c and c[0]["enroll"] == 2024
    reqs = [R("h", "硬门槛", hard_type="到岗天数"), R("u", "硬门槛"), R("c1", "核心能力"), R("c2", "核心能力")]
    ms = [M("h", "不符合"), M("u", "信息不足"), M("c1", "信息不足"), M("c2", "信息不足")]
    qs = pick_followups(reqs, ms, c)
    assert len(qs) == 3 and [q["kind"] for q in qs] == ["grad_year", "adjust", "hard_unknown"]
    apply_answer(qs[0], "2028", ms, prof)
    assert prof["grad_year"] == 2028
    apply_answer(qs[1], "能", ms, prof)
    assert ms[0]["status"] == "符合" and ms[0]["source"] == "用户回答"


def test_risk_flags():
    flags = risk_flags("入职前需缴纳培训费500元。工作轻松")
    assert flags and flags[0]["keyword"] == "培训费" and "500" in flags[0]["quote"]
    assert risk_flags("每周到岗4天") == []


def test_gap_summary_counts_across_jobs():
    rep = lambda t, s: {"job": {"title": t}, "requirements": [R("a", "核心能力", topic="SQL")], "matches": [M("a", s)]}
    rows = gap_summary([rep("岗1", "部分符合"), rep("岗2", "不符合"), rep("岗3", "符合")])
    assert rows[0]["topic"] == "SQL" and rows[0]["count"] == 2


def test_sample_jds_cover_three_verdicts():
    """三个示例岗位在 2028 届示例档案下，演示模式应分别得出三种结论。"""
    import llm, models
    prof = {**models.SAMPLE_PROFILE, "grad_year": 2028}
    got = {}
    for name, jd in models.SAMPLE_JDS.items():
        reqs = llm.demo_extract(jd)
        assert check_quotes(jd, reqs) == []
        hard = [m for r in reqs if r.get("hard_type") and (m := check_hard(r, prof))]
        ids = {m["req_id"] for m in hard}
        ms = hard + [llm.demo_match(r, prof) for r in reqs if r["id"] not in ids]
        got[name] = judge(reqs, ms)[0]
    assert got == {"数据分析实习生（示例）": "谨慎投递",
                   "产品助理实习生（示例）": "建议投递",
                   "新媒体运营实习生（示例）": "补充后投递"}


def test_sample_profiles_valid():
    """示例档案字段齐全、取值合法；只有第一份故意保留届别矛盾。"""
    import models
    keys = set(models.empty_profile())
    for i, (name, p) in enumerate(models.SAMPLE_PROFILES.items()):
        assert set(p) == keys, name
        assert p["degree"] in models.DEGREES and p["major_category"] in models.MAJOR_CATEGORIES, name
        assert all(s["level"] in models.SKILL_LEVELS for s in p["skills"]), name
        assert bool(profile_conflicts(p)) == (i == 0), name
