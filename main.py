import os
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from bson import ObjectId

from database import db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Demo auth helpers (placeholder)
# ------------------------------

def ensure_demo_user():
    """Ensure a demo user exists for this environment and return it."""
    if db is None:
        return None
    user = db["user"].find_one({"email": "demo@flamesblue.com"})
    if not user:
        user_id = db["user"].insert_one({
            "name": "Flames Blue",
            "email": "demo@flamesblue.com",
            "password_hash": "demo",
            "is_admin": True,
            "profile_slug": "flames-blue",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }).inserted_id
        db["profile"].insert_one({
            "user_id": str(user_id),
            "job_title": "Vibe Coding Agent",
            "company": "FlamesBlue",
            "phone_number": "+1 555 123 4567",
            "bio": "We build beautiful digital identity experiences.",
            "profile_image_path": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        db["sociallink"].insert_many([
            {"user_id": str(user_id), "platform": "website", "url": "https://flamesblue.com", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)},
            {"user_id": str(user_id), "platform": "linkedin", "url": "https://linkedin.com/company/flamesblue", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)},
            {"user_id": str(user_id), "platform": "github", "url": "https://github.com/", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)},
        ])
        user = db["user"].find_one({"_id": ObjectId(user_id)})
    return user


def get_current_user():
    user = ensure_demo_user()
    if not user:
        raise HTTPException(status_code=500, detail="Database not configured")
    return user

# ------------------------------
# Models for requests
# ------------------------------

class ProfileUpdate(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None

class SocialLinkCreate(BaseModel):
    platform: str
    url: str

class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    is_admin: Optional[bool] = None
    profile_slug: Optional[str] = None

# ------------------------------
# Utility
# ------------------------------

def serialize_user(user_doc):
    return {
        "id": str(user_doc.get("_id")),
        "name": user_doc.get("name"),
        "email": user_doc.get("email"),
        "is_admin": bool(user_doc.get("is_admin", False)),
        "profile_slug": user_doc.get("profile_slug"),
    }


def fetch_profile_bundle_by_slug(slug: str):
    user = db["user"].find_one({"profile_slug": slug})
    if not user:
        return None
    uid = str(user["_id"]) if isinstance(user.get("_id"), ObjectId) else user.get("_id")
    profile = db["profile"].find_one({"user_id": uid})
    links = list(db["sociallink"].find({"user_id": uid}))
    return {
        "user": serialize_user(user),
        "profile": {
            "job_title": profile.get("job_title") if profile else None,
            "company": profile.get("company") if profile else None,
            "phone_number": profile.get("phone_number") if profile else None,
            "bio": profile.get("bio") if profile else None,
            "profile_image_path": profile.get("profile_image_path") if profile else None,
        },
        "social_links": [{"id": str(l.get("_id")), "platform": l.get("platform"), "url": l.get("url")} for l in links],
    }

# ------------------------------
# Public routes
# ------------------------------

@app.get("/")
def root():
    return {"message": "Digital Business Card API (demo)"}

@app.get("/api/p/{slug}")
def get_public_profile(slug: str):
    bundle = fetch_profile_bundle_by_slug(slug)
    if not bundle:
        raise HTTPException(status_code=404, detail="Profile not found")
    return bundle

@app.get("/api/p/{slug}/vcf")
def get_vcard(slug: str):
    bundle = fetch_profile_bundle_by_slug(slug)
    if not bundle:
        raise HTTPException(status_code=404, detail="Profile not found")
    user = bundle["user"]
    profile = bundle.get("profile") or {}
    # Build simple vCard 3.0
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{user.get('name','')};",
        f"FN:{user.get('name','')}",
        f"ORG:{profile.get('company','') or ''}",
        f"TITLE:{profile.get('job_title','') or ''}",
    ]
    if profile.get("phone_number"):
        lines.append(f"TEL;TYPE=CELL:{profile['phone_number']}")
    if user.get("email"):
        lines.append(f"EMAIL;TYPE=INTERNET:{user['email']}")
    # Include first website link if available
    first_website = next((l for l in bundle["social_links"] if l.get("platform") in ("website", "link", "url")), None)
    if first_website:
        lines.append(f"URL:{first_website['url']}")
    lines.append("END:VCARD")
    vcard_str = "\r\n".join(lines)
    filename = f"{bundle['user'].get('name','contact').replace(' ', '_')}.vcf"
    return StreamingResponse(iter([vcard_str]), media_type="text/vcard", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })

