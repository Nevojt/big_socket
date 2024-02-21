import asyncio
import logging
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.websockets import WebSocketState
from app.connection_manager import ConnectionManagerNotification
from app.database import get_async_session
from app import models, oauth2
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


# Configure logging
logging.basicConfig(filename='_log/notification.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter()
manager = ConnectionManagerNotification()

unread_messages = {}
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
            select(models.PrivateMessage)
            .options(selectinload(models.PrivateMessage.sender))
            .join(models.User, models.PrivateMessage.sender_id == models.User.id)
            .filter(models.PrivateMessage.recipient_id == user_id, models.PrivateMessage.is_read == True)
        )

        # Retrieve the results as a list
        new_messages = new_messages.scalars().all()

        # Extract relevant data for each message
        message_data = []
        for message in new_messages:
            message_data.append({
                "sender_id": message.sender_id,
                "sender": message.sender.user_name,
                "message_id": message.id,
                "message": message.messages,
            })

        return message_data
        
    except Exception as e:
        logger.error(f"Error retrieving new messages: {e}", exc_info=True)
        return []


@router.websocket("/notification")
async def web_private_notification(websocket: WebSocket, token: str, session: AsyncSession = Depends(get_async_session)):
    user = None
    try:
        user = await oauth2.get_current_user(token, session)
        await manager.connect(websocket, user.id)
        logger.info(f"WebSocket connected for user {user.id}")
    except Exception as e:
        logger.error(f"Error authenticating user: {e}", exc_info=True)
        await websocket.close(code=1008)
        return
    
    new_messages_list = []
    
    try:
        while True:

            if websocket.client_state != WebSocketState.CONNECTED:
                logger.info(f"WebSocket not connected for user {user.id}, breaking the loop")
                break
            
            try:
                new_messages_info = await check_new_messages(session, user.id)
                updated = False

                for message in list(new_messages_list):
                    if message not in new_messages_info:
                        new_messages_list.remove(message)
                        updated = True

                for message_info in new_messages_info:
                    if message_info not in new_messages_list:
                        new_messages_list.append(message_info)
                        updated = True

                if updated:
                    await websocket.send_json({
                        "new_message": new_messages_list
                    })
                    
            except websockets.exceptions.ConnectionClosedOK as e:
                logger.info(f"WebSocket connection was closed for user {user.id}: {e}")
                await websocket.close()
            await asyncio.sleep(1)
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user.id}")
        
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket: {e}", exc_info=True)
        
    finally:
        if user:
            await manager.disconnect(user.id, websocket)
            if websocket.client_state in [WebSocketState.CONNECTED, WebSocketState.DISCONNECTED]:
                await websocket.close()