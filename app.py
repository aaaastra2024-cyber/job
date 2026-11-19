"""岗位筛选助手：Streamlit 页面与流程。规则在 rules.py，模型在 llm.py，数据在 storage.py。"""
import copy
import datetime as dt
import json
import os

import pandas as pd
import streamlit as st

import llm
import models
import rules
from storage import Store

st.set_page_config(page_title="岗位筛选助手", page_icon="🧭", layout="wide")


def secret(name, default=None):
    """环境变量优先（魔搭创空间的设置、测试里的临时库），其次读本机 .streamlit/secrets.toml。"""
    if os.environ.get(name):
        return os.environ[name]
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return default


@st.cache_resource
def get_store():
    return Store(secret("DATABASE_URL"))


db = get_store()
INVITES = {c.strip() for c in str(secret("INVITE_CODES", "demo2026")).split(",")}
PAGES = ["分析岗位", "岗位报告", "岗位列表与对比", "投递看板", "缺口汇总", "我的档案", "账号与数据"]
VERDICT_BOX = {"建议投递": st.success, "补充后投递": st.warning, "谨慎投递": st.error}
PRIVACY = """**我们存什么**：你填写的求职档案（不含姓名、电话、学号）、分析过的招聘信息和报告、投递进度。
**存在哪**：本产品的数据库，仅用于为你生成报告；课程项目组成员可在维护时接触到数据。
**发给谁**：点击分析时，招聘信息和档案会发送给大模型服务商（DeepSeek）用于生成结果。
**怎么删**：在“账号与数据”页可以一键注销账号并删除全部数据。请不要在任何地方填写身份证号、电话等敏感信息。"""


# 账号 ----------------------------------------------------------------
def auth_page():
    st.title("🧭 岗位筛选助手")
    st.caption("粘贴一份招聘信息，几分钟内知道：硬门槛满不满足、缺什么、该不该投。")
    t1, t2 = st.tabs(["登录", "注册"])
    with t1, st.form("login"):
        u = st.text_input("用户名")
        p = st.text_input("密码", type="password")
        if st.form_submit_button("登录", type="primary"):
            if db.login(u, p):
                st.session_state.user = u.strip()
                st.rerun()
            st.error("用户名或密码不正确")
    with t2, st.form("register"):
        u = st.text_input("用户名（2 到 20 个字符，不要用真实姓名）")
        p = st.text_input("密码（至少 8 位）", type="password")
        inv = st.text_input("邀请码")
        st.markdown(PRIVACY)
        st.caption("忘记密码无法找回，请记好。")
        agree = st.checkbox("我已阅读并同意上述数据说明")
        if st.form_submit_button("注册", type="primary"):
            err = "请先勾选同意数据说明" if not agree else db.register(u, p, inv, INVITES)
            if err:
                st.error(err)
            else:
                st.session_state.user = u.strip()
                st.rerun()


# 分析流程 --------------------------------------------------------------
def demo_mode():
    return st.session_state.get("demo", not llm.has_key())


def go(page, report_id=None):
    st.session_state._goto = page  # 侧栏单选框已渲染，不能直接改它的值，下一轮开头再切换
    if report_id:
        st.session_state.view = report_id
    st.rerun()


def gaps_of(rep):
    by_id = {m["req_id"]: m for m in rep["matches"]}
    out = []
    for r in rep["requirements"]:
        m = by_id.get(r["id"])
        if m and r["level"] in ("硬门槛", "核心能力", "加分项") and rules.status_of(m) != "符合":
            out.append({"topic": r.get("topic"), "level": r["level"], "quote": r["quote"],
                        "status": rules.status_of(m), "note": m.get("note", "")})
    return out


def rejudge(rep):
    rep["verdict"], rep["verdict_reasons"], rep["remedies"] = rules.judge(rep["requirements"], rep["matches"])


