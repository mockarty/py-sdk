"""Selected job reporting, with no private capability in logs/properties."""
import os
from mockarty import MockartyClient
from mockarty.ci_job_context import CI_CONTEXT_ENVIRONMENT, load_ci_job_context

def main():
    job = load_ci_job_context(os.environ[CI_CONTEXT_ENVIRONMENT])
    with MockartyClient(base_url=os.environ["MOCKARTY_BASE_URL"], api_key=os.environ["MOCKARTY_API_TOKEN"], namespace=job.namespace) as client:
        status = "passed"
        try:
            client.external_runs.report(status=status, case_name="selected test", external_id=os.environ["TEST_EXTERNAL_ID"], full_name=os.environ["TEST_FULL_NAME"])
        except Exception:
            status = "failed"
        client.external_runs.complete_group(job.callback, status)
        if status != "passed":
            raise SystemExit(1)
if __name__ == "__main__":
    main()