# ------------------------------
# Protected user routes (demo auth)
# ------------------------------

@app.get("/api/user")
def get_me(user=Depends(get_current_user)):
    uid = str(user["_id"]) if isinstance(user.get("_id"), ObjectId) else user.get("_id")
    profile = db["profile"].find_one({"user_id": uid})
    links = list(db["sociallink"].find({"user_id": uid}))
    return {
        "user": serialize_user(user),
        "profile": {
            "job_title": profile.get("job_title") if profile else None,
            "company": profile.get("company") if profile else None,
            "phone_number": profile.get("phone_number") if profile else None,
            "bio": profile.get("bio") if profile else None,
            "profile_image_path": profile.get("profile_image_path") if profile else None,
        },
        "social_links": [{"id": str(l.get("_id")), "platform": l.get("platform"), "url": l.get("url")} for l in links],
    }

@app.put("/api/profile")
def update_profile(payload: ProfileUpdate, user=Depends(get_current_user)):
    uid = str(user["_id"]) if isinstance(user.get("_id"), ObjectId) else user.get("_id")
    now = datetime.now(timezone.utc)
    existing = db["profile"].find_one({"user_id": uid})
    update_doc = {k: v for k, v in payload.model_dump().items() if v is not None}
    update_doc["updated_at"] = now
    if existing:
        db["profile"].update_one({"_id": existing["_id"]}, {"$set": update_doc})
    else:
        update_doc.update({"user_id": uid, "created_at": now})
        db["profile"].insert_one(update_doc)
    return {"status": "ok"}

@app.post("/api/social-links")
def create_social_link(payload: SocialLinkCreate, user=Depends(get_current_user)):
    uid = str(user["_id"]) if isinstance(user.get("_id"), ObjectId) else user.get("_id")
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": uid,
        "platform": payload.platform,
        "url": payload.url,
        "created_at": now,
        "updated_at": now,
    }
    ins = db["sociallink"].insert_one(doc)
    return {"id": str(ins.inserted_id)}

@app.delete("/api/social-links/{sid}")
def delete_social_link(sid: str, user=Depends(get_current_user)):
    uid = str(user["_id"]) if isinstance(user.get("_id"), ObjectId) else user.get("_id")
    doc = db["sociallink"].find_one({"_id": ObjectId(sid)})
    if not doc or doc.get("user_id") != uid:
        raise HTTPException(status_code=404, detail="Not found")
    db["sociallink"].delete_one({"_id": ObjectId(sid)})
    return {"status": "deleted"}

# ------------------------------
# Admin routes (demo auth + is_admin flag)
# ------------------------------

def require_admin(user=Depends(get_current_user)):
    if not bool(user.get("is_admin", False)):
        raise HTTPException(status_code=403, detail="Admin only")
    return user

@app.get("/api/admin/users")
def admin_list_users(admin=Depends(require_admin)):
    users = list(db["user"].find())
    return [serialize_user(u) for u in users]

@app.get("/api/admin/users/{uid}")
def admin_get_user(uid: str, admin=Depends(require_admin)):
    try:
        doc = db["user"].find_one({"_id": ObjectId(uid)})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(doc)

@app.put("/api/admin/users/{uid}")
def admin_update_user(uid: str, payload: AdminUserUpdate, admin=Depends(require_admin)):
    update_doc = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_doc:
        return {"status": "no_changes"}
    update_doc["updated_at"] = datetime.now(timezone.utc)
    try:
        res = db["user"].update_one({"_id": ObjectId(uid)}, {"$set": update_doc})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    doc = db["user"].find_one({"_id": ObjectId(uid)})
    return serialize_user(doc)

@app.delete("/api/admin/users/{uid}")
def admin_delete_user(uid: str, admin=Depends(require_admin)):
    try:
        res = db["user"].delete_one({"_id": ObjectId(uid)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    # Cleanup related
    db["profile"].delete_many({"user_id": uid})
    db["sociallink"].delete_many({"user_id": uid})
    return {"status": "deleted"}

# Health and DB test
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                ensure_demo_user()
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