def run_analysis(user, profile, job):
    demo = demo_mode()
    reqs = llm.extract(job["text"], demo)
    hard = [m for r in reqs if r.get("hard_type") and (m := rules.check_hard(r, profile))]
    hard_ids = {m["req_id"] for m in hard}
    others = llm.match([r for r in reqs if r["id"] not in hard_ids], profile, demo)
    matches = hard + others
    return {
        "job": job, "requirements": reqs, "matches": matches,
        "quote_check_failed": rules.check_quotes(job["text"], reqs),
        "risk_flags": rules.risk_flags(job["text"]),
        "pending": rules.pick_followups(reqs, matches, rules.profile_conflicts(profile)),
        "followups": [], "model_id": "演示模式（规则替代）" if demo else llm.MODEL,
        "application": {"status": "待投", "deadline": None, "interview_at": None, "note": ""},
    }


def finalize(user, rep, profile):
    rep.pop("pending", None)
    rejudge(rep)
    with st.spinner("生成准备清单……"):
        rep["checklist"] = llm.checklist(gaps_of(rep), profile, demo_mode())
    rid = db.save_report(user, rep)
    st.session_state.pop("draft", None)
    go("岗位报告", rid)


def analyze_page(user):
    profile = db.get_profile(user)
    if not profile:
        st.info("先建立你的求职档案，之后每次分析都会自动调用。")
        if st.button("去填写档案", type="primary"):
            go("我的档案")
        return
    draft = st.session_state.get("draft")
    if draft and draft.get("pending"):
        return followup_form(user, draft, profile)

    st.header("分析岗位")
    used = db.used_today(user)
    st.caption(f"今日已分析 {used} / {models.DAILY_LIMIT} 次")
    s1, s2 = st.columns([3, 1], vertical_alignment="bottom")
    sample = s1.selectbox("示例岗位", list(models.SAMPLE_JDS))
    if s2.button("填入示例招聘信息"):
        st.session_state.jd_text = models.SAMPLE_JDS[sample]
        st.session_state.jd_title = sample
    c1, c2, c3 = st.columns(3)
    title = c1.text_input("岗位名称", key="jd_title")
    company = c2.text_input("公司（选填）")
    url = c3.text_input("链接（选填）")
    text = st.text_area("粘贴招聘信息全文", height=260, key="jd_text")
    if st.button("开始分析", type="primary", disabled=not text.strip()):
        if used >= models.DAILY_LIMIT:
            st.error("今日分析次数已用完，明天再来。")
            return
        try:
            with st.spinner("拆解要求、核对档案……"):
                rep = run_analysis(user, profile, {"title": title, "company": company, "url": url, "text": text})
        except Exception as e:
            st.error(f"分析失败：{e}。可在左侧打开演示模式先体验流程。")
            return
        db.add_usage(user)
        if rep["pending"]:
            st.session_state.draft = rep
            st.rerun()
        finalize(user, rep, profile)


def followup_form(user, draft, profile):
    st.header("出结论前需要确认几件事")
    st.caption("先问清楚再下结论。可以跳过，跳过的项会在报告里标为信息不足。")
    answers = {}
    with st.form("followups"):
        for i, q in enumerate(draft["pending"]):
            st.markdown(f"**{i + 1}. {q['text']}**")
            answers[i] = st.radio("你的回答", q["options"], index=None, key=f"fq{i}", label_visibility="collapsed")
            st.caption(f"为什么问：{q['why']}")
        submit = st.form_submit_button("提交并出报告", type="primary")
        skip = st.form_submit_button("跳过，直接出报告")
    if submit or skip:
        if submit:
            for i, q in enumerate(draft["pending"]):
                if answers[i] is None:
                    continue
                rules.apply_answer(q, answers[i], draft["matches"], profile)
                draft["followups"].append({"question": q["text"], "answer": answers[i]})
                if q["kind"] == "grad_year":
                    db.save_profile(user, profile)
                    for r in draft["requirements"]:
                        if r.get("hard_type") == "届别":
                            new = rules.check_hard(r, profile)
                            draft["matches"] = [new if m["req_id"] == r["id"] else m for m in draft["matches"]]
        finalize(user, draft, profile)


