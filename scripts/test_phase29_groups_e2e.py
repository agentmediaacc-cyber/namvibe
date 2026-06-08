import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _ensure_project_python():
    try:
        import dotenv  # noqa: F401
    except ModuleNotFoundError:
        venv_python = ROOT / "venv" / "bin" / "python3"
        if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
            os.execv(str(venv_python), [str(venv_python), *sys.argv])
        raise

_ensure_project_python()

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from services import group_feature_service as groups


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def main():
    owner = str(uuid.uuid4())
    member = str(uuid.uuid4())
    private_member = str(uuid.uuid4())

    public = groups.create_group(owner, "Public Phase29", visibility="public")
    assert_true(public["ok"], "public group failed")
    group_id = public["group"]["id"]
    assert_true(groups.join_public_group(group_id, member)["status"] == "joined", "join public failed")
    assert_true(groups.invite_link(group_id).get("invite_link"), "invite link missing")
    assert_true(groups.create_group_post(group_id, member, "hello group")["ok"], "group message failed")
    assert_true(groups.create_group_post(group_id, owner, "announcement", post_type="announcement")["ok"], "announcement failed")

    private = groups.create_group(owner, "Private Phase29", visibility="private")
    assert_true(private["ok"], "private group failed")
    assert_true(groups.request_join(private["group"]["id"], private_member)["status"] == "pending", "private request failed")

    print("phase29 groups e2e: ok")


if __name__ == "__main__":
    main()
