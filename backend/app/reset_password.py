"""Reset a password from the machine that runs Trellis:
    docker compose exec api python -m app.reset_password [person_id]
Asks for the new password twice. Without person_id and with one account, that account is used."""
import getpass
import sys

from . import auth, graph


def main():
    people = graph.run("MATCH (p:Person) WHERE p.password_hash IS NOT NULL RETURN p.id AS id, p.name AS name ORDER BY p.name")
    wanted = sys.argv[1] if len(sys.argv) > 1 else None
    if not people:
        print("No account has a password yet: open Trellis in the browser and finish the setup screen."); return 1
    if wanted is None and len(people) > 1:
        print("Several accounts. Say which one: " + ", ".join(p["id"] for p in people)); return 1
    person = next((p for p in people if p["id"] == wanted), None) if wanted else people[0]
    if not person:
        print(f"No account '{wanted}'. Accounts: " + ", ".join(p["id"] for p in people)); return 1
    first = getpass.getpass(f"New password for {person['name']} ({person['id']}): ")
    if len(first) < 8:
        print("At least 8 characters."); return 1
    if getpass.getpass("Repeat: ") != first:
        print("The two entries differ. Nothing changed."); return 1
    graph.run("MATCH (p:Person {id:$pid}) SET p.password_hash=$hash", pid=person["id"], hash=auth.hash_password(first))
    print(f"Password changed for {person['name']} ({person['id']}). Existing browser sessions stay valid for up to 30 days.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
