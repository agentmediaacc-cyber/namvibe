import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from services.supabase_safe import safe_select
from services.profile_service import get_profile_bundle


def main():
    app = create_app()
    with app.app_context():
        rows = safe_select("chain_profiles", columns="id,username,profile_completed", limit=20) or []
        profile = None
        for row in rows:
            if row.get("id"):
                profile = row
                if row.get("profile_completed"):
                    break

        if not profile:
            print("found_profile=False")
            return

        profile_id = str(profile["id"])
        with app.test_request_context(f"/dev/profile-bundle/{profile_id}"):
            bundle = get_profile_bundle(profile_id=profile_id)
            print("found_profile=True")
            print(f"profile_completed={bool(profile.get('profile_completed'))}")
            print(f"bundle_exists={bool(bundle)}")
            if not bundle:
                return
            print(f"profile_present={bool(bundle.get('profile'))}")
            print(f"age_gate_required={bool(bundle.get('age_gate_required'))}")
            print(f"age_restricted={bool(bundle.get('age_restricted'))}")
            print(f"restricted_view={bool(bundle.get('restricted_view'))}")
            stats = bundle.get("stats") or {}
            content = bundle.get("content") or {}
            wallet = bundle.get("wallet") or {}
            creator_tools = bundle.get("creator_tools") or {}
            print(f"stats_keys={sorted(stats.keys())}")
            print(f"content_posts={len(content.get('posts', []))}")
            print(f"content_reels={len(content.get('reels', []))}")
            print(f"content_rooms={len(content.get('rooms', []))}")
            print(f"wallet_present={bool(wallet)}")
            print(f"creator_tools_present={bool(creator_tools)}")


if __name__ == "__main__":
    main()
