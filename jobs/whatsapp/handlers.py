from pywa import WhatsApp, filters
from pywa import types as wa_types

from jobs.whatsapp.client import get_whatsapp_client
from jobs.whatsapp.inbound import schedule_inbound_processing

_handlers_registered = False


def register_handlers() -> None:
    global _handlers_registered
    if _handlers_registered:
        return

    wa = get_whatsapp_client()

    @wa.on_message(filters.text)
    def handle_text(_client: WhatsApp, msg: wa_types.Message) -> None:
        schedule_inbound_processing(msg)

    @wa.on_message(filters.voice | filters.audio)
    def handle_voice_or_audio(_client: WhatsApp, msg: wa_types.Message) -> None:
        schedule_inbound_processing(msg)

    @wa.on_message(filters.video)
    def handle_video(_client: WhatsApp, msg: wa_types.Message) -> None:
        schedule_inbound_processing(msg)

    @wa.on_message(filters.image)
    def handle_image(_client: WhatsApp, msg: wa_types.Message) -> None:
        schedule_inbound_processing(msg)

    _handlers_registered = True
