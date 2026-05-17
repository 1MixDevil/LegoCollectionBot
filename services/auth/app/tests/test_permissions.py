def test_create_permission(client):
    response = client.post("/permissions/createPermissionRule/", json={"name": "view_reports"})
    assert response.status_code == 201
    assert response.json()["name"] == "view_reports"


def test_list_permissions(client):
    client.post("/permissions/createPermissionRule/", json={"name": "edit_reports"})
    response = client.get("/permissions/rules/")
    assert response.status_code == 200
    assert any(perm["name"] == "edit_reports" for perm in response.json())


def test_create_group(client):
    response = client.post("/permissions/groups/", json={"name": "AdminGroup"})
    assert response.status_code == 201
    assert response.json()["name"] == "AdminGroup"


def test_add_permission_to_group(client):
    # Создаём право
    perm_resp = client.post("/permissions/createPermissionRule/", json={"name": "delete_users"})
    perm_id = perm_resp.json()["id"]

    # Создаём группу
    group_resp = client.post("/permissions/groups/", json={"name": "ModeratorGroup"})
    group_id = group_resp.json()["id"]

    # Добавляем право в группу
    resp = client.post(f"/permissions/groups/{group_id}/rules/{perm_id}")
    assert resp.status_code == 200
    assert any(p["name"] == "delete_users" for p in resp.json()["permissions"])


def test_remove_permission_from_group(client):
    # Создаём право и группу
    perm_resp = client.post("/permissions/createPermissionRule/", json={"name": "ban_users"})
    perm_id = perm_resp.json()["id"]

    group_resp = client.post("/permissions/groups/", json={"name": "SecurityGroup"})
    group_id = group_resp.json()["id"]

    # Добавляем и удаляем
    client.post(f"/permissions/groups/{group_id}/rules/{perm_id}")
    resp = client.delete(f"/permissions/groups/{group_id}/rules/{perm_id}")
    assert resp.status_code == 200
    assert not any(p["name"] == "ban_users" for p in resp.json()["permissions"])
