import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.user import User

async def list_users():
    async with async_session() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        for u in users:
            print(f"ID: {u.id} | Email: {u.email} | Username: {u.username}")

if __name__ == "__main__":
    asyncio.run(list_users())
