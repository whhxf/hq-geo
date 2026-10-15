#!/usr/bin/env python3
"""排版校验器与提取器的回归测试。

**每条机器判据都要有一个会红的用例。** 只有正向用例的测试等于没测——
判据被改弱了，正向用例照样绿。

金样本是 `templates/article.html` 配 `templates/article-layout.json`：
两份必须互相量得出来，也要都过机器判据。两份一旦漂移，站 4 生成的稿子
就会「声明一套、CSS 一套」，而门禁看不出来。
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
TEMPLATES = HERE.parent / "templates"
sys.path.insert(0, str(SCRIPTS))

import check_layout  # noqa: E402
import extract_html_layout  # noqa: E402
import render  # noqa: E402
import validate_type_spec  # noqa: E402

GOLDEN_LAYOUT = json.loads((TEMPLATES / "article-layout.json").read_text(encoding="utf-8"))
GOLDEN_HTML = (TEMPLATES / "article.html").read_text(encoding="utf-8")
RULES = check_layout.load_rules()


def spec(**overrides) -> dict:
    data = copy.deepcopy(GOLDEN_LAYOUT)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    return data


def fails(data: dict) -> list:
    return check_layout.failures(check_layout.check(data, RULES))


def failed_ids(data: dict) -> set:
    return {item["rule_id"] for item in fails(data)}


class ContrastTests(unittest.TestCase):
    """对比度是唯一一处自己算的数学。算错了整套判据都不可信。"""

    def test_black_on_white_is_21(self):
        self.assertAlmostEqual(check_layout.contrast_ratio("#000000", "#ffffff"), 21.0, places=2)

    def test_same_color_is_1(self):
        self.assertAlmostEqual(check_layout.contrast_ratio("#ffffff", "#ffffff"), 1.0, places=4)

    def test_wcag_aa_boundary(self):
        # #767676 对白是 WCAG 公认的 4.5:1 临界色。算不到 4.5 说明公式错了。
        ratio = check_layout.contrast_ratio("#767676", "#ffffff")
        self.assertGreaterEqual(ratio, 4.5)
        self.assertLess(ratio, 4.6)

    def test_short_hex_and_rgb_and_named(self):
        self.assertEqual(check_layout.parse_color("#fff"), (255, 255, 255))
        self.assertEqual(check_layout.parse_color("#1a1a1a"), (26, 26, 26))
        self.assertEqual(check_layout.parse_color("rgb(26, 26, 26)"), (26, 26, 26))
        self.assertEqual(check_layout.parse_color("white"), (255, 255, 255))

    def test_unparseable_is_none_not_pass(self):
        self.assertIsNone(check_layout.parse_color("var(--x)"))
        self.assertIsNone(check_layout.contrast_ratio("var(--x)", "#ffffff"))


class RuleTests(unittest.TestCase):
    """十二条机器判据，逐条给一个会红的用例。"""

    def test_golden_passes(self):
        self.assertEqual(fails(GOLDEN_LAYOUT), [])

    def test_target_deviation_is_warn_not_fail(self):
        # 行宽 38 汉字：超目标上限 35，但在硬上限 40 以内 → 提示，不是失败。
        items = check_layout.check(spec(measure_chars=38), RULES)
        self.assertEqual([i for i in items if i["rule_id"] == "TY-01"][0]["severity"], "warn")

    def test_ty01_measure_too_long(self):
        self.assertIn("TY-01", failed_ids(spec(measure_chars=45)))

    def test_ty01_measure_too_short(self):
        self.assertIn("TY-01", failed_ids(spec(measure_chars=10)))

    def test_ty02_body_line_height(self):
        self.assertIn("TY-02", failed_ids(spec(line_height={"body": 1.2})))

    def test_ty03_heading_line_height(self):
        self.assertIn("TY-03", failed_ids(spec(line_height={"heading": 1.9})))

    def test_ty04_body_letter_spacing(self):
        self.assertIn("TY-04", failed_ids(spec(letter_spacing_em={"body": 0.3})))

    def test_ty05_heading_letter_spacing(self):
        self.assertIn("TY-05", failed_ids(spec(letter_spacing_em={"heading": 0.0})))

    def test_ty06_indent_and_spacing_together(self):
        self.assertIn("TY-06", failed_ids(spec(first_line_indent_em=2, paragraph_spacing_em=1.75)))

    def test_ty06_indent_alone_is_fine(self):
        self.assertNotIn("TY-06", failed_ids(spec(first_line_indent_em=2, paragraph_spacing_em=0)))

    def test_ty07_heading_scale_not_decreasing(self):
        self.assertIn("TY-07", failed_ids(spec(heading_sizes_px=[22, 30, 18])))

    def test_ty07_equal_sizes_fail(self):
        self.assertIn("TY-07", failed_ids(spec(heading_sizes_px=[20, 20])))

    def test_ty08_body_font_too_small(self):
        self.assertIn("TY-08", failed_ids(spec(font_size_body_px=11)))

    def test_ty09_low_contrast(self):
        self.assertIn("TY-09", failed_ids(spec(colors={"text": "#cccccc", "background": "#ffffff"})))

    def test_ty09_unparseable_color_fails(self):
        self.assertIn("TY-09", failed_ids(spec(colors={"text": "var(--ink)", "background": "#ffffff"})))

    def test_ty10_heading_contrast(self):
        self.assertIn(
            "TY-10",
            failed_ids(spec(colors={"text": "#1a1a1a", "heading": "#bbbbbb", "background": "#ffffff"})),
        )

    def test_ty11_bad_line_break_level(self):
        self.assertIn("TY-11", failed_ids(spec(line_break_level="auto")))

    def test_ty12_cjk_latin_spacing_too_wide(self):
        self.assertIn("TY-12", failed_ids(spec(cjk_latin_spacing_em=0.4)))

    def test_ty13_max_width_too_wide(self):
        self.assertIn("TY-13", failed_ids(spec(max_width_px=1400)))

    def test_ty13_missing_max_width_fails(self):
        data = spec()
        del data["max_width_px"]
        self.assertIn("TY-13", failed_ids(data))

    def test_ty14_missing_human_review_is_warn(self):
        data = spec()
        del data["human_review"]
        items = check_layout.check(data, RULES)
        entry = [i for i in items if i["rule_id"] == "TY-14"][0]
        self.assertEqual(entry["severity"], "warn")

    def test_ty14_human_review_not_passed_fails(self):
        data = spec(human_review={
            "reviewed_by": "x", "reviewed_at": "2026-10-07",
            "verdicts": {"reads_comfortably": "fail", "hierarchy_is_clear": "pass",
                         "style_matches_content": "pass"},
        })
        self.assertIn("TY-14", failed_ids(data))

    def test_missing_field_is_structural_failure(self):
        data = spec()
        del data["line_height"]
        self.assertIn("TY-00", failed_ids(data))


class ExtractorTests(unittest.TestCase):
    """提取器量的必须和声明的一致。对不上说明 CSS 抄错了，或者声明在撒谎。"""

    def test_golden_html_matches_golden_layout(self):
        measured = extract_html_layout.extract(GOLDEN_HTML)
        self.assertEqual(extract_html_layout.compare(measured, GOLDEN_LAYOUT), [])

    def test_measured_golden_passes_machine_rules(self):
        measured = extract_html_layout.extract(GOLDEN_HTML)
        self.assertEqual(check_layout.failures(check_layout.check(measured, RULES)), [])

    def test_measure_comes_from_paragraph_column(self):
        # 容器 700px、正文列 32em=512px。行宽必须取 512/16=32，不是 700/16。
        measured = extract_html_layout.extract(GOLDEN_HTML)
        self.assertEqual(measured["max_width_px"], 700)
        self.assertEqual(measured["measure_chars"], 32)

    def test_css_comments_do_not_break_parsing(self):
        # 回归：注释里的中文说明曾被并进选择器，导致 body 的声明整段读不到，
        # 而脚本不报错，只是量出 null。表现是 line_height.body 变 None。
        measured = extract_html_layout.extract(GOLDEN_HTML)
        self.assertEqual(measured["line_height"]["body"], 1.75)
        self.assertEqual(measured["colors"]["text"], "#1a1a1a")

    def test_compare_catches_declared_drift(self):
        measured = extract_html_layout.extract(GOLDEN_HTML)
        drifted = spec(measure_chars=40)
        self.assertTrue(extract_html_layout.compare(measured, drifted))

    def test_unmeasurable_values_are_none_not_guessed(self):
        measured = extract_html_layout.extract("<html><body><p>只有文字，没有样式</p></body></html>")
        self.assertIsNone(measured["line_height"]["body"])
        self.assertIsNone(measured["colors"]["text"])


class RendererTests(unittest.TestCase):
    def test_source_links_are_clickable_and_safe(self):
        rendered = render.inline_markup('[产品说明](https://example.com/spec?a=1&b=2)')
        self.assertIn('<a href="https://example.com/spec?a=1&amp;b=2">产品说明</a>', rendered)
        self.assertNotIn('<a ', render.inline_markup('[危险](javascript:alert)'))

    def test_article_renderer_contains_actual_draft_and_roles(self):
        roles = {}
        for name, size, kind in [('h1', 32, 'display'), ('h2', 24, 'heading'), ('h3', 20, 'heading'), ('body', 16, 'body'), ('caption', 14, 'caption')]:
            roles[name] = dict(size_px=size, kind=kind, line_height=1.75 if kind in ('body', 'caption') else 1.25, letter_spacing_em=.02 if kind in ('body', 'caption') else .08, weight=400, color='#222222')
        data = dict(roles=roles, background='#ffffff', measure_chars=32, chinese=dict(paragraph_indent_em=0, paragraph_spacing_em=1.75))
        page = render.render_article(data, '<h1>真实标题</h1><p>这是真实成稿。</p>', '真实标题')
        self.assertIn('这是真实成稿。', page)
        self.assertIn('class="tp-h1"', page)
        self.assertIn('<title>真实标题</title>', page)
        self.assertNotIn('{{', page)

    """渲染器不许静默丢参数。

    2026-10-08 实测过两处静默失效，都是「脚本报成功、参数一个没进去」：

    - `cover.html` 的 `:root` 把画布写死，`render_cover` 填的十个值全部丢掉，
      画布恒为 1024×1024，`--tp-bg-image` 永远是 `none`。
    - `article.html` 是手写金样本、一个占位符都没有，`render_article` 的输出
      **与模板逐字节相同**，输入的成稿一个字都没进 HTML。

    共同根因：`_fill` 只查「模板里的占位符填没填」，不查「传进来的值有没有落点」。
    下面的用例两个方向都守。
    """

    COVER_SPEC = {
        "schema_version": 1,
        "id": "cover-unit",
        "surface": "image",
        "background": "#14110E",
        "font_family": '"PingFang SC",sans-serif',
        "canvas": {
            "width": 1080,
            "height": 1440,
            "margin": {"top": 120, "right": 108, "bottom": 160, "left": 108},
            "background_image": "assets/generated/x/base.png",
            "text_layout": "bottom-left",
            "scrim": "linear-gradient(transparent,rgba(0,0,0,.45))",
        },
        "chinese": {"line_break": "strict", "paragraph_indent_em": 0, "paragraph_spacing_em": 1.2},
        "roles": {
            "kicker": {"kind": "caption", "size_px": 30, "line_height": 1.6,
                       "letter_spacing_em": 0.04, "weight": 500, "color": "#E2603A"},
            "headline": {"kind": "display", "size_px": 96, "line_height": 1.15,
                         "letter_spacing_em": 0.06, "weight": 600, "color": "#FFFFFF"},
        },
    }
    COVER_CONTENT = {"kicker": "选型前", "headline": "这 7 个问题\n不问清就别买"}

    def test_fill_rejects_value_with_no_placeholder(self):
        # 模板里没有这个占位符时，replace 什么都不做、也不留残余——
        # 值被静默丢掉，输出看着正常。这一条就是防它。
        with self.assertRaises(render.RenderError) as caught:
            render._fill("<html>干干净净的模板</html>", {"CANVAS_W": 1080})
        self.assertIn("CANVAS_W", str(caught.exception))

    def test_fill_rejects_unfilled_placeholder(self):
        with self.assertRaises(render.RenderError) as caught:
            render._fill("<html>{{CANVAS_W}}</html>", {})
        self.assertIn("CANVAS_W", str(caught.exception))

    def test_fill_accepts_when_both_sides_match(self):
        self.assertEqual(
            render._fill("<html>{{CANVAS_W}}</html>", {"CANVAS_W": 1080}),
            "<html>1080</html>",
        )

    def test_cover_carries_canvas_values_into_html(self):
        page = render.render_cover(self.COVER_SPEC, self.COVER_CONTENT)
        for needle in (
            "--tp-w:1080px",
            "--tp-h:1440px",
            "--tp-mt:120px",
            "--tp-mr:108px",
            "--tp-mb:160px",
            "--tp-ml:108px",
            "--tp-bg-image:url('assets/generated/x/base.png')",
            "--tp-scrim:linear-gradient(transparent,rgba(0,0,0,.45))",
            '--tp-font:"PingFang SC",sans-serif',
            "font-size:96px",
            'data-layout="bottom-left"',
            "不问清就别买",
        ):
            self.assertIn(needle, page)

    def test_cover_html_has_no_leftover_placeholder(self):
        page = render.render_cover(self.COVER_SPEC, self.COVER_CONTENT)
        self.assertNotIn("{{", page)

    def test_canvas_block_comes_after_template_defaults(self):
        # 覆盖块必须写在模板 :root 之后，否则后写的默认值赢，覆盖等于没写。
        page = render.render_cover(self.COVER_SPEC, self.COVER_CONTENT)
        self.assertLess(page.index("--tp-w:1024px"), page.index("--tp-w:1080px"))

    def test_cover_without_base_image_declares_none(self):
        spec_data = copy.deepcopy(self.COVER_SPEC)
        del spec_data["canvas"]["background_image"]
        page = render.render_cover(spec_data, self.COVER_CONTENT)
        self.assertIn("--tp-bg-image:none", page)

    def test_golden_sample_is_not_a_fill_template(self):
        # `article.html` 是手写金样本，一个占位符都没有。
        # 所以 `render_article` 现在明确报错，而不是吐一份和模板逐字节相同的假产出。
        # 要恢复这条路径，得给文章单独一份带占位符的模板——见 BACKLOG。
        with self.assertRaises(render.RenderError):
            render.render_article(self.COVER_SPEC, "<p>正文</p>")

    def test_render_png_clears_stale_target_before_running(self):
        # 旧图在的时候，Chrome 没出图也会被判成功——脚本报「全成功」，图一张没变。
        # 这里把 chrome 换成一个必然失败的命令：旧图必须已经被删掉，且必须报错。
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            html_path = tmp / "page.html"
            png_path = tmp / "page.png"
            html_path.write_text("<html><body>hi</body></html>", encoding="utf-8")
            png_path.write_bytes(b"stale")  # 假装是上一次留下的旧图

            original = render.find_chrome
            render.find_chrome = lambda: shutil.which("false") or "/usr/bin/false"
            try:
                with self.assertRaises(render.RenderError):
                    render.render_png(html_path, png_path, 200, 200)
            finally:
                render.find_chrome = original

            self.assertFalse(png_path.exists(), "旧图没被清掉，失败会被它掩盖")


COVER_SPEC = TEMPLATES / "cover-type-spec.json"


class GoldenCoverSpecTests(unittest.TestCase):
    """封面金样本。站 4 照着它起手——它一旦非法，站 4 每次都要现场编参数。

    它和文章金样本是两个载体、一套规则：`surface` 不同，判据同一份。
    """

    def setUp(self):
        self.spec = json.loads(COVER_SPEC.read_text(encoding="utf-8"))

    def test_golden_cover_spec_is_valid(self):
        self.assertEqual(validate_type_spec.validate(self.spec), [])

    def test_golden_cover_spec_is_an_image_surface(self):
        self.assertEqual(self.spec["surface"], "image")
        self.assertIn("canvas", self.spec)

    def test_golden_cover_renders_without_leftover_placeholder(self):
        page = render.render_cover(
            self.spec,
            {"kicker": "AGENT SKILL", "headline": "让 AI 把重复工作包了", "meta": "01 — 工具"},
        )
        for needle in ("--tp-w:1080px", "--tp-h:1440px",
                       'data-layout="bottom-left"', "让 AI 把重复工作包了"):
            self.assertIn(needle, page)
        self.assertNotIn("{{", page)

    def test_low_contrast_headline_is_rejected(self):
        """判据必须会红：把标题换成 2.18:1 的浅赭，校验器要拦下来。

        这个色就是宝玉那张封面的副标题色——照抄会过不了系统自己的判据。
        """
        broken = copy.deepcopy(self.spec)
        broken["roles"]["headline"]["color"] = "#D3A088"
        self.assertTrue(validate_type_spec.validate(broken))


def main() -> int:
    suite = unittest.TestSuite()
    for case in (ContrastTests, RuleTests, ExtractorTests, RendererTests,
                 GoldenCoverSpecTests):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if result.wasSuccessful():
        print(f"PASS typography unit: {result.testsRun} 个用例全过")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
