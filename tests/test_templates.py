import unittest
from jinja2 import Environment, FileSystemLoader

class TestTemplates(unittest.TestCase):
    def test_all_templates_compile(self):
        env = Environment(loader=FileSystemLoader("app/templates"))
        templates = [
            "academic.html", "ai_advisory.html", "availability.html",
            "base.html", "editor.html", "electives.html", "excel_tools.html",
            "faculty.html", "generate.html", "login.html",
            "officer_dashboard.html", "rooms_labs.html", "subjects.html",
            "teacher_dashboard.html", "validation.html", "viewer.html"
        ]
        errors = []
        for tmpl_name in templates:
            try:
                env.get_template(tmpl_name)
            except Exception as e:
                errors.append(f"{tmpl_name}: {type(e).__name__} - {e}")

        if errors:
            self.fail("Template syntax errors:\n" + "\n".join(errors))

if __name__ == "__main__":
    unittest.main()
