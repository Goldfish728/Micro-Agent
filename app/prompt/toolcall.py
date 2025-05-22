SYSTEM_PROMPT = "You are an agent that can execute tool calls"

# NEXT_STEP_PROMPT = (
#     "If you want to stop interaction, use `terminate` tool/function call."
# )

NEXT_STEP_PROMPT = (
    "If you have finished the task and no need to cooperate with other agents, use `terminate` tool/function call."
    "If you want to handoff the work to another agent, use `handoff` tool/function call."
)