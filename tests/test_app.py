import os
import tempfile
import app


def test_status_and_relevance():
    assert app.status_from_text("cyclist was killed after a driver struck him") == "Killed"
    assert app.status_from_text("cyclist suffered a spinal cord injury and was hospitalized") == "Seriously Injured"
    assert app.is_relevant("Cyclist seriously injured after driver crash", "The bicyclist was hospitalized.")
    assert not app.is_relevant("Cyclist wins race", "No crash or injury.")


def test_miami_regression_fixture():
    c = app.KNOWN_REGRESSION
    assert app.is_relevant(c["title"], c["summary"])
    assert app.status_from_text(c["title"] + " " + c["summary"]) == "Seriously Injured"
    assert app.location_from_text(c["title"] + " " + c["summary"]) == "Florida"


def test_duplicate_reports():
    a = {"title": app.KNOWN_REGRESSION["title"], "summary": app.KNOWN_REGRESSION["summary"], "url": "a", "location": "Florida"}
    b = {"title": "Surgeon critically hurt in bicycle crash on Rickenbacker Causeway in Key Biscayne", "summary": "A South Florida surgeon was hit by a driver while riding a bicycle and rushed to Jackson Memorial Hospital.", "url": "b", "location": "Florida"}
    assert app.same_incident(a, b)
