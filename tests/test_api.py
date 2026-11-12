import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from task_runner.api import app, get_db_path
from task_runner.database import initialize_database,get_connection
from task_runner.jobs import get_job

@pytest.fixture
def db_path(tmp_path:Path)->Path:
    path = tmp_path / "test.db"
    initialize_database(path)
    return path

@pytest.fixture
def client(db_path:Path):
    app.dependency_overrides[get_db_path] = lambda:db_path
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_create_job(client,db_path):
    response = client.post("/jobs",json={"type":"sleep","payload":{"seconds":5},"idempotency_key":"k1"})
    
    assert response.status_code == 201
    
    job_id = response.json()["id"]
    job = get_job(job_id,db_path)
    
    assert job is not None
    assert job["type"] == "sleep"
    assert job["status"] == "pending"
    
    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert count == 1
    
def test_unknown_job_types(client,db_path):
    response = client.post("/jobs",json={"type":"ablablablabla","payload":{"seconds":5},"idempotency_key":"k28"})
    
    assert response.status_code == 422
    assert response.json() == {"detail":"unknown job type"}
    
    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert count == 0
     
def test_retrieve_jobs(client,db_path):
   response = client.post("/jobs",json={"type":"sleep","payload":{"seconds":5},"idempotency_key":"k1"})
   
   assert response.status_code == 201
   
   job_id = response.json()["id"]
   
   job = get_job(job_id,db_path)
   
   res = client.get(f"/jobs/{job_id}")
   
   assert res.status_code == 200
   assert res.json() == job
   
def test_wrong_job_id_raises_error(client):
    response = client.post("/jobs",json={"type":"sleep","payload":{"seconds":5},"idempotency_key":"k1"})

    assert response.status_code == 201
    
    job_id = response.json()["id"] + 1
    
    res = client.get(f"/jobs/{job_id}")
    
    assert res.status_code == 404
    assert res.json() == {"detail":"no job with matching id"}

def test_same_key_and_same_type_payload_returns_same_id(client):
    res1 = client.post("/jobs",json={"type":"sleep","payload":{"seconds":5},"idempotency_key":"k1"})
    
    assert res1.status_code == 201
    
    job_id1 = res1.json()["id"]
    
    res2 = client.post("/jobs",json={"type":"sleep","payload":{"seconds":5},"idempotency_key":"k1"})
    
    assert res2.status_code == 201
    
    job_id2 = res2.json()["id"]
    assert job_id1 == job_id2
    
def test_same_key_different_type_or_payload_raises_error(client):
    res1 = client.post("/jobs",json={"type":"sleep","payload":{"seconds":5},"idempotency_key":"k1"})
        
    assert res1.status_code == 201
        
        
    res2 = client.post("/jobs",json={"type":"sleep","payload":{"seconds":9},"idempotency_key":"k1"})
        
    assert res2.status_code == 409
    
    assert res2.json() == {"detail":"a job with similar key already exists"}