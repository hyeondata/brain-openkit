import json
import tempfile
import unittest
from pathlib import Path

from brain_openkit.codex_transcripts import parse_codex_transcript, parse_transcript


def completed(kind, identifier, text, *, turn='turn-1'):
    return {
        'type': 'event_msg', 'payload': {
            'type': 'item_completed', 'thread_id': 'session-1', 'turn_id': turn,
            'item': {'type': kind, 'id': identifier, 'content': [
                {'type': 'text' if kind == 'UserMessage' else 'Text', 'text': text},
            ]},
        },
    }


class CodexTranscriptTests(unittest.TestCase):
    def test_native_events_preserve_text_without_context_or_duplicate_response_items(self):
        records = [
            {'type': 'session_meta', 'payload': {'id': 'session-1'}},
            {'type': 'response_item', 'payload': {
                'type': 'message', 'role': 'user', 'content': [
                    {'type': 'input_text', 'text': '<environment_context>private</environment_context>'},
                ],
            }},
            completed('UserMessage', 'user-1', ' 원문\r\n질문 '),
            completed('AgentMessage', 'answer-1', '응답\n  끝 '),
            {'type': 'response_item', 'payload': {
                'type': 'message', 'role': 'assistant', 'content': [
                    {'type': 'output_text', 'text': '응답\n  끝 '},
                ],
            }},
        ]
        self.assertEqual([
            {'role': 'user', 'text': ' 원문\r\n질문 '},
            {'role': 'assistant', 'text': '응답\n  끝 '},
        ], parse_codex_transcript(records))

    def test_replayed_event_ids_are_deduplicated_but_repeated_real_messages_survive(self):
        first = completed('UserMessage', 'user-1', 'same')
        records = [first, first, completed('UserMessage', 'user-2', 'same', turn='turn-2')]
        self.assertEqual([{'role': 'user', 'text': 'same'}] * 2, parse_codex_transcript(records))

    def test_conflicting_replayed_event_fails_instead_of_rewriting_prior_history(self):
        with self.assertRaises(ValueError):
            parse_codex_transcript([
                completed('AgentMessage', 'a', 'before'), completed('AgentMessage', 'a', 'changed'),
            ])

    def test_commentary_and_final_are_retained_but_reasoning_and_tools_default_off(self):
        records = [
            completed('AgentMessage', 'commentary', '진행 중'),
            completed('Reasoning', 'reason', 'hidden reasoning'),
            {'type': 'response_item', 'payload': {
                'type': 'function_call_output', 'call_id': 'call-1', 'output': 'tool output',
            }},
            completed('AgentMessage', 'final', '완료'),
        ]
        self.assertEqual([
            {'role': 'assistant', 'text': '진행 중'}, {'role': 'assistant', 'text': '완료'},
        ], parse_codex_transcript(records))
        self.assertEqual([
            {'role': 'assistant', 'text': '진행 중'}, {'role': 'tool', 'text': 'tool output'},
            {'role': 'assistant', 'text': '완료'},
        ], parse_codex_transcript(records, include_tool_output=True))

    def test_compaction_summary_does_not_replace_original_event_history(self):
        first = [completed('UserMessage', 'u1', 'original'), completed('AgentMessage', 'a1', 'answer')]
        resumed = first + [
            {'type': 'compacted', 'payload': {'message': 'lossy summary', 'replacement_history': []}},
            completed('UserMessage', 'u2', 'new', turn='turn-2'),
            completed('AgentMessage', 'a2', 'new answer', turn='turn-2'),
        ]
        self.assertEqual(parse_codex_transcript(first), parse_codex_transcript(resumed)[:2])
        self.assertEqual('new answer', parse_codex_transcript(resumed)[-1]['text'])

    def test_unknown_message_content_fails_closed_instead_of_silently_truncating(self):
        record = completed('UserMessage', 'u1', 'known')
        record['payload']['item']['content'].append({'type': 'future_text', 'text': 'must not drop'})
        with self.assertRaises(ValueError):
            parse_codex_transcript([record])

    def test_media_and_skill_references_do_not_become_text_messages(self):
        record = completed('UserMessage', 'u1', 'caption')
        record['payload']['item']['content'].extend([
            {'type': 'image', 'url': 'data:image/png;base64,ignored'},
            {'type': 'skill', 'name': 'skill', 'path': '/not-read'},
        ])
        self.assertEqual([{'role': 'user', 'text': 'caption'}], parse_codex_transcript([record]))

    def test_multiple_session_identities_are_rejected(self):
        records = [completed('UserMessage', 'u1', 'one'), completed('AgentMessage', 'a1', 'two')]
        records[1]['payload']['thread_id'] = 'another-session'
        with self.assertRaises(ValueError):
            parse_codex_transcript(records)

    def test_legacy_explicit_message_events_remain_supported(self):
        records = [
            {'timestamp': 'one', 'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'question'}},
            {'timestamp': 'two', 'type': 'event_msg', 'payload': {'type': 'agent_message', 'message': 'answer'}},
        ]
        self.assertEqual([
            {'role': 'user', 'text': 'question'}, {'role': 'assistant', 'text': 'answer'},
        ], parse_codex_transcript(records))

    def test_mixed_event_generations_fail_instead_of_duplicating_a_turn(self):
        with self.assertRaises(ValueError):
            parse_codex_transcript([
                {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'same'}},
                completed('UserMessage', 'u1', 'same'),
            ])

    def test_path_reader_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary).resolve() / 'source.jsonl'
            source.write_text(json.dumps(completed('UserMessage', 'u1', 'private')) + '\n')
            link = Path(temporary).resolve() / 'link.jsonl'
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                parse_transcript(link)

    def test_path_reader_preserves_crlf_text_and_rejects_partial_jsonl(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'transcript.jsonl'
            path.write_text(json.dumps(completed('UserMessage', 'u1', 'a\r\nb')) + '\n')
            self.assertEqual([{'role': 'user', 'text': 'a\r\nb'}], parse_transcript(path))
            path.write_text(path.read_text() + '{"type":')
            with self.assertRaises(ValueError):
                parse_transcript(path)


if __name__ == '__main__':
    unittest.main()
