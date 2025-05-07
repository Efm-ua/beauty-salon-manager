import re

with open("tests/functional/test_reports.py", "r") as f:
    content = f.read()

pattern = re.compile(
    r"@patch\(\"app\.routes\.reports\.current_user\"\)\ndef test_financial_report_complete_payment_methods_coverage[\s\S]*?def test_financial_report_with_discount"
)
match = pattern.search(content)

if match:
    start_idx = match.start()
    end_idx = match.end() - len("def test_financial_report_with_discount")
    new_content = (
        content[:start_idx]
        + "def test_financial_report_with_discount"
        + content[end_idx + len("def test_financial_report_with_discount") :]
    )
    with open("tests/functional/test_reports.py", "w") as f:
        f.write(new_content)
    print("Successfully removed duplicate test function")
else:
    print("Pattern not found")
