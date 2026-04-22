from fastapi import UploadFile, HTTPException, status
from supabase import create_client, Client
import uuid

from app.config import settings

if settings.supabase_project_url and settings.supabase_api_key:
    supabase: Client = create_client(
        settings.supabase_project_url,
        settings.supabase_api_key
    )
else:
    supabase = None


async def upload_image_to_supabase(file: UploadFile) -> str:
    if not supabase:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Supabase client is not configured")
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image")
    
    file_bytes = await file.read()
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    try:
        supabase.storage.from_("menu-images").upload(
            path=unique_filename,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )

        public_url = supabase.storage.from_("menu-images").get_public_url(unique_filename)

        return public_url
    
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload images to Supabase with error of {e}")