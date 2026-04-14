import asyncio
from sqlalchemy import select
from app.core.database import get_db, engine
from app.models.portal import PortalVideo
from sqlalchemy.ext.asyncio import AsyncSession

async def check_video_url():
    async with AsyncSession(engine) as db:
        try:
            result = await db.execute(select(PortalVideo).where(PortalVideo.is_active == True))
            videos = result.scalars().all()
            if not videos:
                print("No active videos found.")
                return
            
            for video in videos:
                print(f"Video ID: {video.id}")
                print(f"Title: {video.title}")
                print(f"URL: {video.video_url}")
                print(f"Is Active: {video.is_active}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_video_url())
