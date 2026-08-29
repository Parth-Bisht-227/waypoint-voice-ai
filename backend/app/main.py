from contextlib import asynccontextmanager
import aiosqlite
from fastapi import FastAPI, HTTPException
from uuid import uuid4

from .database import DB_PATH, init_db
from .schemas import (
    ApplicationResponse, 
    MissingDocumentsResponse,
    TravelDateUpdateRequest,
    TravelDateUpdateResponse,
    HandoffRequest,
    HandoffResponse,
)
from .voice_tokens import router as voice_router
import json
from datetime import date, datetime, timezone

# the "." is called relative import... means form the same package (app.py)
# it means to search for database and schemas in "app.py"

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db() # startup
    yield # app runs here 

app = FastAPI(
    title = "Waypoint Voice Lab API",
    lifespan=lifespan
    )

app.include_router(voice_router)


#  this means that when FastAPI starts -> run init_db() -> make sure tables + seed data exists
#  then server starts accepting requests
'''
yield roughly separates:
    startup work
    ↓
    yield
    ↓
    application runs
    ↓
    shutdown work could go here later
So we no longer need to manually run an init_db.py.
'''

# first real endpoint

@app.get(
    "/applications/{application_id}",
    response_model=ApplicationResponse
)
async def get_application(application_id: str):
    async with aiosqlite.connect(DB_PATH) as db:

        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT 
                application_id,
                destination,
                status,
                travel_date
            FROM applications
            WHERE application_id = ?
            """,
            (application_id,)
        )

        application = await cursor.fetchone()

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    return dict(application)


@app.get(
    "/applications/{application_id}/missing-documents",
    response_model=MissingDocumentsResponse
)
async def get_missing_documents(application_id: str):

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        #first check whether the application itself exists
        cursor = await db.execute(
            """
            SELECT application_id
            FROM applications
            WHERE application_id  = ?
            """,
            (application_id,)
        )

        application = await cursor.fetchone()

        if application is None:
            raise HTTPException(
                status_code=404,
                detail= "Application not found"
            )

        # Now retrieve all missing documents...
        cursor = await db.execute(
            """
                SELECT document_code
                FROM missing_documents
                WHERE application_id = ?
                ORDER BY document_code
            """,
            (application_id,)
        )

        rows = await cursor.fetchall()

    documents = [
        row["document_code"]
        for row in rows
    ]

    return {
        "application_id": application_id,
        "missing_documents": documents
    }

# 2 queries because 2 diff conditions
# Application id exits, but missing documents =[] -> 200 success
# Application does not exist --> 404

# If we only searched missing_documents,
# both would produce zero rows and we couldn't tell the difference
'''
To implement idempotency and maintain reliability...
this is our approach and idea:

        PATCH arrives
            ↓
        validate request
            ↓
        start DB transaction
            ↓
        does idempotency key already exist?
            |
            ├── YES
            │    ↓
            │ same operation/date?
            │    ├── yes → return stored result
            │    └── no  → 409 conflict
            │
            └── NO
                ↓
            validate application
                ↓
            update travel date
                ↓
            save idempotency record
                ↓
            COMMIT BOTH together
'''
# PATCH endpoint
@app.patch(
    "/applications/{application_id}/travel-date",
    response_model=TravelDateUpdateResponse
)
async def update_travel_date(
    application_id:str,
    request: TravelDateUpdateRequest
):
    # Business validation before touching the data
    if request.new_date <= date.today():
        raise HTTPException(
            status_code=400,
            detail = "Travel date must be in the future!"
        )

    new_date = request.new_date.isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        try:
            # Start one transaction.
            await db.execute("BEGIN")


            # 1. has this request alr happened?
            # ------ | -------

            cursor = await db.execute(
                """
                SELECT 
                    operation,
                    application_id,
                    requested_value,
                    response_json
                FROM idempotency_records
                WHERE idempotency_key = ?
                """,
                (request.idempotency_key,)
            ) 

            existing_record = await cursor.fetchone()

            if existing_record is not None:

                same_request = (
                    existing_record["operation"] == "update_travel_date"
                    and existing_record["application_id"] == application_id 
                    and existing_record["requested_value"] == new_date
                ) 

                if not same_request:
                    raise HTTPException(
                        status_code=409,
                        detail = "Idempotency key already used for a different request"
                    )
                
                # Same logical request -> return original result.
                await db.rollback()

                return json.loads(
                    existing_record["response_json"]
                ) 

            # 2. Check the application exists...
            # ----------  | ----------------

            cursor = await db.execute(
                """
                SELECT travel_date
                FROM applications
                WHERE application_id = ?
                """,
                (application_id,)
            )

            application = await cursor.fetchone()

            if application is None:
                raise HTTPException(
                    status_code=404,
                    detail = "Application not found"
                )

            old_date = application["travel_date"]

            # 3. Building the result...
            changed = old_date != new_date

            result = {
                "application_id": application_id,
                "old_date": old_date,
                "new_date": new_date,
                "changed": changed
            }

            # 4. change business state if needed... 
            if changed:
                await db.execute(
                    """
                    UPDATE applications 
                    SET travel_date = ?
                    WHERE application_id = ?
                    """,
                    (new_date, application_id)
                )

            # 5. Record the logical request
            await db.execute(
                """
                INSERT INTO idempotency_records (
                    idempotency_key,
                    operation,
                    application_id,
                    requested_value,
                    response_json,
                    created_at
                    )
                VALUES (?,?,?,?,?,?)
                """,
                (
                    request.idempotency_key,
                    "update_travel_date",
                    application_id,
                    new_date,
                    json.dumps(result),
                    datetime.now(timezone.utc).isoformat()
                )
            )

            # Both changes become durable together.
            await db.commit()

            return result

        except HTTPException:
            await db.rollback()
            raise

        except Exception:
            await db.rollback()
            raise

'''
raise here means to re-raise the exception we just caught, because we want to 
catch the error -> perform the cleanup/rollback -> then let the error continue upward
if we didn't re-raise it, python would consider the exception handled,
and fastapi might never know that it should send the intended 404 or 409... 

So:
    raise HTTPException(...) --> means create/throw a new exception.

While:
    raise   inside an except means throw the current caught exception again.

----------------------------------

also BEGIN's job is to start an explicit db transaction... and to define the boundary
it tells SQLite: 
to Treat the following operations as one transaction until I either COMMIT or ROLLBACK.


'''


# New end point for handling and adding handoff details

'''
POST used instead of patch, since we're creating *new* handoff resource , that's also why we're returning 201 created rather than 200
uuid4-> creates random unique identifier, since we do not want the LLM to invent canonical handoff ids...
backend code will create them.
'''

@app.post(
    "/applications/{application_id}/handoffs",
    response_model = HandoffResponse,
    status_code=201
)
async def create_handoff(
    application_id:str,
    request: HandoffRequest
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT application_id
            FROM applications
            WHERE application_id = ?
            """,
            (application_id,)
        )

        application = await cursor.fetchone() 

        if application is None:
            raise HTTPException(
                status_code=404,
                detail = "Application not found."
            )

        handoff_id = f"HOF-{uuid4().hex[:10]}"

        await db.execute(
            """
            INSERT INTO handoff_requests (
                handoff_id,
                application_id,
                reason_code,
                status,
                created_at
            )
            VALUES(?, ?, ? ,? ,?)
            """,
            (
                handoff_id,
                application_id,
                request.reason_code.value,
                "requested",
                datetime.now(timezone.utc).isoformat()
            )
        )

        await db.commit()

    return {
        "handoff_id": handoff_id,
        "application_id": application_id,
        "reason_code": request.reason_code,
        "status": "requested"
    }



