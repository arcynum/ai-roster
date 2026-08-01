import datetime
from models import TRAINING_MAP, StaffMember

# Mock data based on what I read
staff = [
    StaffMember("Amanda Bartley", "CN", "Shift Coordinator", 56),
    StaffMember("Jennifer Brodie", "CN", "Shift Coordinator", 48),
    StaffMember("Michelle Caine", "CN", "Shift Coordinator", 72),
    StaffMember("Christine Cardos", "CN", "Shift Coordinator", 72),
    StaffMember("Tracey Cole", "CN", "Shift Coordinator", 72),
    StaffMember("Kellie Fursdon", "CN", "Shift Coordinator", 56),
    StaffMember("Katie Gay", "CN", "Shift Coordinator", 64),
    StaffMember("Shiny Joy", "CN", "Shift Coordinator", 76),
    StaffMember("Sandy Manderson", "CN", "Shift Coordinator", 56),
    StaffMember("Tanya Mountford", "CN", "Shift Coordinator", 8),
    StaffMember("Premshankar Ramachandran", "CN", "Shift Coordinator", 72),
    StaffMember("Laura Rogers", "CN", "Shift Coordinator", 64),
    StaffMember("Jodie Bullock", "CN", "Shift Coordinator", 64),
    StaffMember("Suzanne Coughlan", "RN", "Shift Coordinator", 40),
    StaffMember("Ange Cowper", "RN", "Shift Coordinator", 48),
    StaffMember("Alexia Fallis", "RN", "Shift Coordinator", 72),
    StaffMember("Rebekah Gillespie", "RN", "Shift Coordinator", 32),
    StaffMember("Danielle Hardley", "CN", "Shift Coordinator", 24),
    StaffMember("Lauren Hodge", "RN", "Shift Coordinator", 48),
    StaffMember("Resmi Joseph", "RN", "Shift Coordinator", 72),
    StaffMember("Alexandra Lyons", "RN", "Shift Coordinator", 32),
    StaffMember("Nisha Mathew", "RN", "Shift Coordinator", 64),
    StaffMember("Irina Ovsyankina", "RN", "Shift Coordinator", 64),
    StaffMember("Bec Rafter", "RN", "Shift Coordinator", 64),
    StaffMember("Rebecca Trew", "RN", "Shift Coordinator", 32),
    StaffMember("Allie O'Brien", "RN", "Triage", 56),
    StaffMember("Shana Stokes", "RN", "Triage", 56),
    StaffMember("Maddy Thompson", "RN", "Triage", 64),
    StaffMember("Alyce Tozer", "RN", "Triage", 40),
    StaffMember("Jodie Armstrong", "RN", "Resus", 64),
    StaffMember("Jehan Musasinghe", "RN", "Resus", 64),
    StaffMember("Jessica O'Neill-Yee", "RN", "Resus", 48),
    StaffMember("Cynthia Tran", "RN", "Resus", 48),
    StaffMember("Alex Babu", "RN", "Acute", 64),
    StaffMember("Brianna Born", "RN", "Acute", 56),
    StaffMember("Luca Brahn", "RN", "Acute", 56),
    StaffMember("Olivia Knowles", "RN", "Acute", 72),
    StaffMember("Olivia Ots", "RN", "Acute", 64),
    StaffMember("Charlee Rayner", "RN", "Acute", 56),
    StaffMember("Nicola Odessa", "RN", "Graduate", 56),
    StaffMember("Rianna Rimpos", "RN", "Graduate", 56),
    StaffMember("Rose Turner", "RN", "Graduate", 56),
]

def check():
    # Count available training levels
    counts = {level: 0 for level in ["Graduate", "Acute", "Resus", "Triage", "Shift Coordinator"]}
    for s in staff:
        counts[s.training_level] += 1
    print(f"Training counts: {counts}")

    # Requirements per day (based on roster.md)
    # D12 needs: CN, Coord, Triage, Resus
    # N12 needs: CN, Coord, Triage, Resus
    # Total requirements for 14 days:
    req_coord = 14 * 2 # one per D12 and N12
    req_triage = 14 * 2
    req_resus = 14 * 2
    req_cn = 14 * 2
    
    print(f"Total Coord needed: {req_coord}")
    print(f"Total Triage needed: {req_triage}")
    print(f"Total Resus needed: {req_resus}")

    # How many people can fulfill these?
    can_do_coord = sum(1 for s in staff if TRAINING_MAP.get(s.training_level, 0) >= 4)
    can_do_triage = sum(1 for s in staff if TRAINING_MAP.get(s.training_level, 0) >= 3)
    can_do_resus = sum(1 for s in staff if TRAINING_MAP.get(s.training_level, 0) >= 2)

    print(f"People who can do Coord: {can_do_coord}")
    print(f"People who can do Triage: {can_do_triage}")
    print(f"People who can do Resus: {can_do_resus}")

check()
