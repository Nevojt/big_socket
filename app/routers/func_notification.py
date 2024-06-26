
from datetime import datetime
from http.client import HTTPException
from typing import Optional
import logging

import pytz
from app import models
from app.config import settings
from sqlalchemy.future import select
from sqlalchemy import Interval, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func

from app.schemas import InvitationSchema
import base64
from cryptography.fernet import Fernet, InvalidToken

# Configure logging
logging.basicConfig(filename='_log/func_notification.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



# Ініціалізація шифрувальника
key = settings.key_crypto
cipher = Fernet(key)

def is_base64(s):
    try:
        return base64.b64encode(base64.b64decode(s)).decode('utf-8') == s
    except Exception:
        return False

async def async_encrypt(data: Optional[str]):
    if data is None:
        return None
    
    encrypted = cipher.encrypt(data.encode())
    encoded_string = base64.b64encode(encrypted).decode('utf-8')
    return encoded_string

async def async_decrypt(encoded_data: Optional[str]):
    if encoded_data is None:
        return None
    
    if not is_base64(encoded_data):
        return encoded_data

    try:
        encrypted = base64.b64decode(encoded_data.encode('utf-8'))
        decrypted = cipher.decrypt(encrypted).decode('utf-8')
        return decrypted
    except InvalidToken:
        return None  

async def check_new_messages(session: AsyncSession, user_id: int):
    """
    Retrieve a list of all the unread private messages sent to the specified user.

    Args:
        session (AsyncSession): The database session.
        user_id (int): The ID of the user.

    Returns:
        List[Dict[str, int]]: Information about unread messages.
    """
    try:
        # Fetch unread private messages and corresponding sender information
        new_messages = await session.execute(
            select(models.PrivateMessage.id, models.PrivateMessage.message, models.PrivateMessage.fileUrl, models.User.id.label('sender_id'), models.User.user_name)
            .join(models.User, models.PrivateMessage.sender_id == models.User.id)
            .filter(models.PrivateMessage.receiver_id == user_id, models.PrivateMessage.is_read == True)
        )
        messages = new_messages.all()

        # Extract relevant data for each message
        message_data = [
                        {
                            "sender_id": message.sender_id,
                            "sender": message.user_name,
                            "message_id": message.id,
                            "message": "Message encoded",
                            "fileUrl": message.fileUrl,
                        } for message in messages
                    ]


        return message_data

    except Exception as e:
        logger.error(f"Error retrieving new messages: {e}", exc_info=True)
        return []

async def get_pending_invitations(session: AsyncSession, user_id: int):
    """
    Retrieve a list of all the pending room invitations sent to the specified user.

    Args:
        session (AsyncSession): The database session.
        user_id (int): The ID of the user.

    Returns:
        List[Dict[str, Any]]: Information about the pending invitations. Each
            invitation is represented as a dictionary with the keys "room",
            "sender", and "invitation_id".
    """
    try:
        result = await session.execute(
        select(models.RoomInvitation)
        .options(joinedload(models.RoomInvitation.room), joinedload(models.RoomInvitation.sender))
        .filter(
            models.RoomInvitation.recipient_id == user_id,
            models.RoomInvitation.status == 'pending'
        )
        )
        invitations = result.scalars().all()

        invitation_data = [
        {
            "room": invitation.room.name_room,
            "sender": invitation.sender.user_name,
            "invitation_id": invitation.id
        } for invitation in invitations
        ]

        return invitation_data
    except Exception as e:
        logger.error(f"Error retrieving pending invitations: {e}", exc_info=True)
        return []

async def get_rooms_state(session: AsyncSession):
    result = await session.execute(select(models.Rooms))
    rooms = result.scalars().all()
    return [(room.id, room.name_room, room.image_room, room.secret_room, room.owner) for room in rooms]

async def online(session: AsyncSession, user_id: int):
    online = await session.execute(select(models.User_Status).filter(models.User_Status.user_id == user_id, models.User_Status.status == True))
    online = online.scalars().all()
    return online

async def update_user_status(session: AsyncSession, user_id: int, is_online: bool):
    """
    Update the status of a user in the database.

    Args:
        session (AsyncSession): The database session.
        user_id (int): The ID of the user.
        is_online (bool): The new status of the user.

    Returns:
        None

    Raises:
        Exception: If an error occurs while updating the user status.
    """
    try:
        await session.execute(
            update(models.User_Status)
            .where(models.User_Status.user_id == user_id)
            .values(status=is_online)
        )
        await session.commit()
        logger.info(f"User status updated for user {user_id}: {is_online}")
    except Exception as e:
        logger.error(f"Error updating user status for user {user_id}: {e}", exc_info=True)
        
        
async def check_user_password(session: AsyncSession, user_id: int, clear: bool):
    """
    Check if the password of a user has been changed and optionally clear the password_changed field.

    Args:
        session (AsyncSession): The database session.
        user_id (int): The ID of the user.
        clear (bool): If True, the password_changed field will be cleared.

    Returns:
        datetime.datetime or None: The date and time when the password was last changed, or None if the user does not exist.

    Raises:
        Exception: If an error occurs while checking or updating the password_changed field.
    """
    try:
        # Fetch the password_changed field for the specified user
        result = await session.execute(select(models.User.password_changed).where(models.User.id == user_id))
        user_password_changed = result.scalar_one_or_none()
        
        if clear == True:
            # Update password_changed field to NULL
            await session.execute(
                update(models.User)
                .where(models.User.id == user_id)
                .values(password_changed=None)
            )
            await session.commit()

        return user_password_changed
    except Exception as e:
        logger.error(f"Error checking user password: {e}", exc_info=True)
        return None


async def user_online_start(session: AsyncSession, user_id: int):
    try:
        timezone = pytz.timezone('UTC')
        current_time_utc = datetime.now(timezone)
        logger.info(f"Updating online session start for user {user_id} at {current_time_utc}")

        # Перевірка наявності запису
        result = await session.execute(
            select(models.UserOnlineTime).where(models.UserOnlineTime.user_id == user_id)
        )
        user_online_record = result.scalar_one_or_none()

        if user_online_record is None:
            # Створення нового запису
            await session.execute(
                insert(models.UserOnlineTime).values(user_id=user_id, session_start=current_time_utc)
            )
        else:
            # Оновлення існуючого запису
            await session.execute(
                update(models.UserOnlineTime)
                .where(models.UserOnlineTime.user_id == user_id)
                .values(session_start=current_time_utc, session_end=None)
            )
        await session.commit()
        
    except Exception as e:
        logger.error(f"Error updating user online session: {e}", exc_info=True)

async def user_online_end(session: AsyncSession, user_id: int):
    try:
        timezone = pytz.timezone('UTC')
        current_time_utc = datetime.now(timezone)
        
        # Отримати останній запис сесії користувача
        result = await session.execute(
            select(models.UserOnlineTime)
            .where(models.UserOnlineTime.user_id == user_id)
            .order_by(models.UserOnlineTime.session_start.desc())
            .limit(1)
        )
        user_online_record = result.scalar_one()
        
        if user_online_record.session_start:
            session_duration = current_time_utc - user_online_record.session_start
            
            await session.execute(
                update(models.UserOnlineTime)
                .where(models.UserOnlineTime.id == user_online_record.id)
                .values(
                    session_end=current_time_utc,
                    total_online_time=models.UserOnlineTime.total_online_time + func.cast(session_duration, Interval)
                )
            )
            await session.commit()
    except Exception as e:
        logger.error(f"Error ending user online session: {e}", exc_info=True)
