import chainlit as cl
from agent.agent_session import AgentSession

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("session", AgentSession())

# app.py
@cl.on_message
async def on_message(message: cl.Message):
    session = cl.user_session.get("session")
    
    cl_msg = cl.Message(content="")
    await cl_msg.send()

    async def on_token(text: str):
        await cl_msg.stream_token(text)

    result = await session.run_turn(message.content, on_token=on_token)
    
    cl_msg.content = result.display_text
    await cl_msg.update()
    # render result.charts etc. here in future