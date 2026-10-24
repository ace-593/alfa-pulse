import argparse
import asyncio

from app.core.config import Settings
from app.db.session import database
from app.services.policies import normalize_email


async def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["grant-company", "make-admin"])
    parser.add_argument("email")
    parser.add_argument("company_id", nargs="?")
    args = parser.parse_args()
    engine, factory = database(Settings().database_url)
    try:
        async with factory() as uow:
            user = await uow.users.by_email(normalize_email(args.email))
            if not user:
                raise SystemExit("Пользователь не найден")
            if args.command == "grant-company":
                if not args.company_id or not await uow.resources.get("company", args.company_id):
                    raise SystemExit("Компания не найдена")
                await uow.resources.put(
                    "membership", f"{user.id}:{args.company_id}", {"userId": user.id, "companyId": args.company_id}
                )
            else:
                from sqlalchemy import update

                from app.models.users import UserRow

                await uow.session.execute(update(UserRow).where(UserRow.id == user.id).values(admin=True))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
