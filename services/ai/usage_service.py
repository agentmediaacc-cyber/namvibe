from services.ai.config import get_ai_config
from services.logging_service import log_warning
from services.neon_service import execute, table_exists


def log_provider_usage(profile_id=None, feature_name="", provider_name="disabled", model_name=None, request_id=None, input_units=0, output_units=0, latency_ms=None, status="skipped", error_code=None, estimated_cost=0):
    if not get_ai_config().log_provider_usage:
        return False
    if not table_exists("chain_ai_provider_usage"):
        return False
    try:
        execute(
            """
            INSERT INTO chain_ai_provider_usage
                (profile_id, feature_name, provider_name, model_name, request_id, input_units, output_units, latency_ms, status, error_code, estimated_cost)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                profile_id, feature_name[:80], provider_name[:80], (model_name or "")[:120] or None,
                (request_id or "")[:120] or None, max(0, int(input_units or 0)), max(0, int(output_units or 0)),
                None if latency_ms is None else max(0, int(latency_ms)), status[:40], (error_code or "")[:80] or None,
                max(0.0, float(estimated_cost or 0)),
            ),
            timeout_ms=2000,
        )
        return True
    except Exception as error:
        log_warning("ai_provider_usage_log_failed", error=str(error)[:120])
        return False
