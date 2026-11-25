from app.database import SessionLocal, Base, engine
from app.models.entities import AdminUser
from app.core.security import hash_password

Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter(AdminUser.account == "admin").first()
        if existing:
            print("이미 'admin' 계정이 존재합니다.")
            return

        admin = AdminUser(
            account="admin",
            password_hash=hash_password("admin1234!")
        )
        db.add(admin)
        db.commit()
        print("초기 관리자 계정 생성 완료 (ID: admin / PW: admin1234!)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()