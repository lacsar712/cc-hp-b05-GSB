import json
import os
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from rules import judge

SECRET = os.environ.get("JWT_SECRET", "herb-process-dev-secret")
DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54393/herb")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
USERS = {
    "processor": {"role": "writer", "password_hash": pwd.hash("herb123456")},
    "checker": {"role": "reader", "password_hash": pwd.hash("check123456")},
}


def connect():
    return psycopg.connect(DSN, row_factory=dict_row)


class LoginIn(BaseModel):
    username: str
    password: str


class StepIn(BaseModel):
    name: str
    temp_c: float
    minutes: float


class BatchIn(BaseModel):
    herb: str = Field(min_length=1, max_length=80)
    steps: list[StepIn]
    pressure_id: int


class PressureIn(BaseModel):
    batch_no: str = Field(min_length=1, max_length=80)
    reading: str = Field(min_length=1, max_length=120)
    read_at: datetime


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="无效令牌") from exc
    if payload.get("sub") not in USERS:
        raise HTTPException(status_code=401, detail="无效令牌")
    return {"username": payload["sub"], "role": payload.get("role")}


def require_writer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "writer":
        raise HTTPException(status_code=403, detail="仅炮制员可写入记录")
    return user


app = FastAPI(title="饮片炮制记录台")


@app.on_event("startup")
def startup():
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS batches (
                id serial PRIMARY KEY,
                herb text NOT NULL,
                doc jsonb NOT NULL,
                verdict text NOT NULL,
                reason text NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        count = conn.execute("SELECT COUNT(*) AS n FROM batches").fetchone()["n"]
        if count == 0:
            now = datetime.now(timezone.utc)
            samples = [
                ("甘草", {"steps": [{"name": "清炒", "temp_c": 120, "minutes": 12}]}),
                ("黄芩", {"steps": [{"name": "清炒", "temp_c": 40, "minutes": 12}]}),
            ]
            for herb, doc in samples:
                verdict, reason = judge(doc)
                conn.execute(
                    """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
                       VALUES (%s, %s::jsonb, %s, %s, %s, %s)""",
                    (herb, json.dumps(doc, ensure_ascii=False), verdict, reason, "processor", now),
                )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS steam_pressures (
                id serial PRIMARY KEY,
                batch_no text NOT NULL,
                reading text NOT NULL,
                read_at timestamptz NOT NULL,
                registered_by text NOT NULL,
                created_at timestamptz NOT NULL,
                used_by_batch_id integer REFERENCES batches(id)
            )"""
        )
        conn.commit()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "herb-process-record"}


@app.post("/api/auth/login")
def login(body: LoginIn):
    user = USERS.get(body.username.strip())
    if not user or not pwd.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode({"sub": body.username.strip(), "role": user["role"], "exp": exp}, SECRET, algorithm="HS256")
    return {"access_token": token, "username": body.username.strip(), "role": user["role"]}


@app.get("/api/batches")
def list_batches(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute("SELECT id, herb, doc, verdict, reason, created_by FROM batches ORDER BY id DESC").fetchall()
    return rows


@app.get("/api/pressures")
def list_pressures(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            """SELECT p.id, p.batch_no, p.reading, p.read_at, p.registered_by,
                      p.used_by_batch_id, b.herb AS used_by_herb
               FROM steam_pressures p
               LEFT JOIN batches b ON b.id = p.used_by_batch_id
               ORDER BY p.id DESC"""
        ).fetchall()
    return rows


@app.post("/api/pressures", status_code=201)
def register_pressure(body: PressureIn, user: dict = Depends(require_writer)):
    with connect() as conn:
        row = conn.execute(
            """INSERT INTO steam_pressures (batch_no, reading, read_at, registered_by, created_at)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id, batch_no, reading, read_at, registered_by, used_by_batch_id""",
            (
                body.batch_no.strip(),
                body.reading.strip(),
                body.read_at,
                user["username"],
                datetime.now(timezone.utc),
            ),
        ).fetchone()
        conn.commit()
    return row


@app.post("/api/batches", status_code=201)
def create_batch(body: BatchIn, user: dict = Depends(require_writer)):
    with connect() as conn:
        pressure = conn.execute(
            "SELECT id, batch_no, reading, read_at, used_by_batch_id FROM steam_pressures WHERE id = %s FOR UPDATE",
            (body.pressure_id,),
        ).fetchone()
        if pressure is None:
            raise HTTPException(status_code=400, detail="压力记录不存在")
        if pressure["used_by_batch_id"] is not None:
            raise HTTPException(status_code=400, detail="该压力记录已挂靠，不能重复使用")
        pressure_snapshot = {
            "pressure_id": pressure["id"],
            "batch_no": pressure["batch_no"],
            "reading": pressure["reading"],
            "read_at": pressure["read_at"].isoformat(),
        }
        doc = {"steps": [s.model_dump() for s in body.steps], "pressure": pressure_snapshot}
        verdict, reason = judge(doc)
        row = conn.execute(
            """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s)
               RETURNING id, herb, doc, verdict, reason, created_by""",
            (body.herb.strip(), json.dumps(doc, ensure_ascii=False), verdict, reason, user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.execute(
            "UPDATE steam_pressures SET used_by_batch_id = %s WHERE id = %s",
            (row["id"], body.pressure_id),
        )
        conn.commit()
    return row
