import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SOURCE = ROOT.joinpath("analyze_daily_interactive.py")
OUTPUT = ROOT.joinpath("index.html")


class UnitResponseDimensionTests(unittest.TestCase):
    def test_generated_dashboard_javascript_parses(self):
        html = OUTPUT.read_text(encoding="utf-8")
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
        self.assertGreaterEqual(len(scripts), 3)
        dashboard_script = scripts[-1]
        result = subprocess.run(
            ["node", "--check", "-"],
            input=dashboard_script,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generator_contains_interactive_unit_response_dimension(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('id="unitResponseKpis"', source)
        self.assertIn('id="unitResponseChart"', source)
        self.assertIn('id="unitResponseInsight"', source)
        for mode in ("answered", "delta", "pending"):
            self.assertIn(f'data-response-mode="{mode}"', source)
        self.assertIn("function unitResponseMetrics(unit,latestIdx,baselineIdx)", source)
        self.assertIn("pending:Math.max(0,masks-answered)", source)
        self.assertIn("function renderUnitResponse()", source)
        self.assertIn("hbar(document.getElementById('unitResponseChart')", source)
        render_all = re.search(r"function renderAll\(\)\{([^}]*)\}", source)
        if render_all is None:
            self.fail("renderAll() was not found")
        self.assertIn("renderUnitResponse();", render_all.group(1))

    def test_facility_table_exposes_and_sorts_response_metrics(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("'ตอบกลับ','ยังไม่ตอบ','อัตราตอบกลับ'", source)
        self.assertIn("if(k==='answered')", source)
        self.assertIn("if(k==='pending')", source)
        self.assertIn("if(k==='responseRate')", source)
        self.assertIn("return 'answered'", source)
        self.assertIn("return 'pending'", source)
        self.assertIn("return 'responseRate'", source)

    def test_facility_table_headers_follow_selected_date_range(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("...activeIdx().map(i=>DATA.labels[i])", source)
        self.assertIn("const n=activeIdx().length", source)

    def test_response_chart_keeps_long_details_out_of_phone_canvas(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("item.keyDetail", source)
        self.assertIn("items[c.dataIndex].tooltipExtra", source)
        self.assertIn("keyDetail:", source)
        self.assertIn("tooltipExtra:", source)

    def test_chartjs_hbars_never_receive_svg_gradient_urls(self):
        source = SOURCE.read_text(encoding="utf-8")
        for gradient in ("gA", "gB", "gC"):
            self.assertNotIn(f"color:'url(#{gradient})'", source)


if __name__ == "__main__":
    unittest.main()
