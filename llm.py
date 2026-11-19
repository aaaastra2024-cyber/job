"""模型调用。提示词在 prompts/ 目录，组员可直接修改。

没有可用密钥时走演示模式：用简单规则代替模型做抽取和对照，界面会标明。
"""
import json
import os
import pathlib
import re
import urllib.request

PROMPTS = pathlib.Path(__file__).parent / "prompts"
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _key():
    try:
        import streamlit as st
        if "DEEPSEEK_API_KEY" in st.secrets:
            return st.secrets["DEEPSEEK_API_KEY"]
    except Exception:
        pass
    return os.environ.get("DEEPSEEK_API_KEY", "")


def has_key():
    return bool(_key())


def _prompt(name, **fills):
    s = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for k, v in fills.items():
        s = s.replace("{{" + k + "}}", v)
    return s


def _chat(content, json_mode=True):
    body = {"model": MODEL, "temperature": 0, "messages": [{"role": "user", "content": content}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {_key()}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def _parse(raw):
    raw = re.sub(r"^```(json)?|```$", "", raw.strip()).strip()
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def call_json(content):
    """三级兜底：JSON 模式 → 只修格式 → 带提示重新生成。"""
    raw = _chat(content)
    try:
        return _parse(raw)
    except ValueError:
        pass
    try:
        return _parse(_chat("下面这段本应是 JSON 但格式不合法。只修复格式，不改内容、不补充信息，只输出 JSON：\n" + raw))
    except ValueError:
        pass
    try:
        return _parse(_chat(content + "\n\n上次输出的 JSON 格式错误。请重新输出一个完整合法的 JSON 对象。"))
    except ValueError:
        raise RuntimeError("模型返回格式异常，已自动修复并重试仍未成功，请稍后再试。")


# 三个任务 ------------------------------------------------------------
def extract(jd, demo=False):
    if demo:
        return demo_extract(jd)
    reqs = call_json(_prompt("extract", JD=jd))["requirements"]
    for i, r in enumerate(reqs, 1):
        r["id"] = f"r{i}"
    return reqs


def match(reqs, profile, demo=False):
    if not reqs:
        return []
    if demo:
        return [demo_match(r, profile) for r in reqs]
    slim = [{k: r[k] for k in ("id", "quote", "level", "topic")} for r in reqs]
    out = call_json(_prompt("match", REQS=json.dumps(slim, ensure_ascii=False),
                            PROFILE=json.dumps(profile, ensure_ascii=False)))["matches"]
    for m in out:
        m.update(judged_by="llm", user_override=None)
    return out


def checklist(gaps, profile, demo=False):
    if not gaps:
        return []
    if demo:
        out = []
        for g in gaps[:3]:
            out.append({"text": f"在简历中写清与{g['topic']}相关的具体经历、做法和结果", "type": "简历"})
            out.append({"text": f"准备回答：你用{g['topic']}解决过什么具体问题？", "type": "面试"})
        return [{**c, "done": False} for c in out[:6]]
    out = call_json(_prompt("checklist", GAPS=json.dumps(gaps, ensure_ascii=False),
                            PROFILE=json.dumps(profile, ensure_ascii=False)))["checklist"]
    return [{**c, "done": False} for c in out]


# 演示模式：规则版抽取与对照（不调用模型，效果明显弱于模型）-----------------
def _topic(clause):
    m = re.search(r"[A-Za-z][A-Za-z+#.]*", clause)
    if m:
        return m.group(0)
    return re.sub(r"^(熟练使用|熟练|掌握|熟悉|了解|具备|有|能够)|(者优先|优先|者加分|加分|经历|能力强)$", "", clause)[:8]


def demo_extract(jd):
    reqs, n = [], 0
    has_header = bool(re.search("任职要求|岗位要求|任职资格|我们希望", jd))
    in_req = not has_header
    for line in jd.splitlines():
        line = line.strip()
        if re.match("(任职要求|岗位要求|任职资格|我们希望)", line):
            in_req = True
        elif re.match("(岗位职责|工作内容|职位描述|福利)", line):
            in_req = False
        city = re.match(r"工作地点[:：]\s*(\S+)", line)
        if city:
            n += 1
            reqs.append({"id": f"r{n}", "quote": line, "topic": "工作城市", "level": "硬门槛", "hard_type": "城市",
                         "params": {"cities": [city.group(1)], "remote": False}, "soft_flag": False, "intent": ""})
            continue
        body = re.sub(r"^\d+[.、．]\s*", "", line)
        if not in_req or body == line or not body:
            continue
        for cl in re.split(r"[，,；;。]", body):
            cl = cl.strip()
            if not cl:
                continue
            n += 1
            r = {"id": f"r{n}", "quote": cl, "topic": _topic(cl), "level": "核心能力",
                 "hard_type": None, "params": {}, "soft_flag": False, "intent": ""}
            soft = bool(re.search("优先|加分|者佳", cl))
            if d := re.search("(大专|本科|硕士|博士)及以上", cl):
                r.update(level="硬门槛", hard_type="学历", params={"min_degree": d.group(1)}, topic="学历")
            elif y := re.findall(r"(20\d\d)\s*届", cl):
                r.update(level="硬门槛", hard_type="届别", params={"grad_years": [int(x) for x in y]}, topic="届别")
            elif d := re.search(r"每周.*?(\d)\s*天", cl):
                r.update(level="硬门槛", hard_type="到岗天数", params={"min_days": int(d.group(1))}, topic="到岗天数", soft_flag=soft)
            elif d := re.search(r"(\d+)\s*个月", cl):
                r.update(level="硬门槛", hard_type="实习时长", params={"min_months": int(d.group(1))}, topic="实习时长", soft_flag=soft)
            elif soft:
                r["level"] = "加分项"
            elif re.search("沟通|逻辑|责任心|团队|抗压|学习能力", cl):
                r["level"] = "软性要求"
            reqs.append(r)
    return reqs


LEVEL_TO_STATUS = {"熟练": "符合", "会用": "符合", "了解": "部分符合", "没学过": "不符合"}


def demo_match(r, profile):
    m = {"req_id": r["id"], "status": "信息不足", "profile_evidence": "档案中未体现",
         "judged_by": "demo", "source": "基于档案", "note": "", "user_override": None}
    for s in profile.get("skills", []):
        if s.get("name") and s["name"].lower() in r["quote"].lower():
            st = LEVEL_TO_STATUS.get(s.get("level"), "信息不足")
            if st == "符合" and s.get("level") == "会用" and re.search("熟练|精通", r["quote"]):
                st = "部分符合"
            m.update(status=st, profile_evidence=f"{s['name']}：{s.get('level')}　{s.get('evidence', '')}".strip())
            return m
    for e in profile.get("experiences", []):
        if r["topic"] and r["topic"] in (e.get("title", "") + e.get("text", "")):
            m.update(status="部分符合", profile_evidence=e.get("title", ""), source="基于推断")
            return m
    if r["level"] == "软性要求":
        m["note"] = "难以从档案核对，面试中体现"
    return m
