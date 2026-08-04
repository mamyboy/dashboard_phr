import unittest
from pathlib import Path


class MobileChartLayoutTests(unittest.TestCase):
    def test_mobile_horizontal_charts_use_numbered_axis_and_html_category_key(self):
        source = Path(__file__).parents[1].joinpath("analyze_daily_interactive.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("function renderMobileCategoryKey(el,items)", source)
        self.assertIn(
            "labels=items.map((i,n)=>p.phone?String(n+1):wrapChartLabel(i.name,maxChars))",
            source,
        )
        self.assertIn("renderMobileCategoryKey(el,items);", source)
        self.assertIn(".mobile-category-key{display:none}", source)
        self.assertIn(".mobile-category-key{display:grid", source)
        self.assertIn(
            "afterFit:axis=>{if(p.phone)axis.width=Math.min(axis.width,32);}", source
        )
        self.assertNotIn(
            ".chartjs-box.chart-horizontal .chart-stage{width:640px;min-width:640px}",
            source,
        )


if __name__ == "__main__":
    unittest.main()
