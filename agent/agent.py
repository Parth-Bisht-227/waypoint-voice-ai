from pathlib import Path
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    Agent, 
    AgentServer,
    AgentSession,
    TurnHandlingOptions,
    inference, #?
)

from livekit.plugins import (
    cartesia,
    deepgram,
    groq,
    silero,
)

ENV_PATH = Path(__file__).resolve().parent / ".env.local"
load_dotenv(ENV_PATH)

class WayPointAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
                You are Waypoint, a helpful travel support voice assistant.
                Speak naturally and concisely.
                Keep most responses to one or two short sentences.
                Ask a clarifying question when the user's meaning is unclear.
                Do not pretend that you have updated applications or performed
                actions yet, because no business tools are connected in this version.
            """
        )

server = AgentServer() 
# This is the process that waits for LiveKit to assign realtime agent sessions/jobs.

@server.rtc_session(agent_name="waypoint-agent") # this registers the fn as handler for realtime sessions for the named agent...
async def waypoint_agent(ctx: agents.JobContext):

    # this represents one realtime conversation
    session = AgentSession(
        vad = silero.VAD.load(), 

        stt= deepgram.STT(
            model = "nova-3",
            language="en",
        ),

        
        llm=groq.LLM(
                model="openai/gpt-oss-20b",
                reasoning_effort="low",
        ),

        tts = cartesia.TTS(
            model = "sonic-3.5",
            voice = "47c38ca4-5f35-497b-b1a3-415245fb35e1",
            language= "en",
        ),

        turn_handling = TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
        ),
    )
    # vad asks --> is the user currently producing speech like audio?
    # detects the speech and silence in btw, but it does not necessarily understand whether we've finished
    # our thought or not

    # turn detector on the other hand, helps ans "has the user actually completed their conversational turn?"

    await session.start(
        room = ctx.room,
        agent= WayPointAssistant(),
    )

    await session.generate_reply(
        instructions=(
            "Greet the user briefly and ask how you can help with their travel."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)