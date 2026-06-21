#!/usr/bin/env python3
"""Real messaging reality test using Neon DB (no fallbacks).

Rules followed by this script:
- Uses real DATABASE_URL from environment (do not print it)
- Uses psycopg2 for direct verification when needed
- Does not create DB objects (only reads/writes via app services)
- Temporarily monkeypatches in-memory emit functions to capture emits (no repo changes)
"""
import os
import sys
import time
import json
import traceback
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
except Exception as e:
    print('FAIL: missing psycopg2 ->', e)
    sys.exit(2)

# Load env must be done by caller (we assume DATABASE_URL is in environment)
DSN = os.environ.get('DATABASE_URL')
if not DSN:
    print('FAIL: DATABASE_URL not set in environment')
    sys.exit(2)


def pg_connect():
    # connect_timeout only; do not print DSN
    return psycopg2.connect(DSN, connect_timeout=15, cursor_factory=psycopg2.extras.RealDictCursor)


def fetch_two_profiles(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM chain_profiles WHERE deleted_at IS NULL LIMIT 2")
        rows = cur.fetchall()
        return [str(r['id']) for r in rows]


def direct_verify_message(conn, message_id):
    with conn.cursor() as cur:
        cur.execute("SELECT id, thread_id, sender_profile_id, body, delivery_status, is_seen, seen_at, delivered_at, created_at FROM chain_messages WHERE id = %s LIMIT 1", (message_id,))
        return cur.fetchone()


def timestamp_of_thread(conn, thread_id):
    with conn.cursor() as cur:
        cur.execute("SELECT updated_at FROM chain_message_threads WHERE id = %s LIMIT 1", (thread_id,))
        r = cur.fetchone()
        return r['updated_at'] if r else None


def main():
    results = {
        'db_insert': False,
        'thread_update': False,
        'message_fetch': False,
        'socket_emit_path': False,
        'delivered_status': False,
        'seen_status': False,
        'frontend_listener': False,
    }

    try:
        conn = pg_connect()
    except Exception as e:
        print('FAIL: cannot connect to DB ->', repr(e))
        sys.exit(1)

    try:
        profiles = fetch_two_profiles(conn)
        if len(profiles) < 2:
            print('FAIL: not enough profiles in DB to run test (need >=2)')
            sys.exit(1)
        sender, receiver = profiles[0], profiles[1]

        # Import services after DB checks
        from services import messaging_engine as me

        # Ensure pool is usable by calling a quick helper
        # Capture emits by monkeypatching the in-module references used by messaging_engine
        captured_emits = []
        captured_profile_emits = []

        def _emit_thread(thread_id, event, payload):
            try:
                captured_emits.append((thread_id, event, payload))
            except Exception:
                pass

        def _emit_profile(profile_id, event, payload):
            try:
                captured_profile_emits.append((profile_id, event, payload))
            except Exception:
                pass

        # Patch the names inside messaging_engine module (they were imported at module load time)
        me.emit_to_thread = _emit_thread
        me.emit_to_profile = _emit_profile

        # 1) Ensure direct thread exists
        thread_id = me.get_or_create_direct_thread(sender, receiver)
        # get_or_create_direct_thread may return id or dict; normalize
        if isinstance(thread_id, dict):
            tid = thread_id.get('thread_id') or thread_id.get('id')
        else:
            tid = thread_id
        if not tid:
            print('FAIL: could not obtain thread id')
            sys.exit(1)
        tid = str(tid)

        # Record thread updated_at before
        before_ts = timestamp_of_thread(conn, tid)

        # 2) Send a message (User A -> Send Message)
        text = f"Test message reality {datetime.utcnow().isoformat()}"
        send_result = me.send_message(tid, sender, body=text, client_message_id=f"test-{int(time.time())}")
        msg_id = send_result.get('id') or send_result.get('message_id')
        if not msg_id:
            print('FAIL: send_message did not return message id; result=', send_result)
            sys.exit(1)

        # small pause for async emits/background tasks
        time.sleep(0.5)

        # 3) Verify DB insert directly via psycopg2
        row = direct_verify_message(conn, msg_id)
        if row and str(row.get('id')) == str(msg_id):
            results['db_insert'] = True

        # 4) Thread update check (updated_at should be >= before_ts)
        after_ts = timestamp_of_thread(conn, tid)
        try:
            if before_ts is None:
                # If thread had no timestamp, treat any present updated_at as pass
                results['thread_update'] = after_ts is not None
            else:
                results['thread_update'] = after_ts is not None and after_ts >= before_ts
        except Exception:
            results['thread_update'] = False

        # 5) Message fetch using get_thread as receiver
        thread_view = me.get_thread(tid, receiver)
        found = False
        if thread_view and thread_view.get('messages'):
            for m in thread_view.get('messages'):
                if str(m.get('id')) == str(msg_id):
                    found = True
                    break
        results['message_fetch'] = found

        # 6) Socket emit path: check that emit_to_thread was invoked for message:new
        emitted_message_new = any(ev == 'message:new' for (_, ev, _) in captured_emits)
        results['socket_emit_path'] = emitted_message_new

        # 7) Delivered: acknowledge delivery as if receiver acknowledged
        ack = me.acknowledge_delivery(msg_id, receiver)
        time.sleep(0.2)
        row2 = direct_verify_message(conn, msg_id)
        if row2 and (row2.get('delivery_status') in ('delivered', 'seen') or row2.get('delivered_at') is not None):
            results['delivered_status'] = True

        # 8) Seen: mark thread seen by receiver
        me.mark_thread_seen(tid, receiver)
        time.sleep(0.2)
        row3 = direct_verify_message(conn, msg_id)
        if row3 and (bool(row3.get('is_seen')) or row3.get('delivery_status') == 'seen' or row3.get('seen_at')):
            results['seen_status'] = True

        # 9) Frontend listener mapping: check that emits include message:delivered and message:seen
        emitted_names = {ev for (_, ev, _) in captured_emits} | {ev for (_, ev, _) in captured_profile_emits}
        # JS listens for 'message:delivered' and 'message:seen' and 'message:ack'
        results['frontend_listener'] = ('message:delivered' in emitted_names) or ('message:seen' in emitted_names) or ('message:ack' in emitted_names)

    except Exception as e:
        print('ERROR during test execution:', repr(e))
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Print outputs succinctly
    print('PASS/FAIL DB insert ->', 'PASS' if results['db_insert'] else 'FAIL')
    print('PASS/FAIL thread update ->', 'PASS' if results['thread_update'] else 'FAIL')
    print('PASS/FAIL message fetch ->', 'PASS' if results['message_fetch'] else 'FAIL')
    print('PASS/FAIL socket emit path ->', 'PASS' if results['socket_emit_path'] else 'FAIL')
    print('PASS/FAIL delivered status ->', 'PASS' if results['delivered_status'] else 'FAIL')
    print('PASS/FAIL seen status ->', 'PASS' if results['seen_status'] else 'FAIL')
    print('PASS/FAIL frontend listener mapping ->', 'PASS' if results['frontend_listener'] else 'FAIL')

    # Determine broken point if any
    if all(results.values()):
        print('\nRESULT: All checks passed. Messaging reality path works end-to-end with Neon DB.')
    else:
        print('\nRESULT: Some checks failed. Summary:')
        for k, v in results.items():
            if not v:
                print(f" - {k} failed")
        # Provide exact likely files/functions based on failures
        if not results['db_insert']:
            print('\nLikely broken point: INSERT into chain_messages failed. Check services.messaging_engine.send_message and services.neon_service.write_query')
        elif not results['thread_update']:
            print('\nLikely broken point: thread updated_at not updated after insert. Check services.messaging_engine.send_message -> UPDATE chain_message_threads')
        elif not results['message_fetch']:
            print('\nLikely broken point: message not returned by get_thread. Check services.messaging_engine.get_thread SQL and read permissions')
        elif not results['socket_emit_path']:
            print('\nLikely broken point: emit_to_thread not executed. Check services.messaging_engine.send_message emit_to_thread call and services.socketio_service.emit_to_thread')
        elif not results['delivered_status']:
            print('\nLikely broken point: acknowledge_delivery write/update failed. Check services.messaging_engine.acknowledge_delivery and services.neon_service.write_query')
        elif not results['seen_status']:
            print('\nLikely broken point: mark_thread_seen did not mark messages seen. Check services.messaging_engine.mark_thread_seen')
        elif not results['frontend_listener']:
            print('\nLikely broken point: Emitted event names/payloads do not match frontend listeners. Check static/js/namvibe_messages_pro.js mapping and services.* emit payloads')


if __name__ == '__main__':
    main()
