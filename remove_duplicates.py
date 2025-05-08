#!/usr/bin/env python3

with open("tests/functional/test_appointments.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Range of lines for first duplicate function to remove (with some buffer)
to_remove1 = range(675, 713)  # test_change_status_to_completed_without_payment_method
# Range of lines for second duplicate function to remove (with some buffer)
to_remove2 = range(813, 858)  # test_change_status_to_cancelled

with open("tests/functional/test_appointments.py", "w", encoding="utf-8") as f:
    for i, line in enumerate(lines, 1):  # 1-indexed to match line numbers
        if i not in to_remove1 and i not in to_remove2:
            f.write(line)

print("Removed the duplicate test functions")
