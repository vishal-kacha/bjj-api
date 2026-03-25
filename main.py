import os
import tempfile
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend import analyze_video_with_gemini
from stats import generate_interval_csv, generate_pdf_report

# ---------------------------------------------------------------------------
# Environment & Config
# ---------------------------------------------------------------------------

if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Hardcoded API token — set this in your .env as API_TOKEN or change the default below
API_TOKEN = os.getenv("API_TOKEN", "bjj-super-secret-token-2025")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Checks that the Bearer token in the Authorization header matches API_TOKEN.
    Usage:  Authorization: Bearer bjj-super-secret-token-2025
    """
    if credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY missing. Set it in your .env file.")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BJJ AI Coach API",
    description=("Advanced BJJ Performance Analysis powered by Gemini AI.\n\n"),
    version="2.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# HEALTH
# ===========================================================================


@app.get("/health", summary="Health check", tags=["General"])
def health():
    """Public endpoint — no auth required."""
    return {"status": "ok", "api_key_set": bool(GOOGLE_API_KEY)}


# ===========================================================================
# ANALYZE
# ===========================================================================


@app.post(
    "/analyze",
    summary="Analyze BJJ sparring footage",
    tags=["Analysis"],
    dependencies=[Depends(verify_token)],
)
async def analyze(
    video: UploadFile = File(
        ..., description="Sparring video file (mp4/mov/avi, max ~1.5 mins)"
    ),
    user_desc: str = Form(
        ...,
        description="Visual description of the user (e.g. 'black jersey, long hair')",
    ),
    opp_desc: str = Form(
        ..., description="Visual description of the opponent (e.g. 'green jersey')"
    ),
    match_context: str = Form(
        "", description="Optional narrative context about the match"
    ),
    activity_type: str = Form("Brazilian Jiu-Jitsu", description="Activity type"),
):
    """
    Upload a sparring video and player descriptions.

    Returns a full JSON analysis including scores, grades, interval breakdown,
    strengths/weaknesses, missed opportunities, key moments, and coach notes.

    **Requires:** `Authorization: Bearer <your_token>` header.
    """
    # Validate file type
    allowed_types = {"video/mp4", "video/quicktime", "video/x-msvideo"}
    if video.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {video.content_type}. Use mp4, mov, or avi.",
        )

    tmp_video_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(await video.read())
            tmp_video_path = tmp_file.name

        result = analyze_video_with_gemini(
            tmp_video_path,
            user_desc,
            opp_desc,
            match_context,
            GOOGLE_API_KEY,
            status_callback=lambda msg: print(f"[STATUS] {msg}"),
        )

        return JSONResponse(content=result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if tmp_video_path and os.path.exists(tmp_video_path):
            try:
                time.sleep(1)
                os.remove(tmp_video_path)
            except Exception as cleanup_err:
                print(f"[CLEANUP WARNING] {cleanup_err}")


# ===========================================================================
# EXPORT — CSV
# ===========================================================================


@app.post(
    "/export/csv",
    summary="Export interval breakdown as CSV",
    tags=["Export"],
    dependencies=[Depends(verify_token)],
)
async def export_csv(interval_breakdown: list):
    """
    Pass the `interval_breakdown` array from the `/analyze` response.
    Returns a downloadable CSV file.

    **Requires:** `Authorization: Bearer <your_token>` header.
    """
    try:
        csv_data = generate_interval_csv(interval_breakdown)
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=bjj_intervals.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# EXPORT — PDF
# ===========================================================================


@app.post(
    "/export/pdf",
    summary="Export full analysis as PDF report",
    tags=["Export"],
    dependencies=[Depends(verify_token)],
)
async def export_pdf(
    result: dict,
    filename: str = "analysis",
):
    """
    Pass the full JSON result from `/analyze` and an optional filename.
    Returns a downloadable PDF report.

    **Requires:** `Authorization: Bearer <your_token>` header.
    """
    try:
        pdf_bytes = generate_pdf_report(result, filename=filename)
        safe_name = filename.split(".")[0]
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=Report_{safe_name}.pdf"
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
