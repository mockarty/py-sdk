"""Tag management and folder organization examples.

Demonstrates:
  - Creating and listing tags
  - Creating a folder hierarchy for mocks
  - Moving folders between parents
  - Moving mocks into folders
  - Batch-updating tags on mocks
  - Organizing mocks by team, service, or feature
"""

from mockarty import MockBuilder, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


# ---------------------------------------------------------------------------
# Tag Management
# ---------------------------------------------------------------------------

def create_tags(client: MockartyClient) -> None:
    """Create tags for categorizing mocks.

    Tags help organize and filter mocks by:
      - Service name (user-service, order-service)
      - Environment (dev, staging, prod)
      - Feature area (auth, payments, search)
      - Status (stable, experimental, deprecated)
    """
    tag_names = [
        "user-service",
        "order-service",
        "auth",
        "payments",
        "stable",
        "experimental",
        "v2",
    ]
    for name in tag_names:
        tag = client.tags.create(name)
        print(f"Created tag: {tag.name} (id={tag.id})")


def list_tags(client: MockartyClient) -> None:
    """List all tags in the current namespace."""
    tags = client.tags.list()
    print(f"Tags ({len(tags)}):")
    for tag in tags:
        print(f"  - {tag.id}: {tag.name}")


def create_mocks_with_tags(client: MockartyClient) -> list[str]:
    """Create mocks with tags using MockBuilder."""
    mock_ids = []

    # User service mocks
    for endpoint, method in [("/api/users", "GET"), ("/api/users/:id", "GET"),
                              ("/api/users", "POST")]:
        mock_id = f"tagged-{method.lower()}-{endpoint.replace('/', '-').strip('-')}"
        mock = (
            MockBuilder.http(endpoint, method)
            .id(mock_id)
            .tags("user-service", "stable", "v2")
            .respond(200, body={"status": "ok"})
            .build()
        )
        client.mocks.create(mock)
        mock_ids.append(mock_id)
        print(f"Created mock: {mock_id} [user-service, stable, v2]")

    # Order service mocks
    for endpoint, method in [("/api/orders", "GET"), ("/api/orders", "POST")]:
        mock_id = f"tagged-{method.lower()}-{endpoint.replace('/', '-').strip('-')}"
        mock = (
            MockBuilder.http(endpoint, method)
            .id(mock_id)
            .tags("order-service", "experimental")
            .respond(200, body={"status": "ok"})
            .build()
        )
        client.mocks.create(mock)
        mock_ids.append(mock_id)
        print(f"Created mock: {mock_id} [order-service, experimental]")

    return mock_ids


def batch_update_tags(client: MockartyClient, mock_ids: list[str]) -> None:
    """Update tags for multiple mocks at once.

    Useful for:
      - Promoting mocks from experimental to stable
      - Adding a version tag to a batch of endpoints
      - Tagging mocks for a sprint or release
    """
    # Promote order-service mocks to stable
    order_mock_ids = [mid for mid in mock_ids if "orders" in mid]
    if order_mock_ids:
        client.mocks.batch_update_tags(order_mock_ids, ["order-service", "stable", "v2"])
        print(f"Batch updated tags for {len(order_mock_ids)} order mocks -> [stable, v2]")

    # Add release tag to all mocks
    client.mocks.batch_update_tags(mock_ids, ["release-2.1"])
    print(f"Added 'release-2.1' tag to {len(mock_ids)} mocks")


def filter_mocks_by_tag(client: MockartyClient) -> None:
    """Filter mocks using tag-based search."""
    # Find all stable mocks
    stable_page = client.mocks.list(tags=["stable"])
    print(f"Stable mocks: {stable_page.total}")
    for mock in stable_page.items[:5]:
        print(f"  - {mock.id}")

    # Find user-service mocks
    user_page = client.mocks.list(tags=["user-service"])
    print(f"User-service mocks: {user_page.total}")


# ---------------------------------------------------------------------------
# Folder Organization
# ---------------------------------------------------------------------------

