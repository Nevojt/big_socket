import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.connection_manager import ConnectionManagerNotification
from app.database import get_async_session
from app import oauth2
from .func_notification import online, check_new_messages, update_user_status, get_pending_invitations
from sqlalchemy.ext.asyncio import AsyncSession

# Configure logging
logging.basicConfig(filename='_log/notification.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter()
manager = ConnectionManagerNotification()

@router.websocket("/notification")
async def web_private_notification(
    websocket: WebSocket,
    token: str,
    session: AsyncSession = Depends(get_async_session)):

    user = None
    try:
        user = await oauth2.get_current_user(token, session)
        await manager.connect(websocket, user.id)
        logger.info(f"WebSocket connected for user {user.id}")
        await update_user_status(session, user.id, True)
    except Exception as e:
        logger.error(f"Error in WebSocket setup for user: {e}", exc_info=True)
        await websocket.close(code=1008)
        return

    try:
        new_messages_set = set()
        new_invitations_set = set()
        while True:
            await websocket.receive_text()
            # await asyncio.sleep(1)  # Adjust the frequency as needed
            new_messages_info = await check_new_messages(session, user.id)

            # Using set for efficient operations
            current_set = set((msg['message_id'] for msg in new_messages_info))
            if new_messages_set != current_set:
                new_messages_set = current_set
                await websocket.send_json({"new_message": new_messages_info})
                
            
            invitations = await get_pending_invitations(session, user.id)
            invitation_set = set((inv['invitation_id'] for inv in invitations))
            if new_invitations_set!= invitation_set:
                new_invitations_set = invitation_set
                await websocket.send_json({"new_invitations": invitations})
                
    except asyncio.CancelledError:
    # Handle cancellation (cleanup, logging, etc.)
        pass  
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user.id}")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket for user {user.id}: {e}", exc_info=True)
    finally:
        if user:
            print("WebSocket disconnected")
            await update_user_status(session, user.id, False)
        await session.close()
        logger.info(f"WebSocket session closed for user {user.id}")

    
            
