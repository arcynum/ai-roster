import datetime
from models import parse_staff

def check_fte():
    with open("staff.md", "r") as f:
        staff = parse_staff(f.read())
    total_fte = sum(s.fte_hours for s in staff)
    print(f"Total FTE hours per fortnight: {total_fte}")

if __name__ == "__main__":
    check_fte()
