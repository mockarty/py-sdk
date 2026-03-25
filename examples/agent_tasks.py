"""AI Agent Tasks examples.

Demonstrates:
  - Submitting AI-assisted mock generation tasks
  - Tracking task progress and status
  - Viewing task results
  - Re-running completed tasks
  - Exporting task output
  - Cancelling and cleaning up tasks
"""

from mockarty import MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def submit_mock_generation_task(client: MockartyClient) -> str:
    """Submit an AI task to generate mocks from a natural language description.

    The AI agent analyzes the prompt, generates appropriate mock
    definitions, and optionally creates them in the namespace.
    """
    task = client.agent_tasks.submit({
        "prompt": (
            "Create a REST API for a bookstore with the following endpoints: "
            "GET /api/books - list all books with pagination, "
            "GET /api/books/:id - get a book by ID, "
            "POST /api/books - create a new book (title, author, isbn, price), "
            "PUT /api/books/:id - update a book, "
            "DELETE /api/books/:id - delete a book. "
            "Use realistic Faker values for book titles and author names."
        ),
        "autoCreate": True,  # Automatically create the generated mocks
        "tags": ["ai-generated", "bookstore"],
    })
    task_id = task.get("id", "unknown")
    print(f"Submitted AI task: {task_id}")
    print(f"  Status: {task.get('status')}")
    print(f"  Prompt: {task.get('prompt', '')[:80]}...")
    return task_id


def submit_complex_scenario_task(client: MockartyClient) -> str:
    """Submit a task to generate a complex multi-step workflow.

    The AI agent can generate chain mocks with store operations,
    conditions, and realistic response data.
    """
    task = client.agent_tasks.submit({
        "prompt": (
            "Create an e-commerce checkout workflow: "
            "1. POST /api/cart/add - add item to cart (store cart ID in chain store) "
            "2. GET /api/cart/:id - view cart with items and totals "
            "3. POST /api/cart/:id/checkout - start checkout, create order "
            "4. POST /api/orders/:id/pay - process payment "
            "5. GET /api/orders/:id - get order status with tracking. "
            "Use chain stores to maintain state across steps. "
            "Include proper error responses (400, 404, 409)."
        ),
        "autoCreate": False,  # Just generate, don't create
        "chainId": "checkout-workflow",
    })
    task_id = task.get("id", "unknown")
    print(f"Submitted complex scenario task: {task_id}")
    return task_id


def track_task_progress(client: MockartyClient, task_id: str) -> None:
    """Check the status and progress of an agent task.

    Task statuses:
      - pending: queued for processing
      - running: AI is generating mocks
      - completed: mocks generated successfully
      - failed: generation failed (check error)
      - cancelled: task was cancelled
    """
    task = client.agent_tasks.get(task_id)
    print(f"Task {task_id}:")
    print(f"  Status:     {task.get('status')}")
    print(f"  Progress:   {task.get('progress', 0)}%")
    print(f"  Created at: {task.get('createdAt')}")
    if task.get("completedAt"):
        print(f"  Completed:  {task['completedAt']}")
    if task.get("error"):
        print(f"  Error:      {task['error']}")
    if task.get("mocksGenerated"):
        print(f"  Mocks generated: {task['mocksGenerated']}")


def list_all_tasks(client: MockartyClient) -> None:
    """List all agent tasks with their current status."""
    tasks = client.agent_tasks.list()
    print(f"Agent tasks ({len(tasks)}):")
    for t in tasks:
        status = t.get("status", "unknown")
        prompt_preview = t.get("prompt", "")[:60]
        print(f"  - {t.get('id')}: [{status}] {prompt_preview}...")


def rerun_task(client: MockartyClient, task_id: str) -> None:
    """Re-run a completed task to regenerate mocks.

    Useful when you want a different variation of the AI output
    or when the prompt has been refined.
    """
    new_task = client.agent_tasks.rerun(task_id)
    print(f"Re-run started: {new_task.get('id')}")
    print(f"  Based on:  {task_id}")
    print(f"  Status:    {new_task.get('status')}")


def export_task_result(client: MockartyClient, task_id: str) -> None:
    """Export the task result (generated mocks) as raw data.

    The export includes the complete mock definitions that can
    be saved to a file or imported into another Mockarty instance.
    """
    data = client.agent_tasks.export(task_id)
    print(f"Exported task {task_id}: {len(data)} bytes")
    # Save to file:
    # with open(f"agent-task-{task_id}.json", "wb") as f:
    #     f.write(data)


def cancel_running_task(client: MockartyClient, task_id: str) -> None:
    """Cancel a running agent task."""
    client.agent_tasks.cancel(task_id)
    print(f"Cancelled task: {task_id}")


def cleanup_tasks(client: MockartyClient) -> None:
    """Delete individual tasks or clear all tasks."""
    tasks = client.agent_tasks.list()
    if tasks:
        # Delete a specific task
        client.agent_tasks.delete(tasks[0]["id"])
        print(f"Deleted task: {tasks[0]['id']}")

    # Clear all tasks
    client.agent_tasks.clear_all()
    print("Cleared all agent tasks")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== Submit Tasks ===")
        task_id = submit_mock_generation_task(client)
        print()
        complex_task_id = submit_complex_scenario_task(client)
        print()

        print("=== Track Progress ===")
        track_task_progress(client, task_id)
        print()

        print("=== List Tasks ===")
        list_all_tasks(client)
        print()

        print("=== Re-run Task ===")
        rerun_task(client, task_id)
        print()

        print("=== Export Result ===")
        export_task_result(client, task_id)
        print()

        print("=== Cleanup ===")
        cleanup_tasks(client)
        print()

        print("Agent tasks example complete.")


if __name__ == "__main__":
    main()
