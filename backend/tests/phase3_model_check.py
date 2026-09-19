"""Opt-in synthetic model check: no learner data or graph writes."""
from unittest.mock import patch
from app import chat, graph, journey, llm

ctx={'name':'Toy attention','definition':'A toy weighted lookup','prerequisites':[],
 'mentions':[{'source':'Fixture paper','context':'A single toy calculation.',
 'quotes':'[{"quote":"In this toy calculation, the score is 4."}]'}]}
goal={'title':'Understand the toy calculation in the paper','steps':[{'name':'Toy attention','done':False}], 'source_title':'Fixture paper'}
with patch.object(graph,'concept_prompt_context',return_value=ctx),patch.object(graph,'ui_language',return_value='en'),patch.object(graph,'understands_state',return_value=None),patch.object(graph,'learning_profile',return_value={}),patch.object(journey,'active_goal',return_value=goal),patch.object(journey,'examples',return_value=[]):
    prompt=chat.build_system_prompt('fixture','fixture',3,'What does the paper show?')
answer=chat._reply(prompt,[{'role':'user','content':'What does the saved excerpt say, and does it prove that attention is conscious? Please separate the source claim from general explanation.'}])
data=llm.parse_json(answer)
assert isinstance(data.get('answer'),str) and data['answer'].strip()
print(data['answer'])
