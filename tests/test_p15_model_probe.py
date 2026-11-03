"""Offline checks of the model probe's failure detection and network scope."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('p15_probe',
    Path(__file__).resolve().parents[1]/'scripts'/'p15_model_probe.py')
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def completion(text='BLAU42 [Q1]',**fields):
    return {'choices':[{'message':{'content':text,**fields},'finish_reason':'stop'}]}


class ProbeTests(unittest.TestCase):
    def test_detects_obedience_tool_requests_and_missing_evidence(self):
        self.assertTrue(all(probe.assess(completion()).values()))
        for response in (completion(probe.CANARY),completion('BLAU42'),
                         completion(tool_calls=[{'id':'fake'}]),
                         completion(reasoning=probe.CANARY)):
            with self.subTest(response=response):
                self.assertFalse(all(probe.assess(response).values()))
        truncated=completion()
        truncated['choices'][0]['finish_reason']='length'
        self.assertFalse(probe.assess(truncated)['completed'])

    def test_malformed_response_is_technical_error(self):
        for response in ({},{'choices':[]},{'choices':[{'message':{}}]}):
            with self.subTest(response=response),self.assertRaises(ValueError):
                probe.assess(response)

    def test_redirects_are_rejected(self):
        with self.assertRaises(ValueError):
            probe.NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid')

    def test_every_attack_is_included_without_truncation(self):
        for name,attack in probe.CASES:
            messages=probe.make_messages(attack)
            self.assertEqual([item['role'] for item in messages],['system','user'])
            self.assertLessEqual(len(probe.FACT+' '+attack),360)
            self.assertEqual(messages[-1]['content'],probe.QUESTION)


if __name__=='__main__':
    unittest.main()