def create_folder_hierarchy(client: MockartyClient) -> dict[str, str]:
    """Create a hierarchical folder structure for mock organization.

    Folders provide a tree structure for grouping related mocks:
      Services/
        User Service/
          Authentication/
          Profile/
        Order Service/
          Cart/
          Payments/
      Infrastructure/
        Health Checks/
    """
    folder_ids = {}

    # Top-level folders
    services = client.folders.create({"name": "Services", "description": "API service mocks"})
    infra = client.folders.create({"name": "Infrastructure", "description": "Infrastructure mocks"})
    folder_ids["services"] = services.id
    folder_ids["infra"] = infra.id
    print(f"Created top-level: Services ({services.id}), Infrastructure ({infra.id})")

    # Service sub-folders
    user_svc = client.folders.create({
        "name": "User Service",
        "parentId": services.id,
        "description": "User management API",
    })
    order_svc = client.folders.create({
        "name": "Order Service",
        "parentId": services.id,
        "description": "Order processing API",
    })
    folder_ids["user_svc"] = user_svc.id
    folder_ids["order_svc"] = order_svc.id
    print(f"Created service folders: User Service ({user_svc.id}), Order Service ({order_svc.id})")

    # Feature sub-folders under User Service
    auth_folder = client.folders.create({
        "name": "Authentication",
        "parentId": user_svc.id,
    })
    profile_folder = client.folders.create({
        "name": "Profile",
        "parentId": user_svc.id,
    })
    folder_ids["auth"] = auth_folder.id
    folder_ids["profile"] = profile_folder.id
    print(f"Created feature folders: Authentication ({auth_folder.id}), Profile ({profile_folder.id})")

    # Feature sub-folders under Order Service
    cart_folder = client.folders.create({"name": "Cart", "parentId": order_svc.id})
    payments_folder = client.folders.create({"name": "Payments", "parentId": order_svc.id})
    folder_ids["cart"] = cart_folder.id
    folder_ids["payments"] = payments_folder.id

    # Health checks folder
    health_folder = client.folders.create({"name": "Health Checks", "parentId": infra.id})
    folder_ids["health"] = health_folder.id

    return folder_ids


def list_folders(client: MockartyClient) -> None:
    """List all mock folders."""
    folders = client.folders.list()
    print(f"Mock folders ({len(folders)}):")
    for f in folders:
        parent = f"  (parent={f.parent_id})" if f.parent_id else "  (root)"
        print(f"  - {f.id}: {f.name}{parent}")


def move_mocks_to_folders(
    client: MockartyClient,
    mock_ids: list[str],
    folder_ids: dict[str, str],
) -> None:
    """Move mocks into their appropriate folders."""
    user_mocks = [mid for mid in mock_ids if "users" in mid]
    order_mocks = [mid for mid in mock_ids if "orders" in mid]

    if user_mocks and "user_svc" in folder_ids:
        client.mocks.move_to_folder(user_mocks, folder_ids["user_svc"])
        print(f"Moved {len(user_mocks)} user mocks to User Service folder")

    if order_mocks and "order_svc" in folder_ids:
        client.mocks.move_to_folder(order_mocks, folder_ids["order_svc"])
        print(f"Moved {len(order_mocks)} order mocks to Order Service folder")


def update_folder(client: MockartyClient, folder_ids: dict[str, str]) -> None:
    """Update a folder's name or description."""
    if "auth" in folder_ids:
        updated = client.folders.update(folder_ids["auth"], {
            "name": "Authentication & Authorization",
            "description": "Login, registration, OAuth, token management",
        })
        print(f"Updated folder: {updated.name}")


def move_folder(client: MockartyClient, folder_ids: dict[str, str]) -> None:
    """Move a folder to a new parent in the hierarchy.

    Example: move Payments from Order Service to top-level Services.
    """
    if "payments" in folder_ids and "services" in folder_ids:
        moved = client.folders.move(folder_ids["payments"], folder_ids["services"])
        print(f"Moved folder '{moved.name}' to Services (top-level)")

    # Move it back
    if "payments" in folder_ids and "order_svc" in folder_ids:
        client.folders.move(folder_ids["payments"], folder_ids["order_svc"])
        print("Moved Payments back under Order Service")


def cleanup_folders(client: MockartyClient, folder_ids: dict[str, str]) -> None:
    """Delete folders (leaf folders first, then parents)."""
    # Delete in reverse order (leaves first)
    delete_order = ["health", "auth", "profile", "cart", "payments",
                     "user_svc", "order_svc", "services", "infra"]
    for key in delete_order:
        if key in folder_ids:
            try:
                client.folders.delete(folder_ids[key])
                print(f"Deleted folder: {key} ({folder_ids[key]})")
            except Exception as e:
                print(f"Failed to delete {key}: {e}")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== Tags ===")
        create_tags(client)
        print()
        list_tags(client)
        print()

        print("=== Tagged Mocks ===")
        mock_ids = create_mocks_with_tags(client)
        print()
        batch_update_tags(client, mock_ids)
        print()
        filter_mocks_by_tag(client)
        print()

        print("=== Folders ===")
        folder_ids = create_folder_hierarchy(client)
        print()
        list_folders(client)
        print()

        print("=== Organize Mocks ===")
        move_mocks_to_folders(client, mock_ids, folder_ids)
        print()
        update_folder(client, folder_ids)
        print()
        move_folder(client, folder_ids)
        print()

        print("=== Cleanup ===")
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        cleanup_folders(client, folder_ids)
        print()

        print("Tags and folders example complete.")


if __name__ == "__main__":
    main()
