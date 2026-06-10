import chainlit as cl
from chat_session import ChatSession

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("session", ChatSession())

@cl.on_message
async def on_message(message: cl.Message):
    session: ChatSession = cl.user_session.get("session")
    await session.send(message.content)