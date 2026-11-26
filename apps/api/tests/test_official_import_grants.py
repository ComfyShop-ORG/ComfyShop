from fastapi.testclient import TestClient
from official_test_support import (
    OWNER,
    complete_official_artifact,
    image_bytes,
    register,
    submit,
    workflow_body,
)


def test_grants_are_account_bound_and_keep_each_authors_workflows_private(official):
    manager = official
    grants = "/api/v1/auth/official-import-grants"
    workspace = "/api/v1/workspace"
    create = "/api/v1/workflows"
    assert manager.get(workspace).json()["canManageOfficialImportGrants"]
    assert manager.get(workspace).json()["canImportOfficialWorkflows"]
    assert manager.put(f"{grants}/{OWNER}", json={"granted": False}).status_code == 409
    assert manager.put(f"{grants}/missing", json={"granted": True}).status_code == 404

    author = TestClient(manager.app, headers={"Origin": "http://testserver"})
    credentials = register(author, "GuestAuthor")
    target = f"{grants}/guestauthor"
    body = workflow_body(
        "authored-model", [{"name": "prompt", "kind": "string", "default": ""}], operation="image"
    )
    assert not author.get(workspace).json()["canImportOfficialWorkflows"]
    assert author.get(grants).status_code == 403
    assert author.put(target, json={"granted": True}).status_code == 403
    assert author.post(create, json=body).status_code == 403
    assert TestClient(manager.app).get(grants).status_code == 401
    no_csrf = TestClient(
        manager.app, cookies=manager.cookies, headers={"Origin": "http://testserver"}
    )
    assert no_csrf.put(target, json={"granted": True}).status_code == 403
    for _ in range(2):
        assert manager.put(target, json={"granted": True}).status_code == 204
    assert manager.get(grants).json() == {"items": ["GuestAuthor"], "nextCursor": None}
    access = author.get(workspace).json()
    assert access["canImportOfficialWorkflows"] and not access["canManageOfficialImportGrants"]
    assert author.put(target, json={"granted": False}).status_code == 403
    assert author.post(create + "?initialize=true", json=body).status_code == 403
    draft = author.post(create, json=body).raise_for_status().json()
    assert draft["author"] == "GuestAuthor" and not draft["published"]
    item = f"/api/v1/workflows/{draft['id']}"
    assert author.get("/api/v1/workflows?scope=mine").json()["items"][0]["id"] == draft["id"]
    assert manager.get(item).status_code == 404
    assert manager.patch(item, json={"graph": body["graph"]}).status_code == 404
    assert manager.post(create, json=body).status_code == 409
    assert author.post(create, json=body).json()["id"] == draft["id"]
    assert author.patch(item, json={"graph": body["graph"]}).status_code == 200
    assert manager.post(create, json=body, headers={"Accept-Language": "en"}).status_code == 409

    assert manager.put(target, json={"granted": False}).status_code == 204
    assert not author.get(workspace).json()["canImportOfficialWorkflows"]
    assert manager.get(grants).json()["items"] == []
    assert author.post(create, json=body).status_code == 403
    assert author.patch(item, json={"graph": body["graph"]}).status_code == 403
    assert author.patch(item, json={"name": "My model"}).status_code == 200
    assert author.post(item + "/publish").status_code == 409
    task = submit(author, draft, {"prompt": "A flower"})
    complete_official_artifact(author, task, "result.png", image_bytes("red"))
    assert author.post(item + "/publish").raise_for_status().json()["published"]
    assert manager.patch(item, json={"name": "Other author"}).status_code == 404

    manager.put(target, json={"granted": True}).raise_for_status()
    author.post(
        "/api/v1/auth/account/delete", json={"password": credentials["password"]}
    ).raise_for_status()
    assert manager.get(grants).json()["items"] == []
    register(author, credentials["username"])
    assert not author.get(workspace).json()["canImportOfficialWorkflows"]
