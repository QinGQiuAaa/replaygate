def test_settings_templates(client):
    resp = client.get("/settings")
    resp.raise_for_status()
    original = resp.json()

    templates = original.get("threshold_templates") or []
    new_template = {"name": "pytest-template", "thresholds": templates[0]["thresholds"]}
    updated_templates = templates + [new_template]

    update_resp = client.put(
        "/settings",
        json={
            "default_executor": original.get("default_executor", "local"),
            "threshold_templates": updated_templates,
            "active_template": "pytest-template",
        },
    )
    update_resp.raise_for_status()

    check = client.get("/settings").json()
    assert check["active_template"] == "pytest-template"
    assert any(t["name"] == "pytest-template" for t in check["threshold_templates"])

    client.put(
        "/settings",
        json={
            "default_executor": original.get("default_executor", "local"),
            "threshold_templates": templates,
            "active_template": original.get("active_template", "default"),
        },
    )
