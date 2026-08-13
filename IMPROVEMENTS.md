# 100 Improvements for the Perfect AI Agent Chat

Legend: [DONE] implemented · [PLAN] designed, next round · [IDEA] candidate

## Autonomy & Intelligence (1-20)
1. [DONE] Autonomous research: agent searches on its own when info is needed
2. [DONE] Auto-continue: executes plan phases without asking (capped, toggle)
3. [DONE] Tool loop: sees results, iterates (up to 4 rounds)
4. [DONE] Multi-file builds with per-file review
5. [DONE] Project memory per chat (goal, files, next steps)
6. [DONE] Skill packs change behavior per chat
7. [PLAN] Sub-agent spawning for parallel research
8. [PLAN] Self-critique before final answer on hard tasks
9. [PLAN] Answer quality scoring (0-10) on every reply
10. [PLAN] Auto-retry failed turns with a different model
11. [PLAN] Context compression: summarize old messages when chat grows
12. [IDEA] Debate mode: two models argue, best answer wins
13. [IDEA] Self-improving prompt: agent proposes prompt patches
14. [IDEA] Goal decomposition with dependency graph
15. [IDEA] Auto-commit progress notes to repo each session
16. [IDEA] Learn from user corrections instantly (feedback loop)
17. [IDEA] Curiosity trigger: asks questions back on vague asks
18. [IDEA] Time-aware answers (knows today's date context)
19. [IDEA] Location-aware answers (geocoding built in)
20. [IDEA] Multi-turn planning with checkpoint resumption

## Tools & Integrations (21-40)
21. [DONE] MCP client: connect remote MCP servers, list & call tools
22. [DONE] api_call: 21+ keyless public APIs
23. [DONE] web_search + HN/Reddit/GitHub social search
24. [DONE] tutorial / sys_design / roadmap / design_ref knowledge tools
25. [DONE] code_lookup, pdf_text, save/read/list repo
26. [PLAN] MCP catalog browser inside the app
27. [PLAN] Local MCP via pipeline runner
28. [PLAN] YouTube Data API upload flow (documented, key-gated)
29. [PLAN] Telegram bot reconnect + inline scheduler
30. [PLAN] Zapier/Make/n8n webhook recipes
31. [PLAN] Browser extension to summon Nexus anywhere
32. [PLAN] PWA install + offline shell
33. [IDEA] WhatsApp bridge via webhook when business API available
34. [IDEA] Discord bot
35. [IDEA] Slack slash command
36. [IDEA] Email agent (send/receive digests)
37. [IDEA] Calendar integration
38. [IDEA] File sync to Drive/OneDrive
39. [IDEA] Image generation (Puter txt2img) tool
40. [IDEA] Music/audio generation tool

## Scheduling & Automation (41-50)
41. [DONE] Scheduler: interval tasks + reminders (browser + notifications)
42. [DONE] schedule_task tool: agent can schedule itself
43. [DONE] Notification permission flow
44. [PLAN] Cron-style times (daily at 9am)
45. [PLAN] Task chain: "when task A done, run B"
46. [PLAN] Recurring reports (daily digest of prices/news)
47. [PLAN] Pause-all / resume-all scheduler controls
48. [PLAN] Schedule history log
49. [IDEA] Wake-up automation (opens app, runs task)
50. [IDEA] Watchdog: monitor a URL and alert on change

## Chat UX (51-70)
51. [DONE] Multiple chats + persistence + switch/delete
52. [DONE] Auto-titled chats from first message
53. [DONE] Relative timestamps ("2m ago")
54. [DONE] Retry last turn + STOP button
55. [DONE] Copy buttons on replies and artifacts
56. [DONE] Recent prompts dropdown (last 10)
57. [DONE] Textarea composer: Enter send, Shift+Enter newline
58. [DONE] Drag-drop + paste-image attachments
59. [DONE] Voice input (Web Speech) + text-to-speech toggle
60. [DONE] Follow-mode auto-scroll toggle
61. [DONE] In-chat search filter for history
62. [DONE] Esc / click-outside closes modals
63. [DONE] Reduced-motion + a11y polish
64. [DONE] Zip-download all artifacts
65. [DONE] Brain doctor: test all providers at once
66. [PLAN] Message editing + reactions
67. [PLAN] Code block copy + word wrap toggle
68. [PLAN] Dark mode toggle
69. [PLAN] Font size control
70. [PLAN] Image preview lightbox

## Reliability & Performance (71-85)
71. [DONE] Limit auto-fallback across providers
72. [DONE] Lazy Monaco, throttled streaming, light particles
73. [DONE] Overscroll/scroll-leak fixes
74. [DONE] CI UI syntax check
75. [PLAN] Local request queue with retry/backoff
76. [PLAN] Offline indicator + reconnection
77. [PLAN] Storage size guard + cleanup
78. [PLAN] Crash recovery (restore last session state)
79. [PLAN] Per-provider health dashboard
80. [PLAN] Token/context usage estimator
81. [PLAN] Artifact size limits with warnings
82. [IDEA] Service worker caching for faster loads
83. [IDEA] Preload models on idle
84. [IDEA] Benchmarks: measure provider latency per task
85. [IDEA] Auto-tune temperature per task type

## Memory & Learning (86-92)
86. [DONE] Session lessons (dedup, cap 10)
87. [DONE] Project memory per chat
88. [PLAN] Memory consolidation (summarize old turns)
89. [PLAN] Export/import memory across devices
90. [PLAN] Memory browser UI with edit/delete
91. [IDEA] Cross-chat shared knowledge base
92. [IDEA] User-preference learning (style, tone, defaults)

## Platform (93-100)
93. [PLAN] PWA install
94. [PLAN] Multi-device sync via repo-backed storage
95. [PLAN] Usage analytics dashboard (runs, tokens, costs)
96. [PLAN] Admin/security: token rotation reminders
97. [PLAN] Shareable chat links
98. [IDEA] Team mode with roles
99. [IDEA] Mobile app shell
100. [PLAN] Plugin marketplace for Nexus itself
