from services.neon_service import write_query
import uuid

def seed_enterprise_data():
    # 1. Seed Legal Docs
    sql = "INSERT INTO chain_legal_documents (id, doc_type, version, content, is_active) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
    write_query(sql, (str(uuid.uuid4()), 'privacy_policy', '1.0.0', 'Full Privacy Policy content here...', True))
    write_query(sql, (str(uuid.uuid4()), 'terms_of_service', '1.0.0', 'Full TOS content here...', True))

    # 2. Seed API Versions
    sql = "INSERT INTO chain_api_versions (id, platform, current_version, min_required_version, is_active) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
    write_query(sql, (str(uuid.uuid4()), 'android', '1.0.0', '1.0.0', True))
    write_query(sql, (str(uuid.uuid4()), 'ios', '1.0.0', '1.0.0', True))

    print("Enterprise seeding completed.")

if __name__ == "__main__":
    seed_enterprise_data()
