from copy import deepcopy
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src import app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "activities", deepcopy(app_module.activities))
    with TestClient(app_module.app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture
def freeze_today(monkeypatch):
    def freeze(day):
        class FixedDate:
            @classmethod
            def today(cls):
                return day

        monkeypatch.setattr(app_module, "date", FixedDate)

    return freeze


def test_root_redirects_to_activity_page(client):
    # Arrange
    expected_location = "/static/index.html"

    # Act
    response = client.get("/")

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == expected_location


def test_get_activities_includes_signup_deadline_and_participants(client):
    # Arrange
    expected_deadline = app_module.SIGNUP_DEADLINE.isoformat()

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    activities = response.json()
    assert set(activities) == set(app_module.activities)
    assert all(
        activity["signup_deadline"] == expected_deadline
        for activity in activities.values()
    )
    assert activities["Chess Club"]["participants"] == [
        "michael@mergington.edu",
        "daniel@mergington.edu",
    ]


def test_signup_adds_participant(client, freeze_today):
    # Arrange
    freeze_today(date(2027, 7, 31))
    activity = "Soccer Team"
    email = "student@mergington.edu"

    # Act
    response = client.post(
        f"/activities/{activity}/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for {activity}"}
    assert email in client.get("/activities").json()[activity]["participants"]


def test_signup_rejects_unknown_activity(client, freeze_today):
    # Arrange
    freeze_today(date(2027, 7, 31))
    email = "student@mergington.edu"

    # Act
    response = client.post(
        "/activities/Unknown%20Activity/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_signup_rejects_duplicate_participant(client, freeze_today):
    # Arrange
    freeze_today(date(2027, 7, 31))
    email = "michael@mergington.edu"

    # Act
    response = client.post(
        "/activities/Chess%20Club/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "Student already signed up for this activity"


def test_signup_is_allowed_on_deadline(client, freeze_today):
    # Arrange
    freeze_today(app_module.SIGNUP_DEADLINE)
    email = "deadline-day@mergington.edu"

    # Act
    response = client.post(
        "/activities/Soccer%20Team/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert email in client.get("/activities").json()["Soccer Team"]["participants"]


def test_signup_is_rejected_after_deadline(client, freeze_today):
    # Arrange
    freeze_today(date(2027, 8, 2))
    email = "late@mergington.edu"

    # Act
    response = client.post(
        "/activities/Soccer%20Team/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 400
    assert "August 1, 2027" in response.json()["detail"]
    assert email not in client.get("/activities").json()["Soccer Team"]["participants"]


def test_unregister_removes_participant(client):
    # Arrange
    activity = "Chess Club"
    email = "michael@mergington.edu"

    # Act
    response = client.delete(
        f"/activities/{activity}/participants",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from {activity}"}
    assert email not in client.get("/activities").json()[activity]["participants"]


def test_unregister_rejects_unknown_activity(client):
    # Arrange
    email = "student@mergington.edu"

    # Act
    response = client.delete(
        "/activities/Unknown%20Activity/participants",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_unregister_rejects_participant_not_registered(client):
    # Arrange
    activity = "Chess Club"
    email = "not-registered@mergington.edu"

    # Act
    response = client.delete(
        f"/activities/{activity}/participants",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Student is not signed up for this activity"
