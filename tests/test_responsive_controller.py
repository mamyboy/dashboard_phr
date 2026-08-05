import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class ResponsiveControllerTests(unittest.TestCase):
    def test_breakpoint_profiles_cover_target_devices(self):
        script = """
const {ResponsiveChartController}=require('./responsive_chart_controller.js');
const widths=[360,390,430,768,1024,1025];
console.log(JSON.stringify(widths.map(w=>ResponsiveChartController.profileForWidth(w))));
"""
        result = subprocess.run(
            ["node", "-e", script], cwd=ROOT, text=True, capture_output=True, check=True
        )
        profiles = json.loads(result.stdout)
        self.assertEqual(
            [profile["name"] for profile in profiles],
            ["phone-xs", "phone-sm", "phone", "tablet", "laptop", "desktop"],
        )
        self.assertEqual([profile["phone"] for profile in profiles], [True, True, True, False, False, False])
        self.assertEqual([profile["tablet"] for profile in profiles], [True, True, True, True, True, False])

    def test_generator_embeds_controller_and_container_queries(self):
        source = ROOT.joinpath("analyze_daily_interactive.py").read_text(encoding="utf-8")
        self.assertIn("/*__RESPONSIVE_CONTROLLER__*/", source)
        self.assertIn("container-type:inline-size", source)
        self.assertIn("@container dashboard-card (max-width:430px)", source)
        self.assertIn("new ResponsiveChartController", source)
        self.assertIn("responsiveController.start()", source)
        self.assertNotIn("window.addEventListener('resize',()=>", source)


if __name__ == "__main__":
    unittest.main()
