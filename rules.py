"""产品的核心规则：硬门槛检查、结论判定、追问挑选、风险提示、缺口汇总。

全部是纯函数，不调用模型。结论档位只能由这里判定（设计方案 3.4 节，D2 严格版）。
"""
import re

from models import DEGREES

FOLLOWUP_LIMIT = 3
PARTIAL_LIMIT = 2  # 核心能力“部分符合”达到这个数即封顶为补充后投递

REMEDIES = {
    "到岗天数": "投递前先问 HR 能否接受每周 {have} 天到岗",
    "实习时长": "投递前先问 HR 能否接受 {have} 个月的实习期",
    "届别": "投递前先确认岗位是否接受你的届别",
    "城市": "投递前确认能否远程或你是否愿意去该城市",
    "学历": "学历要求通常无法协商，建议优先考虑其他岗位",
}

RISK_WORDS = {
    "培训费": "正规实习不应向学生收取培训费",
    "押金": "要求交押金是常见的招聘骗局信号",
    "保证金": "要求交保证金是常见的招聘骗局信号",
    "服装费": "以服装费等名义收费需警惕",
    "培训贷": "培训贷会让你背上贷款，务必拒绝",
    "分期": "涉及分期付款的岗位需警惕培训贷",
    "无底薪": "无底薪意味着收入完全不确定",
    "垫付": "要求垫付资金是常见骗局信号",
    "刷单": "刷单属于违法活动",
    "日结高薪": "日结高薪类信息诈骗风险高",
}


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def status_of(match):
    """用户改过判断就用用户的，否则用系统的。"""
    ov = match.get("user_override")
    return ov["status"] if ov else match["status"]


def check_quotes(jd_text, reqs):
    """返回原句不在招聘信息里的要求 id（防止模型编造原文）。"""
    jd = _norm(jd_text)
    return [r["id"] for r in reqs if _norm(r.get("quote")) not in jd]


def profile_conflicts(profile):
    e, g = profile.get("enroll_year"), profile.get("grad_year")
    if profile.get("degree") == "本科" and e and g and e + 4 != g:
        return [{"kind": "grad_year", "enroll": e, "grad": g}]
    return []


def _match(req, status, evidence, note=""):
    return {"req_id": req["id"], "status": status, "profile_evidence": evidence,
            "judged_by": "rule", "source": "基于档案", "note": note, "user_override": None}


def check_hard(req, profile):
    """五类硬门槛由程序比较。缺档案字段或缺岗位参数时判信息不足。"""
    t, p = req.get("hard_type"), req.get("params") or {}
    if t == "学历":
        need, have = p.get("min_degree"), profile.get("degree")
        if need not in DEGREES or have not in DEGREES:
            return _match(req, "信息不足", f"学历：{have or '未填'}")
        ok = DEGREES.index(have) >= DEGREES.index(need)
        return _match(req, "符合" if ok else "不符合", f"学历：{have}")
    if t == "届别":
        need, have = p.get("grad_years") or [], profile.get("grad_year")
        if not need or not have:
            return _match(req, "信息不足", f"预计毕业：{have or '未填'}")
        return _match(req, "符合" if have in need else "不符合", f"预计 {have} 年毕业",
                      "" if have in need else f"要求 {'、'.join(map(str, need))} 届")
    if t == "城市":
        if p.get("remote"):
            return _match(req, "符合", "岗位可远程")
        need, have = p.get("cities") or [], profile.get("accept_cities") or []
        if not need or not have:
            return _match(req, "信息不足", f"可接受城市：{'、'.join(have) or '未填'}")
        ok = any(c in have for c in need)
        return _match(req, "符合" if ok else "不符合", f"可接受城市：{'、'.join(have)}")
    for typ, key, field, unit in (("到岗天数", "min_days", "days_per_week", "天/周"),
                                  ("实习时长", "min_months", "months_available", "个月")):
        if t == typ:
            need, have = p.get(key), profile.get(field)
            if need is None or have is None:
                return _match(req, "信息不足", f"{typ}：{'未填' if have is None else str(have) + unit}")
            ok = have >= need
            return _match(req, "符合" if ok else "不符合", f"可{typ} {have} {unit}",
                          "" if ok else f"差 {need - have} {unit}")
    return None