# 报告 ----------------------------------------------------------------
def report_markdown(rep):
    by_id = {m["req_id"]: m for m in rep["matches"]}
    lines = [f"# {rep['job'].get('title') or '岗位'}　{rep['job'].get('company') or ''}", "",
             f"**结论：{rep['verdict']}**", ""] + [f"- {x}" for x in rep["verdict_reasons"] + rep["remedies"]]
    lines += ["", "| 级别 | 要求原文 | 你的情况 | 判断 |", "|---|---|---|---|"]
    for r in rep["requirements"]:
        m = by_id.get(r["id"], {})
        lines.append(f"| {r['level']} | {r['quote']} | {m.get('profile_evidence', '')} | {rules.status_of(m) if m else ''} |")
    lines += ["", "## 投递前准备清单"] + [f"- [{'x' if c['done'] else ' '}] {c['text']}" for c in rep.get("checklist", [])]
    return "\n".join(lines)


def report_page(user):
    reps = db.list_reports(user)
    if not reps:
        st.info("还没有报告，先去分析一个岗位。")
        return
    ids = [r["id"] for r in reps]
    vid = st.session_state.get("view") if st.session_state.get("view") in ids else ids[0]
    rep = next(r for r in reps if r["id"] == vid)
    st.selectbox("选择岗位", ids, index=ids.index(vid), key="report_pick",
                 format_func=lambda i: next(f"{r['job'].get('title') or '未命名'}｜{r['created_at'][:16]}" for r in reps if r["id"] == i),
                 on_change=lambda: st.session_state.update(view=st.session_state.report_pick))

    st.header(f"{rep['job'].get('title') or '未命名岗位'}　{rep['job'].get('company') or ''}")
    st.caption(f"分析时间 {rep['created_at'][:16]}　·　生成方式：{rep.get('model_id')}")

    for f in rep.get("risk_flags", []):
        st.error(f"⚠️ 风险提示：原文“{f['quote']}”含“{f['keyword']}”。{f['advice']}。")

    VERDICT_BOX[rep["verdict"]](f"### 结论：{rep['verdict']}\n" + "\n".join(f"- {x}" for x in rep["verdict_reasons"])
                                + ("\n\n**补救办法**\n" + "\n".join(f"- {x}" for x in rep["remedies"]) if rep["remedies"] else ""))

    by_id = {m["req_id"]: m for m in rep["matches"]}
    hard = [(r, by_id.get(r["id"])) for r in rep["requirements"] if r["level"] == "硬门槛"]
    if hard:
        st.subheader("硬门槛检查")
        icon = {"符合": "✅", "不符合": "❌", "部分符合": "⚠️", "信息不足": "❔"}
        cols = st.columns(min(len(hard), 5))
        for i, (r, m) in enumerate(hard):
            s = rules.status_of(m) if m else "信息不足"
            cols[i % len(cols)].markdown(f"{icon[s]} **{r.get('hard_type') or r['topic']}**  \n{r['quote']}"
                                         + ("  \n_写着优先，但常被当作硬门槛_" if r.get("soft_flag") else ""))

    st.subheader("逐条对照")
    st.caption("觉得判断不对，可以直接在“判断”列修改，结论会按规则自动重算。⚠️ 表示模型给出的原文在招聘信息里找不到，请谨慎参考。")
    failed = set(rep.get("quote_check_failed", []))
    rows = []
    for r in rep["requirements"]:
        m = by_id.get(r["id"], {})
        rows.append({"id": r["id"], "级别": r["level"], "要求原文": ("⚠️ " if r["id"] in failed else "") + r["quote"],
                     "招聘方想看什么": r.get("intent", ""), "你的情况": m.get("profile_evidence", ""),
                     "依据": m.get("source", ""), "判断": rules.status_of(m) if m else "信息不足", "说明": m.get("note", "")})
    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df, hide_index=True, width="stretch", key=f"tbl_{rep['id']}",
        disabled=[c for c in df.columns if c != "判断"],
        column_config={"id": None, "判断": st.column_config.SelectboxColumn(options=models.MATCH_STATUSES, required=True)})
    changed = False
    for _, row in edited.iterrows():
        m = by_id.get(row["id"])
        if m and row["判断"] != rules.status_of(m):
            m["user_override"] = None if row["判断"] == m["status"] else {"status": row["判断"], "at": dt.datetime.now().isoformat(timespec="seconds")}
            changed = True
    if changed:
        rejudge(rep)
        db.save_report(user, rep)
        db.log_event(user, "override")
        st.rerun()

    st.subheader("投递前准备清单")
    for i, c in enumerate(rep.get("checklist", [])):
        done = st.checkbox(f"【{c['type']}】{c['text']}", value=c["done"], key=f"ck_{rep['id']}_{i}")
        if done != c["done"]:
            c["done"] = done
            db.save_report(user, rep)

    st.caption("本报告只依据你的档案和这份招聘信息生成，不了解公司内部的真实筛选标准，仅供决策参考。")
    c1, c2, c3 = st.columns(3)
    c1.download_button("导出报告（Markdown）", report_markdown(rep), file_name="岗位报告.md")
    if c2.button("导出 PDF（会员功能）"):
        db.log_event(user, "fakedoor_pdf")
        st.info("会员功能还在规划中，谢谢你的关注！")
    if c3.button("删除这份报告"):
        db.delete_report(user, rep["id"])
        st.session_state.pop("view", None)
        st.rerun()


