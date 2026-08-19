"""Print 30-day LLM economics grouped by profile."""

from mockarty import MockartyClient

with MockartyClient() as client:
    report = client.economics.get_usage(group_by="profile", days=30)
    print(
        f"calls={report.totals.calls} tokens={report.totals.total_tokens} "
        f"unpriced={report.unpriced_calls}"
    )
    statement = client.economics.download_usage_statement(limit=100)
    print(f"statement_bytes={len(statement)}")
