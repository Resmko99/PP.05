import os
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, constr
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Date, DECIMAL, Text, ForeignKey, func, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "Hotel")
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Position(Base):
    __tablename__ = "Position"
    position_id = Column(Integer, primary_key=True, index=True)
    position_name = Column(String(255), unique=True, nullable=False)

class User(Base):
    __tablename__ = "Users"
    user_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    user_login = Column(String(255), unique=True, nullable=False)
    user_password = Column(String(255), nullable=False)
    position_id = Column(Integer, ForeignKey("Position.position_id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    # Дополнительные для блокировки
    failed_attempts = Column(Integer, default=0)
    block = Column(Integer, default=0)

class Client(Base):
    __tablename__ = "Clients"
    client_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    registered_at = Column(DateTime, default=func.now())

class Category(Base):
    __tablename__ = "Category"
    category_id = Column(Integer, primary_key=True, index=True)
    category_name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)

class Room(Base):
    __tablename__ = "Rooms"
    room_id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(10), unique=True, nullable=False)
    floor = Column(Integer, nullable=False)
    capacity = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey("Category.category_id"), nullable=False)

class Cleaning(Base):
    __tablename__ = "Cleaning"
    cleaning_id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("Rooms.room_id"), nullable=False)
    cleaning_date = Column(DateTime, nullable=False)
    cleaning_status = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("Users.user_id"), nullable=True)

class BookingStatus(Base):
    __tablename__ = "BookingStatus"
    booking_status_id = Column(Integer, primary_key=True, index=True)
    status_name = Column(String(100), unique=True, nullable=False)

class Booking(Base):
    __tablename__ = "Bookings"
    booking_id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("Clients.client_id"), nullable=True)
    user_id = Column(Integer, ForeignKey("Users.user_id"), nullable=True)
    booking_date = Column(DateTime, default=func.now())
    arrival_date = Column(Date, nullable=False)
    departure_date = Column(Date, nullable=False)
    booking_status_id = Column(Integer, ForeignKey("BookingStatus.booking_status_id"), nullable=True)
    total_cost = Column(DECIMAL(10,2), nullable=False)