def summary(rep):
    by_id = {m["req_id"]: m for m in rep["matches"]}
    st_ = lambda r: rules.status_of(by_id[r["id"]]) if r["id"] in by_id else "信息不足"
    return {
        "硬门槛未满足": sum(r["level"] == "硬门槛" and st_(r) == "不符合" for r in rep["requirements"]),
        "核心能力缺口": sum(r["level"] == "核心能力" and st_(r) != "符合" for r in rep["requirements"]),
        "清单完成": f"{sum(c['done'] for c in rep.get('checklist', []))}/{len(rep.get('checklist', []))}",
    }


def list_page(user):
    st.header("岗位列表与对比")
    reps = db.list_reports(user)
    if not reps:
        st.info("还没有分析过岗位。")
        return
    df = pd.DataFrame([{"岗位": r["job"].get("title") or "未命名", "公司": r["job"].get("company"),
                        "结论": r["verdict"], **summary(r), "分析时间": r["created_at"][:16]} for r in reps])
    st.dataframe(df, hide_index=True, width="stretch")
    names = {r["id"]: f"{r['job'].get('title') or '未命名'}｜{r['created_at'][:16]}" for r in reps}
    pick = st.multiselect("选 2 到 3 个岗位并排比较", list(names), format_func=names.get, max_selections=3)
    if len(pick) >= 2:
        cols = st.columns(len(pick))
        for col, rid in zip(cols, pick):
            rep = next(r for r in reps if r["id"] == rid)
            with col:
                st.markdown(f"#### {names[rid]}")
                VERDICT_BOX[rep["verdict"]](rep["verdict"])
                for g in gaps_of(rep):
                    st.markdown(f"- {g['level']}｜{g['quote']}：{g['status']}")
                if st.button("打开报告", key=f"open_{rid}"):
                    go("岗位报告", rid)


