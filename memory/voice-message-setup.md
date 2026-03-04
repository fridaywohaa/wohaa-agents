# Voice message setup (Luke approved)

Date: 2026-03-04

## Default behavior
- Luke sends voice message (Telegram/Discord) → Friday transcribes with local Whisper → replies in **text**.
- Friday sends **voice reply only when appropriate**.

## Accuracy-first transcription
- Prefer accuracy over speed.
- Whisper model: `large`
- Language preference:
  - Cantonese: `yue` (fallback `zh` if needed)

## Voice reply trigger rules (suggested/approved direction)
Friday will send a voice reply when:
1) Luke explicitly asks: 「用voice回 / voice覆 / 讀出嚟」
2) Emotional / state check / encouragement where tone helps
3) Simple decision/confirmation that fits in one short answer

Friday will reply text-only when:
- Long/complex info (briefings, long lists)
- External actions require confirmation (send/delete/notify). Text first.

## Test procedure
- Luke sends 5–10s voice
- Friday replies: transcript + understood intent + next action (and voice if rule triggers)