class BookingRoom(Base):
    __tablename__ = "BookingRooms"
    booking_id = Column(Integer, ForeignKey("Bookings.booking_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)
    room_id = Column(Integer, ForeignKey("Rooms.room_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)

class PaymentMethod(Base):
    __tablename__ = "PaymentMethod"
    payment_method_id = Column(Integer, primary_key=True, index=True)
    method_name = Column(String(100), unique=True, nullable=False)

class Payment(Base):
    __tablename__ = "Payments"
    payment_id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("Bookings.booking_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    payment_date = Column(DateTime, default=func.now())
    amount = Column(DECIMAL(10,2), nullable=False)
    payment_method_id = Column(Integer, ForeignKey("PaymentMethod.payment_method_id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)

class AdditionalService(Base):
    __tablename__ = "AdditionalServices"
    service_id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(255), unique=True, nullable=False)
    price = Column(DECIMAL(10,2), nullable=False)
    description = Column(Text)

class ServiceUsage(Base):
    __tablename__ = "Service_Usage"
    service_usage_id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("Clients.client_id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    service_id = Column(Integer, ForeignKey("AdditionalServices.service_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    booking_id = Column(Integer, ForeignKey("Bookings.booking_id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    usage_date = Column(DateTime, default=func.now())
    quantity = Column(Integer, nullable=False)
    cost = Column(DECIMAL(10,2), nullable=False)
    __table_args__ = (CheckConstraint("quantity > 0", name="check_quantity_positive"),)

class Document(Base):
    __tablename__ = "Documents"
    document_id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("Bookings.booking_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    doc_name = Column(String(255), nullable=False)
    doc_path = Column(Text, nullable=False)
    doc_create_date = Column(DateTime, default=func.now())

class SalesAnalysis(Base):
    __tablename__ = "SalesAnalysis"
    analysis_id = Column(Integer, primary_key=True, index=True)
    analysis_date = Column(Date, nullable=False)
    total_revenue = Column(DECIMAL(10,2), nullable=False)
    rooms_sold = Column(Integer, nullable=False)
    additional_services_revenue = Column(DECIMAL(10,2), nullable=False)
    __table_args__ = (
        CheckConstraint("rooms_sold >= 0", name="check_rooms_sold_nonnegative"),
        CheckConstraint("additional_services_revenue >= 0", name="check_services_revenue_nonnegative"),
    )

Base.metadata.create_all(bind=engine)

LETTER_REGEX = r"^[A-Za-zА-Яа-яЁё]+$"

class LoginData(BaseModel):
    user_login: str
    user_password: str

class UserOut(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    email: EmailStr
    class Config:
        orm_mode = True

class ClientCreate(BaseModel):
    first_name: constr(regex=LETTER_REGEX, strip_whitespace=True)
    last_name: constr(regex=LETTER_REGEX, strip_whitespace=True)
    phone: constr(min_length=2)
    email: EmailStr

class ClientOut(ClientCreate):
    client_id: int
    registered_at: datetime
    class Config:
        orm_mode = True

class PositionCreate(BaseModel):
    position_name: str

class PositionOut(PositionCreate):
    position_id: int
    class Config:
        orm_mode = True

class RoomCreate(BaseModel):
    room_number: str
    floor: int
    capacity: int
    category_id: int

class RoomOut(RoomCreate):
    room_id: int
    class Config:
        orm_mode = True

class CategoryCreate(BaseModel):
    category_name: str
    description: str = ""

class CategoryOut(CategoryCreate):
    category_id: int
    class Config:
        orm_mode = True

class BookingCreate(BaseModel):
    client_id: int
    arrival_date: date
    departure_date: date
    booking_status_id: int
    total_cost: float
    room_id: int

class BookingOut(BookingCreate):
    booking_id: int
    booking_date: datetime
    class Config:
        orm_mode = True

class PaymentCreate(BaseModel):
    booking_id: int
    amount: float
    payment_method_id: int

class PaymentOut(PaymentCreate):
    payment_id: int
    payment_date: datetime
    class Config:
        orm_mode = True

class PaymentMethodCreate(BaseModel):
    method_name: str

class PaymentMethodOut(PaymentMethodCreate):
    payment_method_id: int
    class Config:
        orm_mode = True

class AdditionalServiceCreate(BaseModel):
    service_name: str
    price: float
    description: str = ""

class AdditionalServiceOut(AdditionalServiceCreate):
    service_id: int
    class Config:
        orm_mode = True

class ServiceUsageCreate(BaseModel):
    client_id: int
    service_id: int
    booking_id: int
    quantity: int
    cost: float

class ServiceUsageOut(ServiceUsageCreate):
    service_usage_id: int
    usage_date: datetime
    class Config:
        orm_mode = True

class DocumentCreate(BaseModel):
    booking_id: int
    doc_name: str
    doc_path: str

class DocumentOut(DocumentCreate):
    document_id: int
    doc_create_date: datetime
    class Config:
        orm_mode = True

class SalesAnalysisCreate(BaseModel):
    analysis_date: date
    total_revenue: float
    rooms_sold: int
    additional_services_revenue: float

class SalesAnalysisOut(SalesAnalysisCreate):
    analysis_id: int
    class Config:
        orm_mode = True


app = FastAPI(title="Hotel Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/login", response_model=UserOut)
def login(data: LoginData, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_login == data.user_login).first()
    if not user:
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    if user.block == 1:
        raise HTTPException(status_code=403, detail="Пользователь заблокирован")
    if data.user_password != user.user_password:
        user.failed_attempts += 1
        if user.failed_attempts >= 3:
            user.block = 1
            user.failed_attempts = 0
        db.commit()
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    user.failed_attempts = 0
    db.commit()
    return user

@app.put("/users/{user_id}/change-password", response_model=UserOut)
def change_password(user_id: int, payload: dict, db: Session = Depends(get_db)):
    current = payload.get("current_password")
    new = payload.get("new_password")
    repeat = payload.get("repeat_password")
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if current != user.user_password:
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    if new != repeat:
        raise HTTPException(status_code=400, detail="Новые пароли не совпадают")
    user.user_password = new
    db.commit()
    db.refresh(user)
    return user

@app.post("/users", response_model=UserOut)
def create_user(
    user_data: LoginData,
    first_name: str,
    last_name: str,
    phone: str,
    email: EmailStr,
    position_id: int,
    db: Session = Depends(get_db)
):
    if not (first_name and last_name and phone and email and user_data.user_login):
        raise HTTPException(status_code=400, detail="Все поля обязательны")
    new_user = User(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        user_login=user_data.user_login,
        user_password=user_data.user_password,
        position_id=position_id,
        created_at=datetime.now(),
        block=0,
        failed_attempts=0
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.put("/users/{user_id}/block")
def block_user(user_id: int, block: bool, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.block = 1 if block else 0
    if not block:
        user.failed_attempts = 0
    db.commit()
    return {"detail": "Статус обновлен"}

@app.get("/clients", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).order_by(Client.client_id).all()

@app.post("/clients", response_model=ClientOut)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    exist = db.query(Client).filter(
        (Client.phone == client.phone) | (Client.email == client.email)
    ).first()
    if exist:
        raise HTTPException(status_code=400, detail="Клиент с таким телефоном или email уже существует")
    db_client = Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@app.put("/clients/{client_id}", response_model=ClientOut)
def update_client(client_id: int, client: ClientCreate, db: Session = Depends(get_db)):
    db_client = db.query(Client).filter(Client.client_id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    for key, value in client.dict().items():
        setattr(db_client, key, value)
    db.commit()
    db.refresh(db_client)
    return db_client

@app.delete("/clients/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    db_client = db.query(Client).filter(Client.client_id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    db.delete(db_client)
    db.commit()
    return {"detail": "Клиент удален"}

@app.get("/positions", response_model=list[PositionOut])
def list_positions(db: Session = Depends(get_db)):
    return db.query(Position).order_by(Position.position_id).all()

@app.post("/positions", response_model=PositionOut)
def create_position(position: PositionCreate, db: Session = Depends(get_db)):
    exist = db.query(Position).filter(Position.position_name == position.position_name).first()
    if exist:
        raise HTTPException(status_code=400, detail="Должность с таким названием уже существует")
    db_position = Position(**position.dict())
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position

@app.put("/positions/{position_id}", response_model=PositionOut)
def update_position(position_id: int, position: PositionCreate, db: Session = Depends(get_db)):
    db_position = db.query(Position).filter(Position.position_id == position_id).first()
    if not db_position:
        raise HTTPException(status_code=404, detail="Должность не найдена")
    db_position.position_name = position.position_name
    db.commit()
    db.refresh(db_position)
    return db_position

@app.delete("/positions/{position_id}")
def delete_position(position_id: int, db: Session = Depends(get_db)):
    db_position = db.query(Position).filter(Position.position_id == position_id).first()
    if not db_position:
        raise HTTPException(status_code=404, detail="Должность не найдена")
    db.delete(db_position)
    db.commit()
    return {"detail": "Должность удалена"}

@app.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.category_id).all()

@app.post("/categories", response_model=CategoryOut)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    exist = db.query(Category).filter(Category.category_name == category.category_name).first()
    if exist:
        raise HTTPException(status_code=400, detail="Категория с таким названием уже существует")
    db_category = Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, category: CategoryCreate, db: Session = Depends(get_db)):
    db_category = db.query(Category).filter(Category.category_id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    db_category.category_name = category.category_name
    db_category.description = category.description
    db.commit()
    db.refresh(db_category)
    return db_category

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    db_category = db.query(Category).filter(Category.category_id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    db.delete(db_category)
    db.commit()
    return {"detail": "Категория удалена"}

@app.get("/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(Room).order_by(Room.room_id).all()

@app.post("/rooms", response_model=RoomOut)
def create_room(room: RoomCreate, db: Session = Depends(get_db)):
    exist = db.query(Room).filter(Room.room_number == room.room_number).first()
    if exist:
        raise HTTPException(status_code=400, detail="Номер с таким номером уже существует")
    db_room = Room(**room.dict())
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room

@app.put("/rooms/{room_id}", response_model=RoomOut)
def update_room(room_id: int, room: RoomCreate, db: Session = Depends(get_db)):
    db_room = db.query(Room).filter(Room.room_id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Номер не найден")
    for key, value in room.dict().items():
        setattr(db_room, key, value)
    db.commit()
    db.refresh(db_room)
    return db_room

@app.delete("/rooms/{room_id}")
def delete_room(room_id: int, db: Session = Depends(get_db)):
    db_room = db.query(Room).filter(Room.room_id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Номер не найден")
    db.delete(db_room)
    db.commit()
    return {"detail": "Номер удален"}

@app.get("/cleanings")
def list_cleanings(db: Session = Depends(get_db)):
    return db.query(Cleaning).order_by(Cleaning.cleaning_id).all()

@app.post("/cleanings")
def create_cleaning(cleaning_data: dict, db: Session = Depends(get_db)):
    try:
        cleaning_date = datetime.fromisoformat(cleaning_data["cleaning_date"])
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный формат cleaning_date")
    db_cleaning = Cleaning(
        room_id=cleaning_data["room_id"],
        cleaning_date=cleaning_date,
        cleaning_status=cleaning_data["cleaning_status"],
        user_id=cleaning_data.get("user_id")
    )
    db.add(db_cleaning)
    db.commit()
    db.refresh(db_cleaning)
    return db_cleaning

@app.put("/cleanings/{cleaning_id}")
def update_cleaning(cleaning_id: int, cleaning_data: dict, db: Session = Depends(get_db)):
    db_cleaning = db.query(Cleaning).filter(Cleaning.cleaning_id == cleaning_id).first()
    if not db_cleaning:
        raise HTTPException(status_code=404, detail="Запись очистки не найдена")
    if "room_id" in cleaning_data:
        db_cleaning.room_id = cleaning_data["room_id"]
    if "cleaning_date" in cleaning_data:
        try:
            db_cleaning.cleaning_date = datetime.fromisoformat(cleaning_data["cleaning_date"])
        except Exception:
            raise HTTPException(status_code=400, detail="Неверный формат cleaning_date")
    if "cleaning_status" in cleaning_data:
        db_cleaning.cleaning_status = cleaning_data["cleaning_status"]
    if "user_id" in cleaning_data:
        db_cleaning.user_id = cleaning_data["user_id"]
    db.commit()
    db.refresh(db_cleaning)
    return db_cleaning

@app.delete("/cleanings/{cleaning_id}")
def delete_cleaning(cleaning_id: int, db: Session = Depends(get_db)):
    db_cleaning = db.query(Cleaning).filter(Cleaning.cleaning_id == cleaning_id).first()
    if not db_cleaning:
        raise HTTPException(status_code=404, detail="Запись очистки не найдена")
    db.delete(db_cleaning)
    db.commit()
    return {"detail": "Запись очистки удалена"}

@app.get("/booking-statuses")
def list_booking_statuses(db: Session = Depends(get_db)):
    return db.query(BookingStatus).order_by(BookingStatus.booking_status_id).all()

@app.post("/booking-statuses")
def create_booking_status(status_data: dict, db: Session = Depends(get_db)):
    status = status_data.get("status_name")
    if not status:
        raise HTTPException(status_code=400, detail="status_name обязателен")
    exist = db.query(BookingStatus).filter(BookingStatus.status_name == status).first()
    if exist:
        raise HTTPException(status_code=400, detail="Статус бронирования с таким именем уже существует")
    db_status = BookingStatus(status_name=status)
    db.add(db_status)
    db.commit()
    db.refresh(db_status)
    return db_status

@app.put("/booking-statuses/{status_id}")
def update_booking_status(status_id: int, status_data: dict, db: Session = Depends(get_db)):
    db_status = db.query(BookingStatus).filter(BookingStatus.booking_status_id == status_id).first()
    if not db_status:
        raise HTTPException(status_code=404, detail="Статус бронирования не найден")
    if "status_name" in status_data:
        db_status.status_name = status_data["status_name"]
    db.commit()
    db.refresh(db_status)
    return db_status

@app.delete("/booking-statuses/{status_id}")
def delete_booking_status(status_id: int, db: Session = Depends(get_db)):
    db_status = db.query(BookingStatus).filter(BookingStatus.booking_status_id == status_id).first()
    if not db_status:
        raise HTTPException(status_code=404, detail="Статус бронирования не найден")
    db.delete(db_status)
    db.commit()
    return {"detail": "Статус бронирования удален"}

@app.get("/bookings", response_model=list[BookingOut])
def list_bookings(db: Session = Depends(get_db)):
    return db.query(Booking).order_by(Booking.booking_id).all()

@app.post("/bookings", response_model=BookingOut)
def create_booking(booking: BookingCreate, db: Session = Depends(get_db)):
    if booking.departure_date <= booking.arrival_date:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")
    conflict = db.execute(
        """
        SELECT b.booking_id
        FROM BookingRooms br
        JOIN Bookings b ON br.booking_id = b.booking_id
        WHERE br.room_id = :room_id
          AND NOT (:departure_date <= b.arrival_date OR :arrival_date >= (b.departure_date + INTERVAL '1 day'))
        """,
        {"room_id": booking.room_id, "arrival_date": booking.arrival_date, "departure_date": booking.departure_date}
    ).fetchone()
    if conflict:
        raise HTTPException(status_code=400, detail="Выбранный номер занят на эти даты")
    db_booking = Booking(
        client_id=booking.client_id,
        arrival_date=booking.arrival_date,
        departure_date=booking.departure_date,
        booking_status_id=booking.booking_status_id,
        total_cost=booking.total_cost
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    db.execute(
        "INSERT INTO BookingRooms (booking_id, room_id) VALUES (:booking_id, :room_id)",
        {"booking_id": db_booking.booking_id, "room_id": booking.room_id}
    )
    db.commit()
    return db_booking

@app.put("/bookings/{booking_id}", response_model=BookingOut)
def update_booking(booking_id: int, booking: BookingCreate, db: Session = Depends(get_db)):
    db_booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Бронирование не найдено")
    if booking.departure_date <= booking.arrival_date:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")
    conflict = db.execute(
        """
        SELECT b.booking_id
        FROM BookingRooms br
        JOIN Bookings b ON br.booking_id = b.booking_id
        WHERE br.room_id = :room_id
          AND b.booking_id <> :booking_id
          AND NOT (:departure_date <= b.arrival_date OR :arrival_date >= (b.departure_date + INTERVAL '1 day'))
        """,
        {"room_id": booking.room_id, "booking_id": booking_id,
         "arrival_date": booking.arrival_date, "departure_date": booking.departure_date}
    ).fetchone()
    if conflict:
        raise HTTPException(status_code=400, detail="Выбранный номер занят на эти даты")
    for field, value in booking.dict(exclude={"room_id"}).items():
        setattr(db_booking, field, value)
    db.commit()
    db.refresh(db_booking)
    # Обновляем связь с номером
    db.execute("DELETE FROM BookingRooms WHERE booking_id = :booking_id", {"booking_id": booking_id})
    db.execute("INSERT INTO BookingRooms (booking_id, room_id) VALUES (:booking_id, :room_id)",
               {"booking_id": booking_id, "room_id": booking.room_id})
    db.commit()
    return db_booking

@app.delete("/bookings/{booking_id}")
def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    db_booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Бронирование не найдено")
    db.delete(db_booking)
    db.commit()
    return {"detail": "Бронирование удалено"}

@app.get("/payments", response_model=list[PaymentOut])
def list_payments(db: Session = Depends(get_db)):
    return db.query(Payment).order_by(Payment.payment_id).all()

@app.post("/payments", response_model=PaymentOut)
def create_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    db_payment = Payment(**payment.dict())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

@app.put("/payments/{payment_id}", response_model=PaymentOut)
def update_payment(payment_id: int, payment: PaymentCreate, db: Session = Depends(get_db)):
    db_payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Платеж не найден")
    for key, value in payment.dict().items():
        setattr(db_payment, key, value)
    db.commit()
    db.refresh(db_payment)
    return db_payment

@app.delete("/payments/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    db_payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Платеж не найден")
    db.delete(db_payment)
    db.commit()
    return {"detail": "Платеж удален"}

@app.get("/services", response_model=list[AdditionalServiceOut])
def list_services(db: Session = Depends(get_db)):
    return db.query(AdditionalService).order_by(AdditionalService.service_id).all()

@app.post("/services", response_model=AdditionalServiceOut)
def create_service(service: AdditionalServiceCreate, db: Session = Depends(get_db)):
    exist = db.query(AdditionalService).filter(AdditionalService.service_name == service.service_name).first()
    if exist:
        raise HTTPException(status_code=400, detail="Услуга с таким названием уже существует")
    db_service = AdditionalService(**service.dict())
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    return db_service

@app.put("/services/{service_id}", response_model=AdditionalServiceOut)
def update_service(service_id: int, service: AdditionalServiceCreate, db: Session = Depends(get_db)):
    db_service = db.query(AdditionalService).filter(AdditionalService.service_id == service_id).first()
    if not db_service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    for key, value in service.dict().items():
        setattr(db_service, key, value)
    db.commit()
    db.refresh(db_service)
    return db_service

@app.delete("/services/{service_id}")
def delete_service(service_id: int, db: Session = Depends(get_db)):
    db_service = db.query(AdditionalService).filter(AdditionalService.service_id == service_id).first()
    if not db_service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    db.delete(db_service)
    db.commit()
    return {"detail": "Услуга удалена"}

@app.get("/service-usage", response_model=list[ServiceUsageOut])
def list_service_usage(db: Session = Depends(get_db)):
    return db.query(ServiceUsage).order_by(ServiceUsage.service_usage_id).all()

@app.post("/service-usage", response_model=ServiceUsageOut)
def create_service_usage(usage: ServiceUsageCreate, db: Session = Depends(get_db)):
    db_usage = ServiceUsage(**usage.dict())
    db.add(db_usage)
    db.commit()
    db.refresh(db_usage)
    return db_usage

@app.put("/service-usage/{usage_id}", response_model=ServiceUsageOut)
def update_service_usage(usage_id: int, usage: ServiceUsageCreate, db: Session = Depends(get_db)):
    db_usage = db.query(ServiceUsage).filter(ServiceUsage.service_usage_id == usage_id).first()
    if not db_usage:
        raise HTTPException(status_code=404, detail="Запись использования услуги не найдена")
    for key, value in usage.dict().items():
        setattr(db_usage, key, value)
    db.commit()
    db.refresh(db_usage)
    return db_usage

@app.delete("/service-usage/{usage_id}")
def delete_service_usage(usage_id: int, db: Session = Depends(get_db)):
    db_usage = db.query(ServiceUsage).filter(ServiceUsage.service_usage_id == usage_id).first()
    if not db_usage:
        raise HTTPException(status_code=404, detail="Запись использования услуги не найдена")
    db.delete(db_usage)
    db.commit()
    return {"detail": "Запись использования услуги удалена"}

@app.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.document_id).all()

@app.post("/documents", response_model=DocumentOut)
def create_document(document: DocumentCreate, db: Session = Depends(get_db)):
    db_doc = Document(**document.dict())
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc

@app.put("/documents/{document_id}", response_model=DocumentOut)
def update_document(document_id: int, document: DocumentCreate, db: Session = Depends(get_db)):
    db_doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not db_doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    for key, value in document.dict().items():
        setattr(db_doc, key, value)
    db.commit()
    db.refresh(db_doc)
    return db_doc

@app.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    db_doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not db_doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    db.delete(db_doc)
    db.commit()
    return {"detail": "Документ удален"}

@app.get("/sales-analysis", response_model=list[SalesAnalysisOut])
def list_sales_analysis(db: Session = Depends(get_db)):
    return db.query(SalesAnalysis).order_by(SalesAnalysis.analysis_id).all()

@app.post("/sales-analysis", response_model=SalesAnalysisOut)
def create_sales_analysis(analysis: SalesAnalysisCreate, db: Session = Depends(get_db)):
    db_analysis = SalesAnalysis(**analysis.dict())
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    return db_analysis

@app.put("/sales-analysis/{analysis_id}", response_model=SalesAnalysisOut)
def update_sales_analysis(analysis_id: int, analysis: SalesAnalysisCreate, db: Session = Depends(get_db)):
    db_analysis = db.query(SalesAnalysis).filter(SalesAnalysis.analysis_id == analysis_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="Запись анализа не найдена")
    for key, value in analysis.dict().items():
        setattr(db_analysis, key, value)
    db.commit()
    db.refresh(db_analysis)
    return db_analysis

@app.delete("/sales-analysis/{analysis_id}")
def delete_sales_analysis(analysis_id: int, db: Session = Depends(get_db)):
    db_analysis = db.query(SalesAnalysis).filter(SalesAnalysis.analysis_id == analysis_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="Запись анализа не найдена")
    db.delete(db_analysis)
    db.commit()
    return {"detail": "Запись анализа удалена"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
