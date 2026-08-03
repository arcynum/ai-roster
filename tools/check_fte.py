import datetime
from models import parse_staff

def check_fte():
    with open("staff.yaml", "r") as f:
        staff = parse_staff(f.read())
    total_fte = sum(s.contracted_hours_per_fortnight for s in staff)
    print(f"Total contracted hours per fortnight: {total_fte}")

if __name__ == "__main__":
    check_fte()
