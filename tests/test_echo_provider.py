from ecrivez.chat import EchoProvider, Message


def test_echo_provider():
    provider = EchoProvider()
    messages: list[Message] = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "How are you?"},
    ]
    assert provider.chat_completion(messages) == "(echo) How are you?"