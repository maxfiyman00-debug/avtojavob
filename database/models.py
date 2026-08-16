from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
import enum

class Base(DeclarativeBase):
    pass

class MediaType(str, enum.Enum):
    text = "text"
    voice = "voice"
    video_note = "video_note"
    photo = "photo"
    video = "video"
    document = "document"

class User(Base):
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    connection_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)  # 3 kunlik bepul sinovdan foydalanganmi

    # --- Bot ruxsatlari (screenshotdagi funksiyalar) ---
    auto_mark_read: Mapped[bool] = mapped_column(Boolean, default=False)  # xabarlarni avtomatik o'qilgan deb belgilash

    # --- Ish vaqti bo'yicha avtojavob ---
    working_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    work_start_hour: Mapped[int] = mapped_column(default=9)   # 0-23, UTC
    work_end_hour: Mapped[int] = mapped_column(default=18)    # 0-23, UTC
    out_of_hours_text: Mapped[str] = mapped_column(Text, nullable=True)

    # --- Statistika ---
    total_auto_replies: Mapped[int] = mapped_column(default=0)  # jami avtomatik yuborilgan javoblar soni

    # --- Avtojavob rejimi ---
    reply_every_time: Mapped[bool] = mapped_column(Boolean, default=False)  # False = faqat birinchi murojaatga, True = har safar

    auto_replies: Mapped[list["AutoReply"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    social_links: Mapped[list["SocialLink"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    business_chats: Mapped[list["BusinessChat"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    keyword_replies: Mapped[list["KeywordReply"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class AutoReply(Base):
    __tablename__ = "auto_replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.user_id", ondelete="CASCADE"))
    greeting_text: Mapped[str] = mapped_column(Text, nullable=True)
    media_file_id: Mapped[str] = mapped_column(String, nullable=True)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType), default=MediaType.text)

    user: Mapped["User"] = relationship(back_populates="auto_replies")

class SocialLink(Base):
    __tablename__ = "social_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.user_id", ondelete="CASCADE"))
    platform_type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    url_or_number: Mapped[str] = mapped_column(String)

    user: Mapped["User"] = relationship(back_populates="social_links")

class RepliedCustomer(Base):
    """Bitta biznes egasi (owner) uchun qaysi mijozlarga avtojavob
    allaqachon yuborilganini saqlaydi, shu orqali har bir mijozga
    faqat birinchi murojaatida bir marta javob beriladi."""
    __tablename__ = "replied_customers"
    __table_args__ = (UniqueConstraint("owner_id", "customer_id", name="uq_owner_customer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, index=True)
    replied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PremiumTariff(Base):
    """Admin tomonidan qo'shiladigan premium tariflar (masalan: '1 oylik', '3 oylik').
    Narx va muddatni admin o'zi kiritadi."""
    __tablename__ = "premium_tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    days: Mapped[int] = mapped_column()
    price_text: Mapped[str] = mapped_column(String)  # masalan: "50 000 so'm" - admin xohlagancha yozadi
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PremiumRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class PremiumRequest(Base):
    """Foydalanuvchi 'To'ladim' tugmasini bosganda yaratiladigan so'rov.
    Admin tasdiqlagach yoki rad etgach status yangilanadi."""
    __tablename__ = "premium_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("premium_tariffs.id"))
    status: Mapped[PremiumRequestStatus] = mapped_column(Enum(PremiumRequestStatus), default=PremiumRequestStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_by: Mapped[int] = mapped_column(BigInteger, nullable=True)  # qaysi admin ko'rib chiqqani

    tariff: Mapped["PremiumTariff"] = relationship()

class BusinessChat(Base):
    """Har bir biznes egasi (owner) uchun har bir mijoz chatidagi so'nggi
    kirgan/chiqgan xabar ID'larini saqlaydi. Bu 'Oxirgi xabarni o'chirish'
    kabi funksiyalar uchun kerak (Bot API delete_business_messages faqat
    message_id orqali ishlaydi)."""
    __tablename__ = "business_chats"
    __table_args__ = (UniqueConstraint("owner_id", "chat_id", name="uq_owner_chat"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("bot_users.user_id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[str] = mapped_column(String)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    last_incoming_message_id: Mapped[int] = mapped_column(nullable=True)  # mijozdan kelgan oxirgi xabar
    last_outgoing_message_id: Mapped[int] = mapped_column(nullable=True)  # owner/bot yuborgan oxirgi xabar
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="business_chats")


class ScheduledStory(Base):
    """Foydalanuvchi belgilagan vaqtda avtomatik joylanadigan hikoya (story).
    Bot API'da story'ni bevosita 'kelajakda joylash' imkoniyati yo'q, shu
    sabab buni background watcher orqali o'zimiz amalga oshiramiz."""
    __tablename__ = "scheduled_stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("bot_users.user_id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[str] = mapped_column(String)
    media_file_id: Mapped[str] = mapped_column(String)
    media_type: Mapped[str] = mapped_column(String)  # "photo" yoki "video"
    caption: Mapped[str] = mapped_column(Text, nullable=True)
    active_period: Mapped[int] = mapped_column(default=86400)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    is_posted: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_reason: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()


class KeywordReply(Base):
    """Mijoz xabarida ma'lum kalit so'z uchrasa, umumiy avtojavob o'rniga
    shu maxsus javob yuboriladi (masalan 'narx' so'ziga narxlar ro'yxati)."""
    __tablename__ = "keyword_replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("bot_users.user_id", ondelete="CASCADE"), index=True)
    keyword: Mapped[str] = mapped_column(String)  # kichik harflarda saqlanadi, "contains" bo'yicha tekshiriladi
    reply_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="keyword_replies")


class BotSetting(Base):
    """Karta raqami kabi admin o'zgartira oladigan sozlamalarni saqlash uchun
    oddiy kalit-qiymat (key-value) jadval."""
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=True)
