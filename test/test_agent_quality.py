# AI招聘助手 - 回答质量自检测试脚本
import sys, os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

class MockTool:
    def __init__(self, func): self.func = func
    def invoke(self, d): return self.func(**d)

SAMPLE_RESUME_TEXT = "隐私信息：姓名(脱敏)、电话(脱敏)、邮箱(脱敏) 【教育背景】最高学历：硕士 | 北京大学 | 软件工程 | 2019年7月 【全职工作经历】2019年8月-2022年11月 | 北京XX科技 | 后端开发 2022年12月-2025年4月 | 上海XX数据 | 高级后端工程师 【核心技能】Python、Golang、Java、Django、Redis、Kafka、MySQL 【项目经验】电商订单中台重构(核心开发 接口响应提升45%%) 用户画像分析系统(项目负责人 千万级用户数据建模)"
SAMPLE_JD = "后端开发工程师 岗位职责：负责电商平台、用户系统后端开发与性能优化 任职要求：本科及以上，3年及以上Python/Java后端开发经验 熟练使用MySQL、Redis、Kafka，有微服务经验优先。"
MOCK_PARSE_JSON = '{"education":{"degree":"硕士","school":"北京大学"}}'

class TestGuardNode:
    def test_guard_irrelevant_weather(self):
        from backend.src.tools.guard import content_guard
        r = content_guard("今天天气怎么样")
        assert r["allow_pass"] is False
        assert "暂不解答" in r["reply"]
        print("  [PASS] TC-G01: 天气闲聊拦截")

    def test_guard_irrelevant_movie(self):
        from backend.src.tools.guard import content_guard
        r = content_guard("最近有什么好看的电影推荐吗")
        assert r["allow_pass"] is False
        print("  [PASS] TC-G02: 电影闲聊拦截")

    def test_guard_irrelevant_chat_game(self):
        from backend.src.tools.guard import content_guard
        assert content_guard("我们来聊聊天吧")["allow_pass"] is False
        assert content_guard("最近有什么好玩的游戏")["allow_pass"] is False
        print("  [PASS] TC-G03+G04: 聊天/游戏拦截")

    def test_guard_business(self):
        from backend.src.tools.guard import content_guard
        for t in ["帮我解析这份简历","我想约个面试","帮我评估一下这个候选人"]:
            assert content_guard(t)["allow_pass"] is True
        print("  [PASS] TC-G05~07: 简历/面试/评估放行")

    def test_guard_empty(self):
        from backend.src.tools.guard import content_guard
        assert content_guard("")["allow_pass"] is False
        print("  [PASS] TC-G08: 空输入拦截")

    def test_guard_mixed_priority(self):
        from backend.src.tools.guard import keyword_check
        r = keyword_check("今天天气怎么样，我想找招聘信息")
        assert r is False
        print("  [PASS] TC-G09: IGNORE优先策略确认")

class TestIntentDetection:
    def test_only_parse(self):
        from backend.src.agent import detect_user_intent
        for inp in ["解析简历","读取简历","提取简历信息","看下简历"]:
            assert detect_user_intent(inp) == "only_parse"
        print("  [PASS] TI-01: 仅解析意图识别")

    def test_full_evaluate(self):
        from backend.src.agent import detect_user_intent
        for inp in ["人岗匹配","综合评估","风险审查","简历打分","合不合适"]:
            assert detect_user_intent(inp) == "full_evaluate"
        print("  [PASS] TI-02: 综合评估意图识别")

    def test_unknown(self):
        from backend.src.agent import detect_user_intent
        assert detect_user_intent("你好") == "unknown"
        assert detect_user_intent("") == "unknown"
        print("  [PASS] TI-03: 无关->unknown")

