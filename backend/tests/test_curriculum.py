import unittest
from unittest.mock import patch,AsyncMock
from app import curriculum
class CurriculumTests(unittest.IsolatedAsyncioTestCase):
 async def test_complete_coverage_and_conflicts(self):
  curriculum._cache.clear()
  with patch.object(curriculum.llm,'acomplete_json',new_callable=AsyncMock,return_value={'groups':[{'title':'Basics','stage':0,'ids':['a','a','invented']},{'title':'Later','stage':3,'ids':['b']}]}) as model:
   result=await curriculum.propose([{'id':x,'name':x} for x in ['a','b','c']],[{'source':'b','target':'a','type':'PREREQUISITE_OF'}],'en')
   self.assertEqual(sorted(x for g in result['groups'] for x in g['ids']),['a','b','c'])
   self.assertEqual(len(result['conflicts']),1)
   self.assertEqual(result['coverage'],3)
