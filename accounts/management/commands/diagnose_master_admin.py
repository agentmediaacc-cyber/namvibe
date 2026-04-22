from django.core.management.base import BaseCommand
from django.db.utils import OperationalError

from accounts.services import master_admin_diagnostic_snapshot


class Command(BaseCommand):
    help = "Inspect how the configured master-admin identity resolves against local Django rows."

    def handle(self, *args, **options):
        try:
            snapshot = master_admin_diagnostic_snapshot()
        except OperationalError as exc:
            self.stdout.write("Configured master admin")
            self.stdout.write("  email: kasera@namvibe.com")
            self.stdout.write("  supabase_uid: 2319f827-fc3c-46ce-9239-b350312a0d6f")
            self.stdout.write("\nLocal row inspection")
            self.stdout.write(f"  unavailable: {exc}")
            self.stdout.write("  note: live DB access is required to inspect or repair local Django rows.")
            return

        canonical_user = snapshot["canonical_user"]
        canonical_role = snapshot["canonical_role"]

        self.stdout.write("Configured master admin")
        self.stdout.write(f"  email: {snapshot['configured_email'] or '(unset)'}")
        self.stdout.write(f"  supabase_uid: {snapshot['configured_supabase_uid'] or '(unset)'}")

        self.stdout.write("\nCanonical local target")
        if canonical_user and canonical_role:
            self.stdout.write(
                f"  user_id={canonical_user.id} username={canonical_user.username} "
                f"email={canonical_user.email} role={canonical_role.role} supabase_uid={canonical_role.supabase_uid or '(blank)'}"
            )
        else:
            self.stdout.write("  No local Django user currently matches the configured master-admin identity.")

        self.stdout.write("\nEmail matches")
        if snapshot["matching_email_roles"]:
            for role in snapshot["matching_email_roles"]:
                self.stdout.write(
                    f"  user_id={role.user_id} username={role.user.username} role={role.role} "
                    f"supabase_uid={role.supabase_uid or '(blank)'}"
                )
        else:
            self.stdout.write("  None")

        self.stdout.write("\nSupabase UID matches")
        if snapshot["matching_uid_roles"]:
            for role in snapshot["matching_uid_roles"]:
                self.stdout.write(
                    f"  user_id={role.user_id} username={role.user.username} role={role.role} "
                    f"supabase_uid={role.supabase_uid or '(blank)'}"
                )
        else:
            self.stdout.write("  None")

        self.stdout.write("\nRows that would be bypassed or normalized")
        if snapshot["bypass_roles"]:
            for role in snapshot["bypass_roles"]:
                self.stdout.write(
                    f"  user_id={role.user_id} username={role.user.username} role={role.role} "
                    f"supabase_uid={role.supabase_uid or '(blank)'}"
                )
        else:
            self.stdout.write("  None")

        self.stdout.write(
            f"\nRepair needed: {'yes' if snapshot['would_repair'] else 'no'}"
        )
