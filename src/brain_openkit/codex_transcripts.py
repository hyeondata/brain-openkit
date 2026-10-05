"""Read Codex conversation events, never model-input history or reasoning.

Codex CLI 0.149.0 emits completed UserMessage/AgentMessage items in its
append-only event log. Its response_item messages also contain injected
instructions, so a role=user response_item is not evidence of a user turn.
The transcript format is version dependent; unsupported text fails closed.
"""

from pathlib import Path


_NON_TEXT = {'image', 'localImage', 'audio', 'localAudio', 'skill', 'mention'}


def _text_content(content):
    if not isinstance(content, list):
        raise ValueError('Unsupported Codex message content')
    pieces = []
    for part in content:
        if not isinstance(part, dict):
            raise ValueError('Unsupported Codex message content')
        if part.get('type') in {'text', 'Text', 'input_text', 'output_text'}:
            if not isinstance(part.get('text'), str):
                raise ValueError('Codex message text must be a string')
            pieces.append(part['text'])
        elif part.get('type') not in _NON_TEXT:
            raise ValueError('Unsupported Codex message content type')
    return ''.join(pieces)


def parse_codex_transcript(records, *, include_tool_output=False):
    """Return the full retained event history as role/text dictionaries.

Only explicit conversation events are authoritative. Compaction summaries,
replacement model context, prompts from hooks, and reasoning are ignored.
Stable event IDs de-duplicate replay; identical text with distinct IDs remains.
"""
    messages, seen = [], {}
    session_id = None
    event_generation = None
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not isinstance(record.get('payload'), dict):
            raise ValueError('Codex transcript records must have object payloads')
        payload = record['payload']
        identity = (payload.get('id') if record.get('type') == 'session_meta'
                    else payload.get('thread_id'))
        if identity is not None:
            if not isinstance(identity, str) or (session_id is not None and identity != session_id):
                raise ValueError('Codex transcript contains multiple session identities')
            session_id = identity
        role, text, key = None, None, None
        if record.get('type') == 'event_msg':
            if payload.get('type') == 'item_completed':
                item = payload.get('item')
                if not isinstance(item, dict):
                    raise ValueError('Codex completed event lacks its item')
                role = {'UserMessage': 'user', 'AgentMessage': 'assistant'}.get(item.get('type'))
                if role:
                    if event_generation == 'legacy':
                        raise ValueError('Mixed Codex conversation event generations')
                    event_generation = 'completed'
                    identifier = item.get('id')
                    if not isinstance(identifier, str) or not identifier:
                        raise ValueError('Codex message event lacks a stable identifier')
                    key = ('item', identifier)
                    text = _text_content(item.get('content'))
            elif payload.get('type') in {'user_message', 'agent_message'}:
                if event_generation == 'completed':
                    raise ValueError('Mixed Codex conversation event generations')
                event_generation = 'legacy'
                role = 'user' if payload['type'] == 'user_message' else 'assistant'
                text = payload.get('message')
                key = ('legacy', record.get('ordinal', index))
        elif include_tool_output and record.get('type') == 'response_item':
            if payload.get('type') == 'function_call_output':
                role, text = 'tool', payload.get('output')
                if isinstance(text, list):
                    text = _text_content(text)
                key = ('tool', payload.get('call_id', index))
        if role is None:
            continue
        if not isinstance(text, str):
            raise ValueError('Unsupported Codex conversation text')
        message = {'role': role, 'text': text}
        if key in seen:
            if seen[key] != message:
                raise ValueError('Codex replayed event changed its original text')
            continue
        seen[key] = message
        if text:
            messages.append(message)
    return messages


def parse_transcript(path: Path, include_tool_output=False):
    """Read only this explicitly supplied JSONL file, with bounded intake."""
    from .conversation_hooks import read_jsonl
    return parse_codex_transcript(read_jsonl(path), include_tool_output=include_tool_output)
