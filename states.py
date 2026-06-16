from aiogram.fsm.state import State, StatesGroup


class VideoCreation(StatesGroup):
    choosing_source = State()   # stock or AI generation
    entering_topic = State()    # video topic
    choosing_voice = State()    # TTS voice
    generating = State()        # processing
