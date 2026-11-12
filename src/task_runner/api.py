from pathlib import Path
from typing import Annotated

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from task_runner.database import DB_PATH,initialize_database
from task_runner.jobs import submit_job,get_job
from task_runner.handler import REGISTRY

app = FastAPI(title="Task Runner")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_database(DB_PATH)
    yield


def get_db_path()->Path:
    return DB_PATH

class JobRequest(BaseModel):
    type: str
    payload: dict
    idempotency_key: str | None = None
    

@app.post("/jobs",status_code=201)
def create_job(request: JobRequest,db_path: Annotated[Path,Depends(get_db_path)])->dict:
    if request.type not in REGISTRY:
        raise HTTPException(status_code=422,detail="unknown job type") 
    try:
        job_id = submit_job(request.type,request.payload,db_path=db_path,idempotency_key=request.idempotency_key)
    except ValueError as exc:
        raise  HTTPException(status_code=409,detail="a job with similar key already exists") from exc
    
    return {"id":job_id}

@app.get("/jobs/{job_id}",status_code=200)
def retrieve_job(job_id: int , db_path: Annotated[Path,Depends(get_db_path)])->dict:
    job = get_job(job_id,db_path)
    
    if job is None:
        raise HTTPException(status_code=404,detail="no job with matching id")
    
    return job