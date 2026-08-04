import unittest
from pathlib import Path


class MobileChartLayoutTests(unittest.TestCase):
    def test_mobile_horizontal_charts_use_compact_single_line_categories(self):
        source = Path(__file__).parents[1].joinpath("analyze_daily_interactive.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("function compactMobileCategory(value)", source)
        self.assertIn(
            "labels=items.map(i=>p.phone?compactMobileCategory(i.name):wrapChartLabel(i.name,maxChars))",
            source,
        )
        self.assertIn(
            "afterFit:axis=>{if(p.phone)axis.width=Math.min(axis.width,118);}", source
        )
        self.assertNotIn(
            ".chartjs-box.chart-horizontal .chart-stage{width:640px;min-width:640px}",
            source,
        )


if __name__ == "__main__":
    unittest.main()