def board_page(user):
    st.header("投递看板")
    reps = db.list_reports(user)
    if not reps:
        st.info("分析过的岗位会自动出现在这里。")
        return
    counts = pd.Series([r["application"]["status"] for r in reps]).value_counts()
    cols = st.columns(len(models.APP_STATUSES))
    for c, s in zip(cols, models.APP_STATUSES):
        c.metric(s, int(counts.get(s, 0)))
    to_date = lambda s: dt.date.fromisoformat(s) if s else None
    df = pd.DataFrame([{"id": r["id"], "岗位": r["job"].get("title") or "未命名", "公司": r["job"].get("company"),
                        "结论": r["verdict"], "状态": r["application"]["status"],
                        "截止日期": to_date(r["application"].get("deadline")),
                        "面试时间": to_date(r["application"].get("interview_at")),
                        "备注": r["application"].get("note", "")} for r in reps])
    edited = st.data_editor(df, hide_index=True, width="stretch", disabled=["岗位", "公司", "结论"],
                            column_config={"id": None,
                                           "状态": st.column_config.SelectboxColumn(options=models.APP_STATUSES, required=True),
                                           "截止日期": st.column_config.DateColumn(), "面试时间": st.column_config.DateColumn()})
    if st.button("保存看板", type="primary"):
        for _, row in edited.iterrows():
            rep = next(r for r in reps if r["id"] == row["id"])
            iso = lambda d: d.isoformat() if pd.notna(d) and d else None
            rep["application"] = {"status": row["状态"], "deadline": iso(row["截止日期"]),
                                  "interview_at": iso(row["面试时间"]), "note": row["备注"] or ""}
            db.save_report(user, rep)
        st.success("已保存")
    today = dt.date.today()
    soon = [(d, kind, r["job"].get("title")) for r in reps for kind, key in (("截止", "deadline"), ("面试", "interview_at"))
            if (d := to_date(r["application"].get(key))) and today <= d <= today + dt.timedelta(days=7)]
    if soon:
        st.subheader("近 7 天")
        for d, kind, t in sorted(soon):
            st.markdown(f"- {d}　{kind}　{t}")


def gaps_page(user):
    st.header("缺口汇总")
    st.caption("把你分析过的所有岗位放在一起，看哪些能力被反复要求而你还没达标，按优先级排序。")
    rows = rules.gap_summary(db.list_reports(user))
    if not rows:
        st.info("分析两三个岗位后，这里会显示你最该补的能力。")
        return
    st.dataframe(pd.DataFrame([{"能力": r["topic"], "未达标岗位数": r["count"], "其中作为核心能力": r["core"],
                                "涉及岗位": "、".join(r["jobs"])} for r in rows]), hide_index=True, width="stretch")
    if st.button("生成完整学习路线（会员功能）"):
        db.log_event(user, "fakedoor_roadmap")
        st.info("会员功能还在规划中，谢谢你的关注！")