def judge(reqs, matches):
    """D2 严格版，按顺序命中即停。返回 (结论, 理由列表, 补救列表)。"""
    by_id = {m["req_id"]: m for m in matches}
    hard_fail, hard_unsure, core_fail, core_partial = [], [], [], []
    for r in reqs:
        m = by_id.get(r["id"])
        s = status_of(m) if m else "信息不足"
        if r["level"] == "硬门槛":
            if s == "不符合" and not r.get("soft_flag"):
                hard_fail.append((r, m))
            elif s in ("信息不足", "部分符合") or (s == "不符合" and r.get("soft_flag")):
                hard_unsure.append((r, m))
        elif r["level"] == "核心能力":
            if s == "不符合":
                core_fail.append(r)
            elif s in ("部分符合", "信息不足"):  # 信息不足按部分符合计，偏保守
                core_partial.append(r)

    if hard_fail:
        reasons = [f"硬门槛不满足：{r['quote']}（你：{m['profile_evidence']}）" for r, m in hard_fail]
        remedies = []
        for r, m in hard_fail:
            tpl = REMEDIES.get(r.get("hard_type"), "投递前先与 HR 确认这一条能否协商")
            have = "".join(re.findall(r"\d+", m["profile_evidence"])[:1])
            remedies.append(tpl.format(have=have))
        return "谨慎投递", reasons, remedies
    if hard_unsure:
        reasons = []
        for r, m in hard_unsure:
            tag = "写着优先，但常被当作硬门槛" if r.get("soft_flag") else "信息不足"
            reasons.append(f"硬门槛待确认（{tag}）：{r['quote']}")
        return "补充后投递", reasons, ["投递前先向 HR 或学长学姐确认上述条件"]
    if core_fail or len(core_partial) >= PARTIAL_LIMIT:
        reasons = [f"核心能力不符合：{r['quote']}" for r in core_fail]
        reasons += [f"核心能力有基础但证据不足：{r['quote']}" for r in core_partial]
        return "补充后投递", reasons, ["按准备清单补足证据后再投递"]
    return "建议投递", ["硬门槛全部满足，核心能力无明显缺口"], []


def pick_followups(reqs, matches, conflicts):
    """最多 3 个追问，顺序：档案矛盾 > 硬门槛 > 核心能力。"""
    qs = []
    for c in conflicts:
        qs.append({"kind": "grad_year", "req_id": None,
                   "text": f"你的入学年份是 {c['enroll']}，按四年制本科应在 {c['enroll'] + 4} 年毕业，档案写的是 {c['grad']} 年。实际哪年毕业？",
                   "options": [str(c["grad"]), str(c["enroll"] + 4)],
                   "why": "届别是硬门槛，毕业年份错了结论会错。"})
    by_id = {m["req_id"]: m for m in matches}
    for r in reqs:
        m = by_id.get(r["id"])
        if not m:
            continue
        if r["level"] == "硬门槛" and m["status"] == "不符合" and r.get("hard_type") in ("到岗天数", "实习时长", "城市"):
            qs.append({"kind": "adjust", "req_id": r["id"],
                       "text": f"岗位要求：{r['quote']}。你的情况：{m['profile_evidence']}。能否调整到满足要求？",
                       "options": ["能", "不能", "不确定"], "why": "这是硬门槛，直接决定结论档位。"})
        elif r["level"] == "硬门槛" and m["status"] == "信息不足":
            qs.append({"kind": "hard_unknown", "req_id": r["id"],
                       "text": f"岗位要求：{r['quote']}。你是否满足？",
                       "options": ["满足", "不满足", "不确定"], "why": "这是硬门槛，档案里没有对应信息。"})
    for r in reqs:
        m = by_id.get(r["id"])
        if m and r["level"] == "核心能力" and m["status"] == "信息不足":
            qs.append({"kind": "core_unknown", "req_id": r["id"],
                       "text": f"岗位要求：{r['quote']}。你有相关经历吗？",
                       "options": ["有，在项目或实习中实际用过", "学过，但没有实际用过", "没有"],
                       "why": "这是核心能力，档案里找不到证据。"})
    return qs[:FOLLOWUP_LIMIT]


ANSWER_MAP = {
    "adjust": {"能": "符合", "不能": "不符合", "不确定": "信息不足"},
    "hard_unknown": {"满足": "符合", "不满足": "不符合", "不确定": "信息不足"},
    "core_unknown": {"有，在项目或实习中实际用过": "符合", "学过，但没有实际用过": "部分符合", "没有": "不符合"},
}


def apply_answer(q, answer, matches, profile):
    """把追问的回答写回对照结果或档案。档案矛盾改的是档案，调用方随后要重跑硬门槛检查。"""
    if q["kind"] == "grad_year":
        profile["grad_year"] = int(answer)
        return
    for m in matches:
        if m["req_id"] == q["req_id"]:
            m["status"] = ANSWER_MAP[q["kind"]][answer]
            m["source"] = "用户回答"
            m["profile_evidence"] = f"{m['profile_evidence']}；追问回答：{answer}".lstrip("；")


def risk_flags(jd_text):
    out = []
    for sent in re.split(r"[。；;！!\n]", jd_text or ""):
        for w, advice in RISK_WORDS.items():
            if w in sent:
                out.append({"keyword": w, "quote": sent.strip(), "advice": advice})
    return out


def gap_summary(reports):
    """跨岗位统计缺口：每个技能主题在多少个岗位里没达标。"""
    acc = {}
    for rep in reports:
        by_id = {m["req_id"]: m for m in rep.get("matches", [])}
        for r in rep.get("requirements", []):
            m = by_id.get(r["id"])
            if r["level"] in ("核心能力", "加分项") and m and status_of(m) != "符合":
                g = acc.setdefault(r.get("topic") or r["quote"][:12], {"count": 0, "core": 0, "jobs": []})
                g["count"] += 1
                g["core"] += r["level"] == "核心能力"
                g["jobs"].append(rep["job"].get("title") or "未命名岗位")
    rows = [{"topic": k, **v} for k, v in acc.items()]
    return sorted(rows, key=lambda x: (-x["core"], -x["count"]))
