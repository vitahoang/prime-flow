# Change of mind fires on the first report of written code

The support-digest task has the simulated user change their mind partway through. Arms don't share a common "spec approved" moment: mattpocock and pstack don't always write a spec, and some arms build without asking. So the trigger is the first assistant message that reports product code written, tests passing, a task done or a commit, or that asks to approve finished work. That happens in every arm, and always after some code exists, so every arm has to rework built code rather than revise a plan.

Every run must report to the user through the relay when it thinks it's done, and act on the reply (`harness/setup.py`), so an arm that stays quiet during the build still gets the change, and pays for it with rework. The first dry run showed why: a plain agent asked one round, built and stopped without reporting, so the change never fired.