# 档案 ----------------------------------------------------------------
def profile_page(user):
    st.header("我的档案")
    st.caption("填一次，之后每次分析自动调用。不要填写姓名、电话、学号。")
    p = db.get_profile(user) or models.empty_profile()
    s1, s2 = st.columns([3, 1], vertical_alignment="bottom")
    sample = s1.selectbox("示例档案（虚构同学，载入会覆盖当前档案）", list(models.SAMPLE_PROFILES))
    if s2.button("载入示例档案"):
        db.save_profile(user, copy.deepcopy(models.SAMPLE_PROFILES[sample]))
        for k in ("sk", "ex", "ce"):  # 清掉表格编辑器的残留状态，避免旧档案的改动带到新档案
            st.session_state.pop(k, None)
        st.rerun()
    with st.form("profile"):
        c1, c2, c3 = st.columns(3)
        p["degree"] = c1.selectbox("学历", models.DEGREES, index=models.DEGREES.index(p["degree"]))
        p["major"] = c2.text_input("专业", p["major"])
        p["major_category"] = c3.selectbox("专业大类", models.MAJOR_CATEGORIES, index=models.MAJOR_CATEGORIES.index(p["major_category"]))
        c1, c2, c3 = st.columns(3)
        p["enroll_year"] = c1.number_input("入学年份", 2015, 2035, p["enroll_year"] or None, placeholder="如 2024")
        p["grad_year"] = c2.number_input("预计毕业年份", 2015, 2040, p["grad_year"] or None, placeholder="如 2028")
        p["city"] = c3.text_input("所在城市", p["city"])
        c1, c2, c3 = st.columns(3)
        cities = c1.text_input("可接受的工作城市（逗号分隔）", "，".join(p["accept_cities"]))
        p["days_per_week"] = c2.number_input("学期中每周可到岗天数", 0, 7, p["days_per_week"], placeholder="如 3")
        p["months_available"] = c3.number_input("可连续实习月数", 0, 24, p["months_available"], placeholder="如 3")
        st.markdown("**技能**　熟练度：没学过 / 了解（上过课或看过教程）/ 会用（独立完成过作业或练习）/ 熟练（在项目、实习或竞赛中实际用过）")
        skills = st.data_editor(pd.DataFrame(p["skills"], columns=["name", "level", "evidence"]), num_rows="dynamic",
                                width="stretch", key="sk",
                                column_config={"name": "技能", "evidence": "证据（做过什么）",
                                               "level": st.column_config.SelectboxColumn("熟练度", options=models.SKILL_LEVELS)})
        st.markdown("**经历**（项目、实习、竞赛、社团，写清做了什么、结果如何）")
        exps = st.data_editor(pd.DataFrame(p["experiences"], columns=["title", "text"]), num_rows="dynamic",
                              width="stretch", key="ex", column_config={"title": "名称", "text": "做了什么、结果如何"})
        st.markdown("**证书**")
        certs = st.data_editor(pd.DataFrame(p["certificates"], columns=["name", "status"]), num_rows="dynamic",
                               width="stretch", key="ce",
                               column_config={"name": "证书", "status": st.column_config.SelectboxColumn("状态", options=["已通过", "在考", "未考"])})
        if st.form_submit_button("保存档案", type="primary"):
            p["accept_cities"] = [c.strip() for c in cities.replace(",", "，").split("，") if c.strip()]
            clean = lambda df: [{k: ("" if pd.isna(v) else v) for k, v in row.items()} for row in df.to_dict("records") if any(pd.notna(x) and x != "" for x in row.values())]
            p["skills"], p["experiences"], p["certificates"] = clean(skills), clean(exps), clean(certs)
            for k in ("enroll_year", "grad_year", "days_per_week", "months_available"):
                p[k] = int(p[k]) if p[k] is not None else None
            db.save_profile(user, p)
            st.success("已保存")
    if rules.profile_conflicts(p):
        c = rules.profile_conflicts(p)[0]
        st.warning(f"入学 {c['enroll']} 年、预计 {c['grad']} 年毕业，与四年制本科不一致，请核对。")


def account_page(user):
    st.header("账号与数据")
    st.markdown(PRIVACY)
    st.download_button("导出我的全部数据（JSON）", json.dumps(db.export_user(user), ensure_ascii=False, indent=2),
                       file_name="我的求职数据.json")
    st.divider()
    sure = st.checkbox("我确认注销账号，并永久删除我的档案、报告和看板数据")
    if st.button("注销账号并删除全部数据", disabled=not sure):
        db.delete_user(user)
        st.session_state.clear()
        st.rerun()


# 入口 ----------------------------------------------------------------
user = st.session_state.get("user")
if not user:
    auth_page()
    st.stop()

if "_goto" in st.session_state:
    st.session_state.page = st.session_state.pop("_goto")

with st.sidebar:
    st.markdown(f"### 🧭 岗位筛选助手\n你好，{user}")
    page = st.radio("页面", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    st.toggle("演示模式（不调用大模型）", value=not llm.has_key(), key="demo",
              help="没有可用的模型密钥、或现场断网时使用。抽取和对照改用简单规则，效果明显弱于大模型。")
    if st.button("退出登录"):
        st.session_state.clear()
        st.rerun()

if demo_mode():
    st.info("当前为演示模式：要求拆解和对照由简单规则完成，未调用大模型。", icon="ℹ️")

{"分析岗位": analyze_page, "岗位报告": report_page, "岗位列表与对比": list_page, "投递看板": board_page,
 "缺口汇总": gaps_page, "我的档案": profile_page, "账号与数据": account_page}[page](user)
