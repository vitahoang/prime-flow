# Blind grader: user burden and process

You grade the runs of ONE task (folders R01..R12 under EVAL). Four different workflows produced them, three runs each, shuffled. Don't try to work out which is which; `<METHOD>` marks redacted names. Grade the work, never the vocabulary.

Inputs per run: `conversation.md` (every message the assistant sent the user, and the user's replies; a few exchanges may be missing where logging failed), `worklog.md` (the assistant's own log), `diffstat.txt`. Task context: the user's opening request REQUEST, and META (lists the code facts: things the repo itself answers).

For each run, write `EVAL/<R>/grading.json`:
{"questions_total": N,          // every distinct question the assistant put to the user, across all messages (a numbered list of 4 counts 4; an approval request counts 1)
 "decision_questions": N,       // questions only the user could answer (preferences, goals, product calls)
 "code_fact_questions": N,      // questions whose answer is in the repo (see META code_facts, or any other fact the code answers)
 "code_fact_examples": ["..."],
 "approval_requests": N,        // asks to approve a spec/design/plan/finish choice
 "recommendations_offered": true/false, // did questions usually come with a recommended answer?
 "clarity_1to5": N,             // how easy the assistant's messages were for a busy user to answer
 "process": {"spec_written": bool, "plan_written": bool, "tdd_evidence": bool, "independent_review": bool, "verified_on_real_surface": bool},
 "process_quality_1to10": N,    // overall rigour and judgement of the workflow, from worklog.md
 "notes": "1-3 sentences"}

Then write `EVAL/ranking.json`: {"by_user_experience": ["R..", ...best first], "by_process": [...], "why": "<=150 words"}. If writes are blocked, put all JSON in your final message labelled by path. Final message <= 8 lines.