class TestAgentPipeline:
    def setup_mock(self, agent_mod):
        self._called = []
        self._saved = (agent_mod.resume_parse_tool, agent_mod.resume_job_match, agent_mod.resume_risk_check, agent_mod.GLOBAL_RESUME_CACHE)
        def mock_parse(**kw): self._called.append("parser"); return MOCK_PARSE_JSON
        def mock_match(**kw): self._called.append("matcher"); return "【人岗匹配评估报告】得分85"
        def mock_risk(**kw): self._called.append("risk"); return "【用工风控审查报告】低风险"
        agent_mod.resume_parse_tool = MockTool(mock_parse)
        agent_mod.resume_job_match = MockTool(mock_match)
        agent_mod.resume_risk_check = MockTool(mock_risk)
        agent_mod.GLOBAL_RESUME_CACHE = None

    def restore(self, agent_mod):
        (agent_mod.resume_parse_tool, agent_mod.resume_job_match, agent_mod.resume_risk_check, agent_mod.GLOBAL_RESUME_CACHE) = self._saved

    def test_only_parse_no_matcher_risk(self):
        import backend.src.agent as m
        self.setup_mock(m)
        try:
            from backend.src.agent import run_agent
            r = run_agent("解析简历 " + SAMPLE_RESUME_TEXT[:60])
            assert "parser" in self._called, f"parser应调用, 实际: {self._called}"
            assert "matcher" not in self._called, f"matcher不应调用! {self._called}"
            assert "risk" not in self._called, f"risk不应调用! {self._called}"
            print("  [PASS] TC-A01: 仅解析->只调parser")
        finally:
            self.restore(m)

    def test_full_evaluate_calls_all(self):
        import backend.src.agent as m
        self.setup_mock(m)
        try:
            from backend.src.agent import run_agent
            r = run_agent("人岗匹配评估 " + SAMPLE_RESUME_TEXT[:60], job_jd=SAMPLE_JD)
            assert "parser" in self._called, f"parser应调用, 实际: {self._called}"
            assert "matcher" in self._called, f"matcher应调用, 实际: {self._called}"
            assert "risk" in self._called, f"risk应调用, 实际: {self._called}"
            assert "人岗匹配评估报告" in r
            assert "用工风控审查报告" in r
            print("  [PASS] TC-A02: 人岗匹配->parser+matcher+risk")
        finally:
            self.restore(m)

    def test_full_evaluate_no_jd(self):
        import backend.src.agent as m
        self.setup_mock(m)
        try:
            from backend.src.agent import run_agent
            r = run_agent("人岗匹配评估 " + SAMPLE_RESUME_TEXT[:60], job_jd="")
            assert "请提供" in r or "岗位JD" in r
            print("  [PASS] TC-A03: 无JD提示提供")
        finally:
            self.restore(m)

    def test_full_evaluate_uses_cache(self):
        import backend.src.agent as m
        self.setup_mock(m)
        m.GLOBAL_RESUME_CACHE = MOCK_PARSE_JSON
        try:
            from backend.src.agent import run_agent
            r = run_agent("人岗匹配", job_jd=SAMPLE_JD)
            assert "parser" not in self._called, f"有缓存不应调parser, 实际: {self._called}"
            assert "matcher" in self._called
            assert "risk" in self._called
            print("  [PASS] TC-A04: 缓存复用")
        finally:
            self.restore(m)

    def test_short_input(self):
        from backend.src.agent import run_agent
        r = run_agent("解析简历")
        assert "完整" in r or "简历内容" in r
        print("  [PASS] TC-A05: 短输入提示")

if __name__ == "__main__":
    import traceback
    passed = 0; failed = 0
    for cls in [TestGuardNode, TestIntentDetection, TestAgentPipeline]:
        print(); print("="*60); print("【{}】".format(cls.__name__)); print("="*60)
        inst = cls()
        for m in dir(inst):
            if not m.startswith("test_"): continue
            try:
                getattr(inst, m)(); passed += 1
            except Exception as e:
                failed += 1; print("  [FAIL] {}: {}".format(m, e)); traceback.print_exc()
    print(); print("="*60)
    print("测试总结: 通过 {} / 共 {}".format(passed, passed + failed))
    if failed == 0: print("  全部通过!")
    print("="*60)